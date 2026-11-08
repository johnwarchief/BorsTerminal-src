package tsetmc

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// LockFileName is the canonical lock file name for Market DB single-writer.
const LockFileName = "market_writer.lock"

// ErrWriterLockHeld is returned when another process or thread already holds the writer lock.
var ErrWriterLockHeld = errors.New("writer lock already held")

// LockMetadata contains process identification and timestamp of the lock holder.
type LockMetadata struct {
	PID        int    `json:"pid"`
	AcquiredAt string `json:"acquired_at"`
}

// WriterLock represents an acquired single-writer file lock.
type WriterLock struct {
	lockFilePath string
	file         *os.File
	meta         LockMetadata
	mu           sync.Mutex
	released     bool
}

var (
	activeLocksMu sync.Mutex
	activeLocks   = make(map[string]struct{})
)

func canonicalLockPath(p string) string {
	abs, err := filepath.Abs(p)
	if err != nil {
		abs = p
	}
	clean := filepath.Clean(abs)
	return strings.ToLower(clean)
}

func tryRegisterActiveLock(p string) bool {
	key := canonicalLockPath(p)
	activeLocksMu.Lock()
	defer activeLocksMu.Unlock()
	if _, exists := activeLocks[key]; exists {
		return false
	}
	activeLocks[key] = struct{}{}
	return true
}

func unregisterActiveLock(p string) {
	key := canonicalLockPath(p)
	activeLocksMu.Lock()
	defer activeLocksMu.Unlock()
	delete(activeLocks, key)
}

// LockFilePath returns the absolute or configured path of the lock file.
func (l *WriterLock) LockFilePath() string {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.lockFilePath
}

// File returns the underlying open os.File, or nil if released.
func (l *WriterLock) File() *os.File {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.file
}

// PID returns the process ID recorded in the lock metadata.
func (l *WriterLock) PID() int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.meta.PID
}

// AcquiredAt returns the RFC3339 timestamp when the lock was acquired.
func (l *WriterLock) AcquiredAt() string {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.meta.AcquiredAt
}

// Metadata returns a copy of the lock metadata.
func (l *WriterLock) Metadata() LockMetadata {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.meta
}

// AcquireWriterLock acquires an exclusive single-writer file lock in dataDir.
// If dataDir does not exist, it is created.
// Returns ErrWriterLockHeld if the lock is held by another process or thread.
func AcquireWriterLock(dataDir string) (*WriterLock, error) {
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create data dir %s: %w", dataDir, err)
	}

	lockFilePath := filepath.Join(dataDir, LockFileName)

	if !tryRegisterActiveLock(lockFilePath) {
		pid := readLockPID(lockFilePath)
		if pid <= 0 {
			pid = os.Getpid()
		}
		return nil, fmt.Errorf("%w: by PID %d or external process", ErrWriterLockHeld, pid)
	}

	success := false
	defer func() {
		if !success {
			unregisterActiveLock(lockFilePath)
		}
	}()

	file, err := os.OpenFile(lockFilePath, os.O_CREATE|os.O_RDWR, 0666)
	if err != nil {
		if isLockOrSharingViolation(err) {
			pid := readLockPID(lockFilePath)
			return nil, fmt.Errorf("%w: by PID %d or external process", ErrWriterLockHeld, pid)
		}
		return nil, fmt.Errorf("failed to open lock file %s: %w", lockFilePath, err)
	}

	if err := osLockFile(file); err != nil {
		_ = file.Close()
		if errors.Is(err, ErrWriterLockHeld) {
			pid := readLockPID(lockFilePath)
			return nil, fmt.Errorf("%w: by PID %d or external process", ErrWriterLockHeld, pid)
		}
		return nil, fmt.Errorf("failed to acquire OS lock on %s: %w", lockFilePath, err)
	}

	if err := file.Truncate(0); err != nil {
		_ = osUnlockFile(file)
		_ = file.Close()
		return nil, fmt.Errorf("failed to truncate lock file %s: %w", lockFilePath, err)
	}

	if _, err := file.Seek(0, io.SeekStart); err != nil {
		_ = osUnlockFile(file)
		_ = file.Close()
		return nil, fmt.Errorf("failed to seek lock file %s: %w", lockFilePath, err)
	}

	meta := LockMetadata{
		PID:        os.Getpid(),
		AcquiredAt: time.Now().UTC().Format(time.RFC3339),
	}

	data, err := json.Marshal(meta)
	if err != nil {
		_ = osUnlockFile(file)
		_ = file.Close()
		return nil, fmt.Errorf("failed to marshal lock info: %w", err)
	}

	if _, err := file.Write(data); err != nil {
		_ = osUnlockFile(file)
		_ = file.Close()
		return nil, fmt.Errorf("failed to write lock info: %w", err)
	}
	_ = file.Sync()

	success = true
	return &WriterLock{
		lockFilePath: lockFilePath,
		file:         file,
		meta:         meta,
	}, nil
}

