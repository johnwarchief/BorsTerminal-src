# -*- coding: utf-8 -*-
"""
scripts/build_installer_exe.py
================================
تولید پکیج نصبی گرافیکی مستقل ویندوز (.exe) برای ترمینال بورس التیمیت
خروجی نهایی: installer/out/BorsTerminal_Ultimate_Setup_v1.0.0.exe
"""
import os
import sys
import shutil
import zipfile
import subprocess

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate")
OUT_DIR = os.path.join(ROOT, "installer", "out")
RELEASES_DIR = os.path.join(ROOT, "releases")
PAYLOAD_ZIP = os.path.join(ROOT, "build", "installer_payload.zip")
INSTALLER_RUNNER = os.path.join(ROOT, "build", "installer_runner.py")
ICON_PATH = os.path.join(ROOT, "assets", "bors.ico")
VERSION = "1.0.5"

def ensure_payload():
    print("[1/4] بررسی و فشرده‌سازی پکیج اجرایی (dist/BorsTerminal_Ultimate)...")
    if not os.path.exists(os.path.join(DIST_DIR, "BorsTerminal_Ultimate.exe")):
        raise FileNotFoundError(f"فایل اجرایی در {DIST_DIR} یافت نشد. ابتدا بیلد را انجام دهید.")
    
    os.makedirs(os.path.dirname(PAYLOAD_ZIP), exist_ok=True)
    if os.path.exists(PAYLOAD_ZIP):
        os.remove(PAYLOAD_ZIP)

    print("      در حال ایجاد آرشیو فشرده payload.zip ...")
    with zipfile.ZipFile(PAYLOAD_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(DIST_DIR):
            for file in files:
                full = os.path.join(root, file)
                rel = os.path.relpath(full, DIST_DIR)
                # از قرار دادن فایل‌های زائد موقت صرف‌نظر می‌کنیم
                if file.endswith(("-wal", "-shm")):
                    continue
                zf.write(full, rel)
    
    size_mb = os.path.getsize(PAYLOAD_ZIP) / (1024 * 1024)
    print(f"      [✓] فایل فشرده payload آماده شد ({size_mb:.1f} MB).")

def generate_runner_script():
    print("[2/4] ایجاد اسکریپت رانر گرافیکی نصاب (Tkinter Modern GUI)...")
    runner_code = r'''# -*- coding: utf-8 -*-
import os
import sys
import time
import shutil
import zipfile
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
DEFAULT_INSTALL_DIR = os.path.join(LOCALAPPDATA, "Programs", "BorsTerminal_Ultimate")

def is_silent():
    args = [a.lower() for a in sys.argv[1:]]
    return "/s" in args or "--silent" in args or "-s" in args

def create_shortcut(target, lnk_path, icon_path=None, description=""):
    try:
        ps_cmd = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{lnk_path}')
$Shortcut.TargetPath = '{target}'
$Shortcut.WorkingDirectory = '{os.path.dirname(target)}'
$Shortcut.Description = '{description}'
"""
        if icon_path and os.path.exists(icon_path):
            ps_cmd += f"$Shortcut.IconLocation = '{icon_path}'\n"
        ps_cmd += "$Shortcut.Save()\n"
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], capture_output=True)
    except Exception:
        pass

def perform_install(install_dir, create_desktop, create_start, progress_cb=None, status_cb=None):
    base_meipass = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    payload_path = os.path.join(base_meipass, "installer_payload.zip")
    icon_src = os.path.join(base_meipass, "bors.ico")

    if not os.path.exists(payload_path):
        raise FileNotFoundError("بسته فشرده نصاب (payload) یافت نشد.")

    if status_cb: status_cb("در حال بستن نمونه‌های فعال برنامه...", 3)
    try:
        subprocess.run(["taskkill", "/F", "/T", "/IM", "BorsTerminal_Ultimate.exe"], capture_output=True)
        time.sleep(1)
    except Exception:
        pass

    if status_cb: status_cb("در حال آماده‌سازی پوشه نصب...", 5)
    os.makedirs(install_dir, exist_ok=True)

    if status_cb: status_cb("در حال استخراج فایل‌های باینری و کتابخانه‌ها...", 10)
    with zipfile.ZipFile(payload_path, "r") as zf:
        members = zf.namelist()
        total = len(members)
        for i, m in enumerate(members, 1):
            try:
                zf.extract(m, install_dir)
            except PermissionError:
                subprocess.run(["taskkill", "/F", "/T", "/IM", "BorsTerminal_Ultimate.exe"], capture_output=True)
                time.sleep(1)
                try:
                    zf.extract(m, install_dir)
                except Exception:
                    pass
            if (i % 20 == 0 or i == total) and progress_cb:
                pct = 10 + int((i / total) * 65)
                progress_cb(pct, f"استخراج فایل‌ها: {i}/{total} ({pct}%)")

    if status_cb: status_cb("پیکربندی پایگاه داده و آیکون‌ها...", 78)
    target_exe = os.path.join(install_dir, "BorsTerminal_Ultimate.exe")
    target_icon = os.path.join(install_dir, "assets", "bors.ico")
    if os.path.exists(icon_src):
        os.makedirs(os.path.join(install_dir, "assets"), exist_ok=True)
        shutil.copy2(icon_src, target_icon)

    db_file = os.path.join(install_dir, "market.db")
    lzma_file = os.path.join(install_dir, "market.db.lzma")
    if not os.path.exists(db_file) and os.path.exists(lzma_file):
        try:
            import lzma
            with open(lzma_file, "rb") as fi, open(db_file, "wb") as fo:
                fo.write(lzma.decompress(fi.read()))
        except Exception:
            pass

    if status_cb: status_cb("در حال ایجاد میانبرهای سیستم...", 88)
    desk_lnk = ""
    start_menu = ""
    if create_desktop:
        desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.exists(desktop_dir):
            desk_lnk = os.path.join(desktop_dir, "ترمینال بورس التیمیت.lnk")
            create_shortcut(target_exe, desk_lnk, target_icon, "ترمینال بورس التیمیت")

    if create_start:
        start_menu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "BorsTerminal")
        os.makedirs(start_menu, exist_ok=True)
        start_lnk = os.path.join(start_menu, "BorsTerminal Ultimate.lnk")
        create_shortcut(target_exe, start_lnk, target_icon, "BorsTerminal Ultimate")

    # فایل حذف
    try:
        uninstaller_path = os.path.join(install_dir, "uninstall.bat")
        with open(uninstaller_path, "w", encoding="utf-8") as uf:
            uf.write("@echo off\n")
            uf.write("chcp 65001 >nul\n")
            uf.write("echo Removing BorsTerminal shortcuts...\n")
            if desk_lnk: uf.write(f'del /f /q "{desk_lnk}" 2>nul\n')
            if start_menu: uf.write(f'rmdir /s /q "{start_menu}" 2>nul\n')
            uf.write("echo Shortcuts removed successfully.\n")
            uf.write("pause\n")
    except Exception:
        pass

    if status_cb: status_cb("نصب با موفقیت انجام شد.", 100)
    return target_exe

class ModernSetupWizard:
    def __init__(self, root):
        self.root = root
        self.root.title("نصاب ترمینال بورس التیمیت — BorsTerminal Setup v1.0.5")
        self.root.geometry("600x440")
        self.root.minsize(560, 420)
        self.root.configure(bg="#0f172a")

        # آیکون
        base_meipass = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_meipass, "bors.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        # متغیرها
        self.install_dir_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.desktop_var = tk.BooleanVar(value=True)
        self.start_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=True)
        self.installed_exe = ""

        # استایل‌ها
        self.setup_styles()

        # کانتینر اصلی
        self.main_container = tk.Frame(self.root, bg="#0f172a")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # هدر
        self.create_header()

        # بدنه
        self.body_frame = tk.Frame(self.main_container, bg="#1e293b", padx=24, pady=20)
        self.body_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        # ساخت صفحات
        self.show_step_1()

        # مرکز کردن پنجره
        self.center_window()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TProgressbar", thickness=16, troughcolor="#334155", background="#2563eb")

    def center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def create_header(self):
        header = tk.Frame(self.main_container, bg="#0f172a", padx=20, pady=14)
        header.pack(fill=tk.X)

        title = tk.Label(
            header,
            text="ترمینال بورس التیمیت — سامانه داوری نخبگان",
            font=("Segoe UI", 12, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
            anchor="e"
        )
        title.pack(fill=tk.X)

        subtitle = tk.Label(
            header,
            text="BorsTerminal Ultimate Official Windows Setup v1.0.5",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a",
            anchor="e"
        )
        subtitle.pack(fill=tk.X)

    def clear_body(self):
        for widget in self.body_frame.winfo_children():
            widget.destroy()

    def show_step_1(self):
        self.clear_body()

        lbl_intro = tk.Label(
            self.body_frame,
            text="به برنامه نصب رسمی ترمینال بورس التیمیت خوش آمدید.\nلطفاً مسیر نصب برنامه را تأیید یا انتخاب کنید:",
            font=("Segoe UI", 10),
            fg="#e2e8f0",
            bg="#1e293b",
            justify="right",
            anchor="e"
        )
        lbl_intro.pack(fill=tk.X, pady=(0, 14))

        # انتخاب مسیر
        dir_frame = tk.Frame(self.body_frame, bg="#1e293b")
        dir_frame.pack(fill=tk.X, pady=6)

        btn_browse = tk.Button(
            dir_frame,
            text="انتخاب...",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#334155",
            activebackground="#475569",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.browse_folder
        )
        btn_browse.pack(side=tk.LEFT, padx=(0, 8))

        entry_dir = tk.Entry(
            dir_frame,
            textvariable=self.install_dir_var,
            font=("Segoe UI", 9),
            fg="#f8fafc",
            bg="#0f172a",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#475569",
            highlightcolor="#38bdf8"
        )
        entry_dir.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # گزینه‌ها
        opts_frame = tk.Frame(self.body_frame, bg="#1e293b")
        opts_frame.pack(fill=tk.X, pady=(16, 8))

        chk_desk = tk.Checkbutton(
            opts_frame,
            text="ایجاد میانبر روی دسکتاپ (Desktop Shortcut)",
            variable=self.desktop_var,
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#1e293b",
            activebackground="#1e293b",
            activeforeground="#ffffff",
            selectcolor="#0f172a",
            anchor="e"
        )
        chk_desk.pack(fill=tk.X, pady=3)

        chk_start = tk.Checkbutton(
            opts_frame,
            text="ایجاد در منوی استارت ویندوز (Start Menu)",
            variable=self.start_var,
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#1e293b",
            activebackground="#1e293b",
            activeforeground="#ffffff",
            selectcolor="#0f172a",
            anchor="e"
        )
        chk_start.pack(fill=tk.X, pady=3)

        # فوتر دکمه‌ها
        btn_frame = tk.Frame(self.body_frame, bg="#1e293b")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(16, 0))

        btn_cancel = tk.Button(
            btn_frame,
            text="انصراف",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1e293b",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.root.quit
        )
        btn_cancel.pack(side=tk.LEFT)

        btn_install = tk.Button(
            btn_frame,
            text="شروع نصب برنامه",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg="#2563eb",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
            command=self.start_install_thread
        )
        btn_install.pack(side=tk.RIGHT)

    def browse_folder(self):
        sel = filedialog.askdirectory(initialdir=self.install_dir_var.get(), title="انتخاب پوشه نصب")
        if sel:
            self.install_dir_var.set(os.path.normpath(sel))

    def show_step_2(self):
        self.clear_body()

        lbl_wait = tk.Label(
            self.body_frame,
            text="در حال استقرار ترمینال بورس التیمیت...",
            font=("Segoe UI", 11, "bold"),
            fg="#f8fafc",
            bg="#1e293b",
            anchor="e"
        )
        lbl_wait.pack(fill=tk.X, pady=(10, 8))

        self.lbl_status = tk.Label(
            self.body_frame,
            text="آماده‌سازی...",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#1e293b",
            anchor="e"
        )
        self.lbl_status.pack(fill=tk.X, pady=(0, 16))

        self.prog_bar = ttk.Progressbar(self.body_frame, style="TProgressbar", mode="determinate")
        self.prog_bar.pack(fill=tk.X, pady=8)
        self.prog_bar["value"] = 5

        self.lbl_detail = tk.Label(
            self.body_frame,
            text="",
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#1e293b",
            anchor="e"
        )
        self.lbl_detail.pack(fill=tk.X, pady=4)

    def start_install_thread(self):
        target_dir = self.install_dir_var.get().strip()
        if not target_dir:
            messagebox.showwarning("خطا", "لطفاً مسیر نصب معتبری را انتخاب کنید.")
            return

        self.show_step_2()

        def _worker():
            try:
                def on_prog(pct, msg):
                    self.root.after(0, lambda: self._update_prog(pct, msg))

                def on_status(msg, pct):
                    self.root.after(0, lambda: self._update_status(msg, pct))

                exe = perform_install(
                    target_dir,
                    self.desktop_var.get(),
                    self.start_var.get(),
                    progress_cb=on_prog,
                    status_cb=on_status
                )
                self.installed_exe = exe
                self.root.after(200, self.show_step_3)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("خطای نصب", f"نصب با خطا مواجه شد:\n{e}"))
                self.root.after(0, self.show_step_1)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _update_prog(self, pct, msg):
        self.prog_bar["value"] = pct
        self.lbl_detail.config(text=msg)

    def _update_status(self, msg, pct):
        self.lbl_status.config(text=msg)
        self.prog_bar["value"] = pct

    def show_step_3(self):
        self.clear_body()

        lbl_success = tk.Label(
            self.body_frame,
            text="✓ نصب با موفقیت کامل انجام شد!",
            font=("Segoe UI", 12, "bold"),
            fg="#4ade80",
            bg="#1e293b",
            anchor="e"
        )
        lbl_success.pack(fill=tk.X, pady=(10, 6))

        lbl_msg = tk.Label(
            self.body_frame,
            text=f"ترمینال بورس التیمیت در مسیر زیر نصب گردید:\n{self.install_dir_var.get()}\n\nمیانبرهای دسترسی با موفقیت ساخته شدند.",
            font=("Segoe UI", 9),
            fg="#e2e8f0",
            bg="#1e293b",
            justify="right",
            anchor="e"
        )
        lbl_msg.pack(fill=tk.X, pady=(0, 16))

        chk_launch = tk.Checkbutton(
            self.body_frame,
            text="اجرای ترمینال بورس التیمیت پس از خروج",
            variable=self.launch_var,
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#1e293b",
            activebackground="#1e293b",
            activeforeground="#38bdf8",
            selectcolor="#0f172a",
            anchor="e"
        )
        chk_launch.pack(fill=tk.X, pady=8)

        btn_frame = tk.Frame(self.body_frame, bg="#1e293b")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(16, 0))

        btn_finish = tk.Button(
            btn_frame,
            text="پایان و خروج",
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg="#2563eb",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=24,
            pady=6,
            cursor="hand2",
            command=self.finish_install
        )
        btn_finish.pack(side=tk.RIGHT)

    def finish_install(self):
        if self.launch_var.get() and self.installed_exe and os.path.exists(self.installed_exe):
            install_dir = os.path.dirname(self.installed_exe)
            subprocess.Popen([self.installed_exe], cwd=install_dir, shell=True)
        self.root.quit()

def main():
    if is_silent():
        perform_install(DEFAULT_INSTALL_DIR, True, True)
        sys.exit(0)

    root = tk.Tk()
    app = ModernSetupWizard(root)
    root.mainloop()

if __name__ == "__main__":
    main()
'''
    with open(INSTALLER_RUNNER, "w", encoding="utf-8") as f:
        f.write(runner_code)
    print("      [✓] اسکریپت نصاب با رابط گرافیکی ایجاد شد.")

def build_setup_exe():
    # GUARD: the canonical Windows installer is the Inno Setup build produced by
    # `release.ps1 setup` (installer/bors_setup.iss), which writes to
    # installer/out/BorsTerminal_Ultimate_Setup_v{VERSION}.exe. This legacy
    # PyInstaller/Tkinter pseudo-installer used to write to THAT EXACT SAME PATH
    # and silently replaced the real installer (the v1.0.5 regression). It must
    # never collide with the Inno output again, so it is disabled by default and
    # writes to a distinctly-named file when explicitly enabled.
    if os.environ.get("BORS_ALLOW_LEGACY_PYI_INSTALLER") != "1":
        print(
            "\n[-] این اسکریپت دیگر نصاب رسمی نیست و به‌صورت پیش‌فرض غیرفعال است.\n"
            "    نصب رسمی توسط Inno Setup و از طریق `release.ps1 setup` ساخته می‌شود\n"
            "    (خروجی: installer/out/BorsTerminal_Ultimate_Setup_v%s.exe).\n"
            "    این اسکریپتِ PyInstaller در گذشته همان مسیر را بازنویسی می‌کرد و\n"
            "    نصاب واقعی را خراب می‌کرد (علتِ باگِ v1.0.5).\n"
            "    در صورت نیاز به ساخت نسخهٔ گرافیکی قدیمی، متغیر محیطی\n"
            "    BORS_ALLOW_LEGACY_PYI_INSTALLER=1 را تنظیم کنید (خروجی با پیشوند\n"
            "    legacy_pyi_ ذخیره می‌شود تا با خروجیِ Inno تداخلی نداشته باشد)." % VERSION
        )
        sys.exit(2)

    # legacy prefix keeps this well away from the canonical Inno artifact
    SETUP_NAME = f"legacy_pyi_BorsTerminal_Ultimate_Setup_v{VERSION}"
    print("[3/4] کامپایل نصاب گرافیکی مستقل با PyInstaller (--windowed)...")
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(RELEASES_DIR, exist_ok=True)

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", SETUP_NAME,
        "--add-data", f"{PAYLOAD_ZIP};.",
        "--add-data", f"{ICON_PATH};.",
        "--icon", ICON_PATH,
        "--distpath", OUT_DIR,
        "--workpath", os.path.join(ROOT, "build", "installer_build"),
        INSTALLER_RUNNER
    ]

    print("      اجرای دستور کامپایل:")
    print("      " + " ".join(cmd))
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        raise RuntimeError("کامپایل نصاب با خطا مواجه شد.")
    
    out_exe = os.path.join(OUT_DIR, f"{SETUP_NAME}.exe")
    rel_exe = os.path.join(RELEASES_DIR, f"{SETUP_NAME}.exe")
    if os.path.exists(out_exe):
        shutil.copy2(out_exe, rel_exe)
        size_mb = os.path.getsize(out_exe) / (1024 * 1024)
        print(f"\n[4/4] [SUCCESS] فایل نصاب گرافیکی با موفقیت ساخته شد!")
        print(f"      مسیر نصاب ۱: {out_exe} ({size_mb:.1f} MB)")
        print(f"      مسیر نصاب ۲ (ریلیزها): {rel_exe}")

