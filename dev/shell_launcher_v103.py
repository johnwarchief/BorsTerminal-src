#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/shell_launcher_v103.py — قراردادِ پوستهٔ Tauri در منبع و باندل.

چرا: پنجرهٔ تازه سه راهِ شکستِ بی‌صدا دارد: فراموش‌شدنِ fallback به pywebview،
از‌دست‌رفتنِ پروفایلِ تنظیمات، و جاافتادنِ EXE در باندل/نصب. این گارد هر سه را
می‌سنجد. `--dist` وجود و اندازهٔ EXE را هم چک می‌کند.
"""
import argparse
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import bors_shell  # noqa: E402

FAILS = []


def ck(label, cond):
    print(('  ok   ' if cond else '  FAIL ') + label)
    if not cond:
        FAILS.append(label)


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dist', default='')
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix='bors_shell_guard_') as d:
        p = os.path.join(d, 'shell_settings.json')
        ck('missing settings -> exit', bors_shell.read_close_action(p) == 'exit')
        ck('ask disabled writes exit',
           bors_shell.ask_close_action(p, ask=False) == 'exit')
        ck('exit persisted', bors_shell.read_close_action(p) == 'exit')
        ck('tray write/read',
           bors_shell.write_close_action(p, 'tray')
           and bors_shell.read_close_action(p) == 'tray')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('{broken')
        ck('broken settings -> exit', bors_shell.read_close_action(p) == 'exit')
        ck('exe missing -> None', bors_shell.shell_exe_path(d) is None)
        fake = os.path.join(d, bors_shell.SHELL_EXE)
        open(fake, 'wb').close()
        ck('exe found', bors_shell.shell_exe_path(d) == fake)
        ck('ready timeout bounded', 0 < bors_shell.SHELL_READY_TIMEOUT <= 30)

    src = read('bors_entry.py')
    ck('launcher uses bors_shell',
       'import bors_shell' in src and '_open_shell_window' in src)
    ck('shell tried before pywebview',
       src.index('_open_shell_window(url)') < src.index('import webview'))
    ck('pywebview fallback intact', 'webview.start(**kwargs)' in src)
    ck('shell switch env', 'BORS_SHELL' in src)

    conf = json.loads(read('frontend/src-tauri/tauri.conf.json'))
    ck('no default window', conf.get('app', {}).get('windows') == [])
    ck('stub frontendDist',
       conf.get('build', {}).get('frontendDist') == 'shell-dist')
    ck('csp is not null',
       conf.get('app', {}).get('security', {}).get('csp') is not None)

    cargo = read('frontend/src-tauri/Cargo.toml')
    ck('tauri pinned 2.12.5', 'version = "=2.12.5"' in cargo)
    ck('tray feature enabled', 'features = ["tray-icon"]' in cargo)
    ck('shell binary name', 'name = "BorsTerminal_Shell"' in cargo)

    iss = read('installer/bors_setup.iss')
    ck('installer knows shell',
       '{#ShellExe}' in iss and 'BorsTerminal_Shell.exe' in iss)
    upd = read('api/update.py')
    ck('updater waits for shell',
       'SHELL_EXE' in upd and ':waitshell' in upd)

    if args.dist:
        exe = os.path.join(args.dist, bors_shell.SHELL_EXE)
        exists = os.path.isfile(exe)
        ck('shell in bundle', exists)
        if exists:
            mb = os.path.getsize(exe) / 1e6
            ck(f'shell size sane ({mb:.2f} MB)', 5 <= mb <= 25)
        ck('python exe in bundle',
           os.path.isfile(os.path.join(args.dist, 'BorsTerminal_Ultimate.exe')))

    print(f'\n{len(FAILS)} failed')
    print('SHELL LAUNCHER GUARD ' + ('OK' if not FAILS else 'FAILED'))
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