// AcquireWriterLockWithTimeout attempts to acquire the lock within ctx deadline/cancellation.
// Retries periodically according to retryInterval (defaulting to 50ms if <= 0).
func AcquireWriterLockWithTimeout(ctx context.Context, dataDir string, retryInterval time.Duration) (*WriterLock, error) {
	if retryInterval <= 0 {
		retryInterval = 50 * time.Millisecond
	}

	if err := ctx.Err(); err != nil {
		return nil, fmt.Errorf("%w: context canceled: %v", ErrWriterLockHeld, err)
	}

	for {
		lock, err := AcquireWriterLock(dataDir)
		if err == nil {
			return lock, nil
		}
		if !errors.Is(err, ErrWriterLockHeld) {
			return nil, err
		}

		select {
		case <-ctx.Done():
			return nil, fmt.Errorf("%w: waiting for lock in %s timed out or canceled: %v", ErrWriterLockHeld, dataDir, ctx.Err())
		case <-time.After(retryInterval):
		}
	}
}

// Release unlocks the OS-level lock, closes the underlying file descriptor,
// and cleans up the lock file. Calling Release multiple times is safe (idempotent).
func (l *WriterLock) Release() error {
	if l == nil {
		return nil
	}
	l.mu.Lock()
	defer l.mu.Unlock()

	if l.released {
		return nil
	}
	l.released = true

	unregisterActiveLock(l.lockFilePath)

	var firstErr error

	if l.file != nil {
		if err := osUnlockFile(l.file); err != nil && firstErr == nil {
			firstErr = fmt.Errorf("failed to unlock file: %w", err)
		}
		if err := l.file.Close(); err != nil && firstErr == nil {
			firstErr = fmt.Errorf("failed to close lock file: %w", err)
		}
		l.file = nil
	}

	if l.lockFilePath != "" {
		_ = os.Remove(l.lockFilePath)
	}

	return firstErr
}

// ReadLockMetadata reads and parses lock metadata from the specified lock file path.
func ReadLockMetadata(lockFilePath string) (*LockMetadata, error) {
	data, err := os.ReadFile(lockFilePath)
	if err != nil {
		data = readLockedFileFallback(lockFilePath)
	}
	if len(data) == 0 {
		if err != nil {
			return nil, err
		}
		return nil, errors.New("lock file is empty")
	}

	var meta LockMetadata
	if err := json.Unmarshal(data, &meta); err != nil {
		return nil, fmt.Errorf("failed to parse lock metadata: %w", err)
	}
	return &meta, nil
}

// InspectWriterLock inspects whether a lock file exists in dataDir, returning its metadata
// and whether the recorded holder process is currently alive.
func InspectWriterLock(dataDir string) (*LockMetadata, bool, error) {
	lockFilePath := filepath.Join(dataDir, LockFileName)
	meta, err := ReadLockMetadata(lockFilePath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, false, nil
		}
		return nil, false, err
	}
	alive := IsProcessAlive(meta.PID)
	return meta, alive, nil
}

// IsProcessAlive checks whether the process with the given PID is currently running.
func IsProcessAlive(pid int) bool {
	return isProcessAlive(pid)
}

func readLockPID(path string) int {
	data, err := os.ReadFile(path)
	if err != nil {
		data = readLockedFileFallback(path)
	}
	if len(data) == 0 {
		return 0
	}
	var meta LockMetadata
	if err := json.Unmarshal(data, &meta); err == nil && meta.PID > 0 {
		return meta.PID
	}
	return 0
}
