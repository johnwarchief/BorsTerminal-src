#define AppName "BorsTerminal Ultimate"
; AppVersion can be overridden from the command line (ISCC /DAppVersion=x.y.z,
; used by CI so the release tag and the built filename always agree). Because a
; bare #define always wins over a command-line define, guard it with #ifndef and
; keep the default in sync with bors_config.APP_VERSION for local builds.
#ifndef AppVersion
#define AppVersion "1.0.20"
#endif
#define AppPublisher "BorsTerminal"
#define AppExe "BorsTerminal_Ultimate.exe"
; کلیدِ Uninstall در رجیستری (AppId بدون کروشه‌های اضافی + پسوند _is1) —
; برای تشخیصِ نصبِ قبلی در بخشِ [Code].
#define AppRegID "{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1"
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
; v1.0.10: اعمال‌کنندهٔ پچ دلتا. باید قبل از رسیدنِ هر پچ روی دیسک باشد تا
; آپدیتِرِ درون‌برنامه‌ای بتواند آن را spawn کند. این فایل خودش را در %TEMP%
; کپی می‌کند تا بتواند رویِ خودش را بازنویسی کند (phase2).
Source: "..\scripts\apply_update.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; آپدیتِ درون‌برنامه‌ای نصب را با /VERYSILENT اجرا می‌کند. در حالتِ سایلنت
; skipifsilent جلوی اجرای برنامه را می‌گرفت و نسخهٔ جدید بالا نمی‌آمد؛
; nowait یعنی Inno منتظرِ بسته‌شدنِ برنامه نمی‌ماند.
Filename: "{app}\{#AppExe}"; Description: "اجرای {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall

[InstallDelete]
; پاک‌سازی *پیش از* کپیِ فایل‌هایِ جدید. ریشه: Inno فقط فایل‌هایِ Listِ نصبِ
; خودش را بازنویسی/حذف می‌کند؛ اگر نسخهٔ جدید ماژولی را دیگر نیاورد، فایلِ
; .pyd/.dllِ کهنه در _internal می‌ماند و باندلِ فریزشده را می‌شکاند (یک
; آپدیتِ درجا، بیلدِ مخلوط). همین را حذفِ برنامه هم نشان داد: بعد از
; Uninstall پوشهٔ _internal با ده‌ها فایلِ Runtime-added روی دیسک ماند.
; market.db عمداً در این فهرست نیست: مرحلهٔ cumulative همان را می‌خواند تا
; جدول‌هایِ کاربر را به دیتابیسِ تازه منتقل کند.
Type: filesandordirs; Name: "{app}\_internal"

[UninstallDelete]
; --- محصولِ اجرا، نه فایلِ نصب ---
; market.dbِ استخراج‌شده ~۱۰۰ مگابایت است و با هر نسخهٔ باندل عوض می‌شود؛
; archivelِ .stale و .part هم بی‌ارنده. Inno فقط فایل‌هایِ Listِ نصب را پاک
; می‌کند، پس این‌ها باید صریحlisted شوند وگرنه بعد از حذفِ برنامه روی دیسک
; می‌مانند (همان «باقی‌مانده»ای که کاربر شکایت کرد).
Type: files; Name: "{app}\market.db"
Type: files; Name: "{app}\market.db-wal"
Type: files; Name: "{app}\market.db-shm"
Type: files; Name: "{app}\market.db.lzma"
Type: files; Name: "{app}\market.db.baseline"
Type: files; Name: "{app}\market.db.stale"
Type: files; Name: "{app}\market.db.stale-wal"
Type: files; Name: "{app}\market.db.stale-shm"
Type: files; Name: "{app}\codal.db"
Type: files; Name: "{app}\*.db.part"
; `-wal` و `-shm`ِ فایلِ موقتِ استخراج هم باید بروند: تستِ واقعی نشان داد
; market.db.part-shm/-wal بعد از حذف روی دیسک می‌مانند.
Type: files; Name: "{app}\market.db.part*"
Type: files; Name: "{app}\codal.db.part*"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\backups"
Type: filesandordirs; Name: "{app}\__pycache__"
; --- باقی‌مانده‌هایی که یک حذفِ واقعی روی دیسک نگه داشت (شواهدِ v1.0.19) ---
; کشِ اسکرینر و وضعیتِ سینک/کدال هنگامِ اجرا نوشته می‌شوند؛ فایل‌هایِ Listِ
; نصب نیستند، پس بدونِ این خطوط Inno آن‌ها و پوشهٔ _internal (پیای‌تُن در
; زمانِ اجرا .pyc می‌سازد) را بی‌صدا رها می‌کند.
Type: files; Name: "{app}\.screener_cache.json"
Type: files; Name: "{app}\codal_control.json"
Type: files; Name: "{app}\codal_db_status.json"
Type: files; Name: "{app}\market_sync.json"
Type: files; Name: "{app}\sync_summary.json"
Type: filesandordirs; Name: "{app}\_internal"
; --- ریشهٔ دومِ داده: %LOCALAPPDATA%\BorsTerminal_Ultimate\data ---
; وقتی پوشهٔ نصب نوشتنی نباشد (نصبِ «برای همهٔ کاربران» در Program Files) کلِ
; داده‌ها به اینجا منتقل می‌شود؛ حذفِ برنامه بدونِ این خطوط همان ~۱۰۰ مگابایت
; را بی‌صدا روی دیسک نگه می‌داشت.
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db-wal"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db-shm"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db.lzma"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db.baseline"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db.stale"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db.stale-wal"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market.db.stale-shm"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\codal.db"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\*.db.part"
Type: filesandordirs; Name: "{localappdata}\BorsTerminal_Ultimate\data\logs"
Type: filesandordirs; Name: "{localappdata}\BorsTerminal_Ultimate\data\backups"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\.screener_cache.json"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\codal_control.json"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\codal_db_status.json"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\market_sync.json"
Type: files; Name: "{localappdata}\BorsTerminal_Ultimate\data\sync_summary.json"
; نکته: user.db (واچ‌لیست و تصمیم‌های کاربر) و fts_thresholds.json (آستانه‌هایی
; که خودش در پنل چیده) هرگز در این فهرست نیستند — آن‌ها نوشتهٔ کاربرند، نه
; باقی‌ماندهٔ برنامه.

