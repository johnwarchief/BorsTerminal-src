//go:build windows

package securefile

import (
	"fmt"
	"runtime"
	"unsafe"

	"golang.org/x/sys/windows"
)

func currentUserSID() (*windows.SID, error) {
	tu, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		return nil, fmt.Errorf("read current user: %w", err)
	}
	if tu.User.Sid == nil {
		return nil, fmt.Errorf("current user SID is nil")
	}
	return tu.User.Sid, nil
}

// Restrict DACL را به یک ACE برایِ کاربرِ جاری محدود و وراثت را قطع می‌کند.
func Restrict(path string) error {
	sid, err := currentUserSID()
	if err != nil {
		return err
	}
	var pinner runtime.Pinner
	pinner.Pin(sid)
	defer pinner.Unpin()

	entries := []windows.EXPLICIT_ACCESS{{
		AccessPermissions: windows.GENERIC_ALL,
		AccessMode:        windows.GRANT_ACCESS,
		Inheritance:       windows.NO_INHERITANCE,
		Trustee: windows.TRUSTEE{
			TrusteeForm:  windows.TRUSTEE_IS_SID,
			TrusteeType:  windows.TRUSTEE_IS_USER,
			TrusteeValue: windows.TrusteeValueFromSID(sid),
		},
	}}
	acl, err := windows.ACLFromEntries(entries, nil)
	if err != nil {
		return fmt.Errorf("build dacl: %w", err)
	}
	if err := windows.SetNamedSecurityInfo(path, windows.SE_FILE_OBJECT,
		windows.DACL_SECURITY_INFORMATION|windows.PROTECTED_DACL_SECURITY_INFORMATION,
		nil, nil, acl, nil); err != nil {
		return fmt.Errorf("set dacl: %w", err)
	}
	return nil
}

// Verify می‌سنجد DACL دقیقاً یک ACEِ allow برایِ کاربرِ جاری دارد.
func Verify(path string) error {
	sd, err := windows.GetNamedSecurityInfo(path, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION)
	if err != nil {
		return fmt.Errorf("read security info: %w", err)
	}
	dacl, _, err := sd.DACL()
	if err != nil {
		return fmt.Errorf("read dacl: %w", err)
	}
	if dacl == nil {
		return fmt.Errorf("dacl is nil")
	}
	if dacl.AceCount != 1 {
		return fmt.Errorf("dacl has %d allow entries; want exactly 1 (current user)", dacl.AceCount)
	}
	var ace *windows.ACCESS_ALLOWED_ACE
	if err := windows.GetAce(dacl, 0, &ace); err != nil {
		return fmt.Errorf("read ace: %w", err)
	}
	if ace.Header.AceType != windows.ACCESS_ALLOWED_ACE_TYPE {
		return fmt.Errorf("ace type %d is not allow", ace.Header.AceType)
	}
	sid := (*windows.SID)(unsafe.Pointer(&ace.SidStart))
	user, err := currentUserSID()
	if err != nil {
		return err
	}
	if !sid.Equals(user) {
		return fmt.Errorf("dacl belongs to %s, not the current user", sid)
	}
	if ace.Mask&windows.GENERIC_ALL == 0 && ace.Mask&windows.FILE_GENERIC_READ == 0 {
		return fmt.Errorf("current user cannot read the file (mask %#x)", ace.Mask)
	}
	return nil
}
