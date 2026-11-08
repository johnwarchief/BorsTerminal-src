//go:build !windows

package tsetmc

import (
	"errors"
	"os"
	"syscall"

	"golang.org/x/sys/unix"
)

func osLockFile(file *os.File) error {
	err := unix.Flock(int(file.Fd()), unix.LOCK_EX|unix.LOCK_NB)
	if err != nil {
		if errors.Is(err, unix.EWOULDBLOCK) || errors.Is(err, unix.EAGAIN) {
			return ErrWriterLockHeld
		}
		return err
	}
	return nil
}

func osUnlockFile(file *os.File) error {
	return unix.Flock(int(file.Fd()), unix.LOCK_UN)
}

func isProcessAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	return proc.Signal(syscall.Signal(0)) == nil
}

func isLockOrSharingViolation(err error) bool {
	if err == nil {
		return false
	}
	return errors.Is(err, unix.EWOULDBLOCK) || errors.Is(err, unix.EAGAIN)
}

func readLockedFileFallback(path string) []byte {
	return nil
}