if __name__ == "__main__":
    # Fail fast: refuse to run (and refuse to create any build artifacts) unless
    # explicitly enabled. See the note in build_setup_exe() for why this script
    # is no longer the canonical installer path.
    if os.environ.get("BORS_ALLOW_LEGACY_PYI_INSTALLER") != "1":
        print(
            "\n[-] این اسکریپت دیگر نصاب رسمی نیست و به‌صورت پیش‌فرض غیرفعال است.\n"
            "    نصب رسمی توسط Inno Setup و از طریق `release.ps1 setup` ساخته می‌شود\n"
            "    (خروجی: installer/out/BorsTerminal_Ultimate_Setup_v%s.exe).\n"
            "    این اسکریپتِ PyInstaller در گذشته همان مسیر را بازنویسی می‌کرد و\n"
            "    نصاب واقعی را خراب می‌کرد (علتِ باگِ v1.0.5).\n"
            "    در صورت نیاز به ساخت نسخهٔ گرافیکی قدیمی، متغیر محیطی\n"
            "    BORS_ALLOW_LEGACY_PYI_INSTALLER=1 را تنظیم کنید (خروجی با پیشوند\n"
            "    legacy_pyi_ ذخیره می‌شود تا با خروجیِ Inno تداخلی نداشته باشد)." % VERSION
        )
        sys.exit(2)
    try:
        ensure_payload()
        generate_runner_script()
        build_setup_exe()
    except Exception as e:
        print(f"\n[-] خطا در ساخت نصاب: {e}")
        sys.exit(1)