; ===========================================================================
; حالتِ تعمیر / حذف-و-نصبِ مجدد
; ===========================================================================
; وقتی نسخهٔ قبلی نصب است، یک صفحهٔ انتخاب به کاربر نشان داده می‌شود:
;   ۱) نصبِ مجدد / تعمیر فایلها در همان مسیر        (پیش‌فرض)
;   ۲) نصبِ مجدد + بازنشانی دیتابیس بازار
;   ۳) حذفِ کامل برنامه و نصبِ دوباره از صفر
;   ۴) فقط حذفِ کامل برنامه (بدون نصبِ دوباره)
;
; توجه: آپدیتِ درون‌برنامه‌ای با /VERYSILENT اجرا می‌شود و WizardSilent() است،
; پس هیچ‌کدام از این صفحات ساخته نمی‌شوند و مسیرِ ارتقای سایلنت دست‌نخورده
; می‌ماند. این حالت فقط نصبِ تعاملی (دابل‌کلیک روی setup.exe) را تغییر می‌دهد.
[Code]
var
  MaintenancePage: TInputOptionWizardPage;

const
  UNINST_KEY = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#AppRegID}';

// آیا نصبِ قبلی وجود دارد و مسیرش روی دیسک سالم است؟
function PriorInstallLocation(var Dir: String): Boolean;
begin
  Result := RegQueryStringValue(HKCU, UNINST_KEY, 'InstallLocation', Dir);
  if not Result then
    Result := RegQueryStringValue(HKLM, UNINST_KEY, 'InstallLocation', Dir);
  if Result and not DirExists(Dir) then
    Result := False;
end;

procedure InitializeWizard();
var
  PriorDir: String;
begin
  MaintenancePage := nil;
  // در نصبِ سایلنت (آپدیتِ خودکار) هیچ صفحه‌ای نشان داده نمی‌شود.
  if WizardSilent() then
    Exit;
  if not PriorInstallLocation(PriorDir) then
    Exit;

  MaintenancePage := CreateInputOptionPage(wpWelcome,
    'تعمیر یا نصبِ مجدد',
    'نسخهٔ قبلی برنامه در این مسیر نصب شده است:' + #13#10 + PriorDir,
    'می‌خواهید چه کاری انجام شود؟', False, False);
  MaintenancePage.Add('نصبِ مجدد / تعمیر فایلها در همان مسیر (توصیه‌شده)');
  MaintenancePage.Add('نصبِ مجدد + بازنشانی دیتابیس بازار');
  MaintenancePage.Add('حذفِ کامل برنامه و نصبِ دوباره از صفر');
  MaintenancePage.Add('فقط حذفِ کامل برنامه (بدون نصبِ دوباره)');
  MaintenancePage.Values[0] := True;
end;

function SelectedMaintenance: Integer;
var
  I: Integer;
begin
  Result := -1;
  if MaintenancePage = nil then
    Exit;
  for I := 0 to MaintenancePage.CheckListBox.Items.Count - 1 do
    if MaintenancePage.Values[I] then
    begin
      Result := I;
      Break;
    end;
