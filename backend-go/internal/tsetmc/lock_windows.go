//go:build windows

package tsetmc

import (
	"bytes"
	"errors"
	"os"
	"syscall"

	"golang.org/x/sys/windows"
)

func osLockFile(file *os.File) error {
	var ov windows.Overlapped
	err := windows.LockFileEx(
		windows.Handle(file.Fd()),
		windows.LOCKFILE_EXCLUSIVE_LOCK|windows.LOCKFILE_FAIL_IMMEDIATELY,
		0,
		1,
		0,
		&ov,
	)
	if err != nil {
		if isLockOrSharingViolation(err) {
			return ErrWriterLockHeld
		}
		return err
	}
	return nil
}

func osUnlockFile(file *os.File) error {
	var ov windows.Overlapped
	err := windows.UnlockFileEx(
		windows.Handle(file.Fd()),
		0,
		1,
		0,
		&ov,
	)
	if err != nil {
		return err
	}
	return nil
}

func isProcessAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	h, err := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION, false, uint32(pid))
	if err != nil {
		return false
	}
	defer windows.CloseHandle(h)

	var exitCode uint32
	if err := windows.GetExitCodeProcess(h, &exitCode); err != nil {
		return false
	}
	const stillActive = 259
	return exitCode == stillActive
}

func isLockOrSharingViolation(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, windows.ERROR_LOCK_VIOLATION) || errors.Is(err, windows.ERROR_SHARING_VIOLATION) {
		return true
	}
	var errno syscall.Errno
	if errors.As(err, &errno) {
		if errno == 32 || errno == 33 { // ERROR_SHARING_VIOLATION (32), ERROR_LOCK_VIOLATION (33)
			return true
		}
	}
	return false
}

func readLockedFileFallback(path string) []byte {
	f, err := os.OpenFile(path, os.O_RDONLY, 0)
	if err != nil {
		return nil
	}
	defer f.Close()

	buf := make([]byte, 512)
	n, _ := f.ReadAt(buf, 1)
	if n <= 0 {
		return nil
	}
	content := bytes.TrimSpace(buf[:n])
	if !bytes.HasPrefix(content, []byte("{")) {
		content = append([]byte("{"), content...)
	}
	return content
}
