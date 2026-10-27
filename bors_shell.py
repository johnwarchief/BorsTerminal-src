# -*- coding: utf-8 -*-
"""ابزارهایِ پوستهٔ Tauri (D1) — بدونِ وابستگی به لانچر، تا قابلِ تست باشد."""
import json
import os

SHELL_EXE = 'BorsTerminal_Shell.exe'
SHELL_READY_TIMEOUT = 20.0
_VALID_ACTIONS = ('tray', 'exit')


def shell_exe_path(*roots):
    """نخستین مسیری که Shell EXE در آن هست؛ None یعنی نصب/بیلد نشده."""
    for root in roots:
        if not root:
            continue
        p = os.path.join(root, SHELL_EXE)
        if os.path.isfile(p):
            return p
    return None


def settings_path(root):
    return os.path.join(root, 'shell_settings.json')


def read_close_action(path):
    """'tray' یا 'exit'؛ فایلِ خراب/مقدارِ ناشناخته ⇒ 'exit'."""
    try:
        with open(path, encoding='utf-8') as f:
            value = json.load(f).get('close_action')
        return value if value in _VALID_ACTIONS else 'exit'
    except Exception:
        return 'exit'


def write_close_action(path, action):
    action = action if action in _VALID_ACTIONS else 'exit'
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'version': 1, 'close_action': action},
                      f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f'[shell] cannot write settings ({e})')
        return False


def ask_close_action(path, ask=True):
    """نخستین اجرا: خروج یا Tray. انتخاب در فایل می‌ماند؛ تا تغییرِ Tray."""
    if os.path.isfile(path):
        return read_close_action(path)
    if not ask:
        write_close_action(path, 'exit')
        return 'exit'
    action = 'exit'
    try:
        import ctypes
        mb_yesno, mb_icon, mb_front = 0x4, 0x20, 0x10000
        msg = (
            'بستنِ پنجره چه معنایی داشته باشد؟\n\n'
            'بله: انتقال به System Tray — دریافتِ بازار و وضعیتِ اتصال ادامه می‌یابد.\n'
            'خیر: خروجِ کامل.\n\n'
            'این انتخاب بعداً از منویِ Tray قابلِ تغییر است.'
        )
        result = ctypes.windll.user32.MessageBoxW(
            0, msg, 'BorsTerminal — رفتارِ بستنِ پنجره',
            mb_yesno | mb_icon | mb_front)
        action = 'tray' if result == 6 else 'exit'   # IDYES = 6
    except Exception as e:
        print(f'[shell] close dialog failed ({e}) -> exit')
    write_close_action(path, action)
    return action
