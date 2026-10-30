//go:build windows

package market

import (
	"os/exec"
	"syscall"
)

// hideWindow عینِ CREATE_NO_WINDOWِ api/_core.py؛ بی‌آن هر پولینگِ sync-state
// یک پنجرۀ کنسول رویِ میزِ کاربر پدیدار می‌کند.
func hideWindow(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
}
