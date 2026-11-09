//go:build !windows

package securefile

import (
	"fmt"
	"os"
)

func Restrict(path string) error {
	if err := os.Chmod(path, 0o600); err != nil {
		return fmt.Errorf("chmod 0600: %w", err)
	}
	return nil
}

func Verify(path string) error {
	fi, err := os.Stat(path)
	if err != nil {
		return err
	}
	if fi.Mode().Perm() != 0o600 {
		return fmt.Errorf("file mode is %o, want 0600", fi.Mode().Perm())
	}
	return nil
}
