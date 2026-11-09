//go:build windows

package pointerfile

import (
	"errors"
	"os"
	"syscall"
	"time"
)

const (
	replaceAttempts = 100
	replaceBackoff  = 2 * time.Millisecond

	errSharingViolation syscall.Errno = 32
)

func replaceAtomic(tmp, dst string) error {
	var err error
	for i := 0; i < replaceAttempts; i++ {
		err = os.Rename(tmp, dst)
		if err == nil {
			return nil
		}
		if !sharingViolation(err) {
			return err
		}
		time.Sleep(replaceBackoff)
	}
	return err
}

func sharingViolation(err error) bool {
	var errno syscall.Errno
	if errors.As(err, &errno) {
		return errno == syscall.ERROR_ACCESS_DENIED || errno == errSharingViolation
	}
	return false
}
