//go:build windows

package main

import (
	"os/exec"
	"strconv"
	"unsafe"

	"golang.org/x/sys/windows"
)

// setProcGroup is a no-op on Windows: the child is killed through taskkill /T,
// which walks the tree by parent PID.
func setProcGroup(cmd *exec.Cmd) {}

// processTree reads the full process table from a Toolhelp32 snapshot. No WMI
// and no elevation: TH32CS_SNAPPROCESS needs neither.
func processTree() ([]proc, error) {
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return nil, err
	}
	defer windows.CloseHandle(snap)
	var e windows.ProcessEntry32
	e.Size = uint32(unsafe.Sizeof(e))
	out := []proc{}
	for err = windows.Process32First(snap, &e); err == nil; err = windows.Process32Next(snap, &e) {
		out = append(out, proc{
			PID:    int(e.ProcessID),
			Parent: int(e.ParentProcessID),
			Name:   windows.UTF16ToString(e.ExeFile[:]),
		})
	}
	return out, nil
}

// killTree terminates the verified root and its descendants. stopTree has
// already proven that pid is the process this command started.
func killTree(pid int) {
	_ = exec.Command("taskkill", "/T", "/F", "/PID", strconv.Itoa(pid)).Run()
}
