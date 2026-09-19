#define AppName "BorsTerminal Ultimate"
#define AppVersion "1.0.4"
#define AppPublisher "BorsTerminal"
#define AppExe "BorsTerminal_Ultimate.exe"
; رمز نصب از فایل gitignored خوانده می‌شود تا هرگز وارد ریپو نشود
#include ".setup_password.iss"

[Setup]
AppId={{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=no
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\assets\bors.ico
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
OutputDir=out
OutputBaseFilename=BorsTerminal_Ultimate_Setup_v{#AppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
AllowNoIcons=yes
; --- زبان پیش‌فرض: فارسی. با غیرفعال کردن تشخیص خودکار زبان سیستم، همیشه
;     اولین زبان [Languages] (farsi) پیش‌فرض می‌شود؛ کاربر هنوز می‌تواند
;     انگلیسی را از دیالوگ انتخاب کند ولی پیش‌فرض روی فارسی است.
LanguageDetectionMethod=none
; --- امنیت نصب‌کننده: رمزنگاری کامل payload + درخواست رمز هنگام نصب ---
Password={#SetupPassword}
Encryption=yes

[Languages]
Name: "farsi"; MessagesFile: "Farsi.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "ساخت آیکون روی دسکتاپ"; GroupDescription: "آیکون‌های اضافه:"; Flags: checkedonce
Name: "startmenuicon"; Description: "ساخت آیکون در منوی استارت"; GroupDescription: "آیکون‌های اضافه:"; Flags: checkedonce

[Files]
Source: "..\dist\BorsTerminal_Ultimate\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\market.db.lzma"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "اجرای {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\backups"
