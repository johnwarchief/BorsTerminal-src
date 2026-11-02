import sys
import ctypes
from ctypes import wintypes

class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('lpReserved', wintypes.LPWSTR),
        ('lpDesktop', wintypes.LPWSTR),
        ('lpTitle', wintypes.LPWSTR),
        ('dwX', wintypes.DWORD),
        ('dwY', wintypes.DWORD),
        ('dwXSize', wintypes.DWORD),
        ('dwYSize', wintypes.DWORD),
        ('dwXCountChars', wintypes.DWORD),
        ('dwYCountChars', wintypes.DWORD),
        ('dwFillAttribute', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('wShowWindow', wintypes.WORD),
        ('cbReserved2', wintypes.WORD),
        ('lpReserved2', ctypes.c_void_p),
        ('hStdInput', wintypes.HANDLE),
        ('hStdOutput', wintypes.HANDLE),
        ('hStdError', wintypes.HANDLE),
    ]

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('hProcess', wintypes.HANDLE),
        ('hThread', wintypes.HANDLE),
        ('dwProcessId', wintypes.DWORD),
        ('dwThreadId', wintypes.DWORD),
    ]

class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ('nLength', wintypes.DWORD),
        ('lpSecurityDescriptor', ctypes.c_void_p),
        ('bInheritHandle', wintypes.BOOL),
    ]

def run_agent_desktop(args_list):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    
    sa = SECURITY_ATTRIBUTES()
    sa.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
    sa.bInheritHandle = True
    sa.lpSecurityDescriptor = None

    hRead, hWrite = wintypes.HANDLE(), wintypes.HANDLE()
    if not kernel32.CreatePipe(ctypes.byref(hRead), ctypes.byref(hWrite), ctypes.byref(sa), 0):
        raise OSError("CreatePipe failed")
    
    kernel32.SetHandleInformation(hRead, 1, 0) # Non-inheritable read handle

    si = STARTUPINFO()
    si.cb = ctypes.sizeof(STARTUPINFO)
    si.lpDesktop = r"WinSta0\Default"
    si.dwFlags = 0x00000100 # STARTF_USESTDHANDLES
    si.hStdOutput = hWrite
    si.hStdError = hWrite

    pi = PROCESS_INFORMATION()
    exe = r"C:\Users\PCMOD\AppData\Roaming\npm\node_modules\agent-desktop\bin\agent-desktop-win32-x64.exe"
    
    # Build command line
    cmd_parts = [f'"{exe}"'] + [f'"{a}"' if ' ' in a or '@' in a else a for a in args_list]
    cmd_line = ' '.join(cmd_parts)

    ok = kernel32.CreateProcessW(
        None,
        cmd_line,
        None,
        None,
        True,
        0,
        None,
        None,
        ctypes.byref(si),
        ctypes.byref(pi)
    )
    kernel32.CloseHandle(hWrite)
    
    if not ok:
        err = ctypes.get_last_error()
        kernel32.CloseHandle(hRead)
        print(f'{{"ok": false, "error": "CreateProcess failed: {err}"}}')
        return 1

    kernel32.CloseHandle(pi.hThread)
    
    # Read output
    output_chunks = []
    buf = ctypes.create_string_buffer(4096)
    bytes_read = wintypes.DWORD()
    while True:
        success = kernel32.ReadFile(hRead, buf, 4096, ctypes.byref(bytes_read), None)
        if not success or bytes_read.value == 0:
            break
        output_chunks.append(buf.raw[:bytes_read.value])
    
    kernel32.CloseHandle(hRead)
    kernel32.WaitForSingleObject(pi.hProcess, 30000)
    
    exit_code = wintypes.DWORD()
    kernel32.GetExitCodeProcess(pi.hProcess, ctypes.byref(exit_code))
    kernel32.CloseHandle(pi.hProcess)
    
    full_output = b''.join(output_chunks).decode('utf-8', errors='replace')
    sys.stdout.write(full_output)
    return exit_code.value

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(run_agent_desktop(sys.argv[1:]))
