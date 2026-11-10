//go:build linux

package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

// setProcGroup puts the child in its own process group so killTree can signal
// the whole tree with one kill(-pgid).
func setProcGroup(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

// processTree reads /proc/<pid>/stat for every process. comm may contain
// spaces and parentheses, so the parent/name split is anchored on the last ')'.
func processTree() ([]proc, error) {
	ents, err := os.ReadDir("/proc")
	if err != nil {
		return nil, err
	}
	out := []proc{}
	for _, e := range ents {
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		b, err := os.ReadFile(filepath.Join("/proc", e.Name(), "stat"))
		if err != nil {
			continue
		}
		s := string(b)
		i := strings.LastIndex(s, ")")
		if i < 0 {
			continue
		}
		f := strings.Fields(s[i+1:])
		if len(f) < 2 {
			continue
		}
		ppid, _ := strconv.Atoi(f[1])
		// stat is "pid (comm) state ppid ..."; comm may itself contain spaces
		// and parentheses, so take the text between the last '(' and the ')'
		// that was already located.
		open := strings.LastIndex(s[:i], "(")
		if open < 0 {
			continue
		}
		out = append(out, proc{PID: pid, Parent: ppid, Name: s[open+1 : i]})
	}
	return out, nil
}

// killTree terminates the verified process group and the root itself. It only
// runs after stopTree has proven that pid is the process this command started.
func killTree(pid int) {
	_ = syscall.Kill(-pid, syscall.SIGKILL)
	_ = syscall.Kill(pid, syscall.SIGKILL)
}