end;

// اگر برنامه در حالِ اجرا باشد uninstall نمی‌تواند فایلها را پاک کند.
procedure EnsureAppNotRunning();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'), '/C "taskkill /F /IM {#AppExe} >NUL 2>NUL"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

// باقی‌ماندهٔ نصب‌هایِ قدیمی را پاک می‌کند: پوشه‌ای که نامش شبیهِ برنامه است و
// فایلِ EXE یا market.dbِ بزرگ دارد ولی unins000.exe ندارد — یعنی نصابش حذف
// شده یا هرگز درست نصب نشده بوده. نصبِ سالم (ثبت‌شده در رجیستری) همیشه
// unins000.exe دارد، پس این شرط هرگز به نصبِ فعلی دست نمی‌زند.
// user.db هیچ‌جا حذف نمی‌شود: نوشتهٔ خودِ کاربر است.
function SweepOrphanLeftovers(): Boolean;
var
  FindRec: TFindRec;
  Roots: TArrayOfString;
  Base, Dir, ExePath, UninstPath: String;
  I, Killed: Integer;
  HasPayload: Boolean;
begin
  Result := True;
  SetArrayLength(Roots, 3);
  Roots[0] := ExpandConstant('{autopf}');
  Roots[1] := ExpandConstant('{commonpf32}');
  Roots[2] := ExpandConstant('{localappdata}\Programs');
  Killed := 0;
  for I := 0 to GetArrayLength(Roots) - 1 do
  begin
    Base := Roots[I];
    if (Base = '') or not DirExists(Base) then
      Continue;
    if FindFirst(Base + '\*', FindRec) then
    begin
      try
        repeat
          if (FindRec.Name = '.') or (FindRec.Name = '..') then
            Continue;
          Dir := Base + '\' + FindRec.Name;
          if Pos('BorsTerminal', FindRec.Name) = 0 then
            Continue;
          // مسیرِ همان نصبی که داریم رویش کار می‌کنیم هرگز پاک نمی‌شود
          if CompareText(Dir, RemoveBackslashUnlessRoot(
               ExpandConstant('{app}'))) = 0 then
            Continue;
          UninstPath := Dir + '\unins000.exe';
          if FileExists(UninstPath) then
            Continue;                       // نصبِ ثبت‌شده — به آن دست نزن
          ExePath := Dir + '\BorsTerminal_Ultimate.exe';
          HasPayload := FileExists(ExePath) or FileExists(Dir + '\market.db')
                        or FileExists(Dir + '\market.db.lzma');
          if not HasPayload then
            Continue;                       // پوشهٔ بی‌ربطِ همنام
          if DelTree(Dir, True, True, True) then
            Killed := Killed + 1;
        until not FindNext(FindRec);
      finally
        FindClose(FindRec);
      end;
    end;
  end;
  if Killed > 0 then
    Log(Format('[sweep] %d orphan leftover folder(s) removed', [Killed]));
end;

// unins000.exe را کاملاً سایلنت اجرا می‌کند و موفقیت را برمی‌گرداند.
function RunFullUninstall: Boolean;
var
  Uninstaller: String;
  ResultCode: Integer;
begin
  Result := False;
  Uninstaller := ExpandConstant('{app}\unins000.exe');
  if not FileExists(Uninstaller) then
    Exit;
  EnsureAppNotRunning();
  if Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

// market.db ای که برنامه در زمانِ اجرا از market.db.lzma استخراج کرده.
procedure DeleteRuntimeDb;
begin
  DeleteFile(ExpandConstant('{app}\market.db'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Choice: Integer;
begin
  Result := '';
  Choice := SelectedMaintenance;
  if Choice < 0 then
    Exit;

  case Choice of
    1:
      DeleteRuntimeDb;
    2:
      begin
        if not RunFullUninstall then
          MsgBox('حذفِ کامل نسخهٔ قبلی ناموفق بود. نصبِ نسخهٔ جدید ادامه می‌یابد.',
            mbError, MB_OK);
        DeleteRuntimeDb;
      end;
    3:
      begin
        if RunFullUninstall then
        begin
          DeleteFile(ExpandConstant('{app}\market.db'));
          DeleteFile(ExpandConstant('{app}\market.db.lzma'));
          // برگرداندنِ متنِ غیرخالی = توقفِ نصب (با یک پیام به کاربر)
          Result := 'برنامه به‌طور کامل حذف شد. نصبِ نسخهٔ جدید لغو شد.';
        end
        else
          Result := 'حذفِ کامل ناموفق بود؛ لطفاً از Settings > Apps ویندوز حذف کنید.';
      end;
  end;
end;
