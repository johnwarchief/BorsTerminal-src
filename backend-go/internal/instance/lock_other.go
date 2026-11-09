//go:build !windows

package instance

import (
	"fmt"
	"os"
	"syscall"
)

func acquire(path string) (*Lock, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		return nil, fmt.Errorf("open lock file: %w", err)
	}
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		_ = f.Close()
		if err == syscall.EWOULDBLOCK {
			return nil, ErrAlreadyRunning
		}
		return nil, fmt.Errorf("flock %s: %w", path, err)
	}
	if _, err := f.WriteAt([]byte(fmt.Sprintf("pid=%d\n", os.Getpid())), 0); err != nil {
		_ = f.Close()
		return nil, err
	}
	return &Lock{path: path, file: f}, nil
}

func release(l *Lock) error {
	f := l.file
	l.file = nil
	_ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN)
	return f.Close()
}
