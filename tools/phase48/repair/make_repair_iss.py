# Phase 4.8 Closeout S5: isolated copy of installer/bors_setup.iss for the
# interactive repair test. The maintenance page and the repair logic are kept
# byte-for-byte; only the parts that could reach the real install, the real
# registry or the real user-data root are redirected or neutralised:
#   - unique test AppId / AppRegID (never the production {8F3A2E7C...})
#   - no password / no encryption (so no auth dialog is automated)
#   - sandbox DefaultDirName and sandboxed former-LocalAppData delete root
#   - [Icons]/[Tasks]/[Run] removed: the test never creates shortcuts and
#     never auto-launches the app (the harness launches it on its own port)
#   - EnsureAppNotRunning / SweepOrphanLeftovers exit before their bodies, so
#     this installer can never taskkill a real app or DelTree a real folder.
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC = os.path.join(ROOT, "installer", "bors_setup.iss")
BASE = os.environ.get("PHASE48_REPAIR_BASE") or os.path.join(
    ROOT, "_audit", "phase48closeout", "repair")
BUNDLE = os.environ.get("PHASE48_REPAIR_BUNDLE") or os.path.join(
    ROOT, "_audit", "phase48closeout", "installer", "bundle")
OUT = os.path.join(BASE, "bors_setup_repairtest.iss")
TEST_APPID = "C3D84F60-2A19-4E7B-8C55-6F9A1B2D3E40"

txt = open(SRC, encoding="utf-8").read()


def one(old, new):
    global txt
    n = txt.count(old)
    if n != 1:
        raise SystemExit("anchor count %d for %r" % (n, old[:80]))
    txt = txt.replace(old, new)


one('#define AppName "BorsTerminal Ultimate"',
    '#define AppName "BorsTerminal Ultimate Phase48 Repair Test"')
one('#define AppRegID "{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1"',
    '#define AppRegID "{%s}_is1"' % TEST_APPID)
one("AppId={{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}",
    "AppId={{%s}" % TEST_APPID)
one('#define BundleDir "..\\dist\\BorsTerminal_Ultimate"',
    '#define BundleDir "%s"\n'
    '#define SetupIcon "%s"' % (
        BUNDLE.replace("\\", "\\\\"),
        os.path.join(ROOT, "assets", "bors.ico").replace("\\", "\\\\")))
one('DefaultDirName={autopf}\\{#AppName}',
    'DefaultDirName={localappdata}\\BorsTerminal_Phase48RepairTest\\app')
one('DisableProgramGroupPage=no', 'DisableProgramGroupPage=yes')
one('OutputDir=out', 'OutputDir=%s' % os.path.join(BASE, "out").replace("\\", "\\\\"))
one('OutputBaseFilename=BorsTerminal_Ultimate_Setup_v{#AppVersion}',
    'OutputBaseFilename=BorsTerminal_RepairTest_Setup_v{#AppVersion}')
one('SetupIconFile=..\\assets\\bors.ico', 'SetupIconFile={#SetupIcon}')
one('MessagesFile: "Farsi.isl"',
    'MessagesFile: "%s"' % os.path.join(ROOT, "installer", "Farsi.isl").replace("\\", "\\\\"))

# No password / no encryption: the repair wizard must be reachable without an
# authentication dialog (and this test must never handle a real secret).
one('#include ".setup_password.iss"\n', '')
one('Password={#SetupPassword}\n', '')
one('Encryption=yes\n', '')

# Keep the production wildcard + market.db rules, but do not carry the 118 MB
# seed in this harness: seed delivery was measured in S2/S3. The repair path
# under test copies program files only.
one('Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "market.db,market.db-wal,market.db-shm,market.db.lzma"',
    'Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "market.db,market.db-wal,market.db-shm,market.db.lzma,market.db.gz"')
one('Source: "{#BundleDir}\\market.db.gz"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist\n', '')
one('Source: "..\\market.db.lzma"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist\n', '')
# apply_update.bat already arrives via the bundle wildcard.
one('Source: "..\\scripts\\apply_update.bat"; DestDir: "{app}"; Flags: ignoreversion\n', '')

# No shortcuts / no post-install launch. The harness starts the repaired exe
# explicitly on an isolated port after checking the files.
one('''[Icons]
Name: "{autoprograms}\\{#AppName}"; Filename: "{app}\\{#AppExe}"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{autodesktop}\\{#AppName}"; Filename: "{app}\\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

''', '')
one('''[Tasks]
Name: "desktopicon"; Description: "ساخت آیکون روی دسکتاپ"; GroupDescription: "آیکون‌های اضافه:"; Flags: checkedonce
Name: "startmenuicon"; Description: "ساخت آیکون در منوی استارت"; GroupDescription: "آیکون‌های اضافه:"; Flags: checkedonce

''', '')
import re
run_re = re.compile(r'Filename: "\{app\}\\\{#AppExe\}";[^\n]*postinstall skipifsilent\n')
txt, n_run = run_re.subn('', txt)
if n_run != 1:
    raise SystemExit("Run entry count %d" % n_run)

# The real user-data root must not appear in this document at all; the test
# install's uninstaller (if ever run) may only delete inside its sandbox.
la_old = "{localappdata}\\BorsTerminal_Ultimate\\data"
n = txt.count(la_old)
if n < 10:
    raise SystemExit("LocalAppData anchor count unexpected: %d" % n)
txt = txt.replace(la_old, "{app}\\_la_sandbox")

# Neutralise the two cross-install helpers. Exit; is valid Pascal and leaves
# the rest of each routine as unreachable code.
one('''procedure EnsureAppNotRunning();
var
  ResultCode: Integer;
begin
''', '''procedure EnsureAppNotRunning();
var
  ResultCode: Integer;
begin
  Exit;
''')
one('''  HasPayload: Boolean;
begin
  Result := True;
''', '''  HasPayload: Boolean;
begin
  Result := True;
  Exit;
''')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8", newline="\n").write(txt)
print("wrote", OUT, "la_entries", n, "bytes", len(txt))
