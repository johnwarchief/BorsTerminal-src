//go:build !windows

package pointerfile

import "os"

func replaceAtomic(tmp, dst string) error {
	return os.Rename(tmp, dst)
}
