//go:build !windows

package market

import "os/exec"

func hideWindow(cmd *exec.Cmd) {}
