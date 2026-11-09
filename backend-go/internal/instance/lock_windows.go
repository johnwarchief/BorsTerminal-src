//go:build windows

package instance

import (
	"errors"
	"fmt"
	"os"

	"golang.org/x/sys/windows"
)

func acquire(path string) (*Lock, error) {
	name, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return nil, err
	}
	// share mode صفر: هیچ handle دیگری (حتی در همین پروسه) نمی‌تواند بازش کند.
	h, err := windows.CreateFile(name,
		windows.GENERIC_READ|windows.GENERIC_WRITE, 0, nil,
		windows.OPEN_ALWAYS, windows.FILE_ATTRIBUTE_NORMAL, 0)
	if err != nil {
		if errors.Is(err, windows.ERROR_SHARING_VIOLATION) {
			return nil, ErrAlreadyRunning
		}
		return nil, fmt.Errorf("lock %s: %w", path, err)
	}
	f := os.NewFile(uintptr(h), path)
	if _, err := f.WriteAt([]byte(fmt.Sprintf("pid=%d\n", os.Getpid())), 0); err != nil {
		_ = f.Close()
		return nil, fmt.Errorf("write lock file: %w", err)
	}
	return &Lock{path: path, file: f}, nil
}

func release(l *Lock) error {
	f := l.file
	l.file = nil
	return f.Close()
}
