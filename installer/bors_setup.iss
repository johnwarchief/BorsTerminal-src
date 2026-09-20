#define AppName "BorsTerminal Ultimate"
#define AppVersion "1.0.9"
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
; --- نصبِ پیش‌فرض per-user: بدون نیاز به حقِ مدیر و بدون پنجرهٔ UAC. کاربر در
;     نصبِ تعاملی هنوز می‌تواند «برای همهٔ کاربران» را انتخاب کند (آنگاه UAC
;     می‌آید). وجودِ commandline ضروری است تا آپدیتِ درون‌برنامه‌ای بتواند با
;     /CURRENTUSER یک نصبِ کاملاً سایلنت و بدونِ UAC انجام دهد؛ بدونِ آن، Inno
;     این فلگ را نادیده می‌گیرد و به حالتِ admin (با UAC) برمی‌گردد.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed="dialog commandline"
; --- مسیرِ نصب همیشه از کاربر پرسیده می‌شود، حتی هنگام ارتقا (در نصبِ
;     تعاملی). مقدارِ پیش‌فرضِ صفحه، مسیرِ نصبِ قبلی است (UsePreviousDir).
DisableDirPage=no
UsePreviousAppDir=yes
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
; آپدیتِ درون‌برنامه‌ای نصب را با /VERYSILENT اجرا می‌کند. در حالتِ سایلنت
; skipifsilent جلوی اجرای برنامه را می‌گرفت و نسخهٔ جدید بالا نمی‌آمد؛
; nowait یعنی Inno منتظرِ بسته‌شدنِ برنامه نمی‌ماند.
Filename: "{app}\{#AppExe}"; Description: "اجرای {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\backups"
