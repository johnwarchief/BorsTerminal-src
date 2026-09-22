# -*- coding: utf-8 -*-
"""
scripts/remote_agent_bot.py
===========================
ربات هوشمند مدیریت راه دور BorsTerminal و ارتباط با ایجنت‌ها از طریق تلگرام.
"""
import os
import sys
import sqlite3
import subprocess
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "market.db")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_ID", "")

def check_auth(update: Update) -> bool:
    if not ADMIN_ID:
        return True
    return str(update.effective_user.id) == str(ADMIN_ID)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        await update.message.reply_text("⛔ دسترسی غیرمجاز است.")
        return
    msg = (
        "🤖 **ربات کنترل از راه دور BorsTerminal**\n\n"
        "دستورات موجود:\n"
        "📊 `/status` - وضعیت منابع، دیتابیس و نسخه سیستم\n"
        "📈 `/price <نماد>` - مشاهده آخرین قیمت و حجم (مثال: `/price فولاد`)\n"
        "🔍 `/fts <نماد>` - گزارش بنیادی FTS نماد\n"
        "💻 `/sh <دستور>` - اجرای مستقیم دستور شل در ماشین ابری\n"
        "🧠 `/agent <پرامپت>` - ارسال تسک به ایجنت هوش مصنوعی\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return
    db_status = "❌ دیتابیس یافت نشد"
    row_count = 0
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM daily_prices")
            row_count = c.fetchone()[0]
            conn.close()
            db_status = f"✅ متصل ({row_count:,} رکورد قیمتی)"
        except Exception as e:
            db_status = f"⚠️ خطا: {e}"

    uptime_res = subprocess.run(["uptime"], capture_output=True, text=True)
    df_res = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
    disk_line = df_res.stdout.splitlines()[1] if len(df_res.stdout.splitlines()) > 1 else ""

    text = (
        f"🖥 **وضعیت ماشین ابری BorsTerminal**\n\n"
        f"• دیتابیس: {db_status}\n"
        f"• آپ‌تایم: `{uptime_res.stdout.strip()}`\n"
        f"• فضای دیسک: `{disk_line}`\n"
        f"• دایرکتوری: `{ROOT}`\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return
    if not context.args:
        await update.message.reply_text("لطفاً نماد را وارد کنید. مثال: `/price فولاد`", parse_mode="Markdown")
        return
    symbol = context.args[0].strip()
    if not os.path.exists(DB_PATH):
        await update.message.reply_text("دیتابیس هنوز استخراج نشده است.")
        return
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        c = conn.cursor()
        c.execute("SELECT close, volume, date, high, low FROM daily_prices WHERE symbol=? ORDER BY date DESC LIMIT 1", (symbol,))
        row = c.fetchone()
        conn.close()
        if row:
            close_p, vol, dt, hi, lo = row
            resp = (
                f"📊 **اطلاعات نماد {symbol}**\n"
                f"📅 تاریخ: `{dt}`\n"
                f"💰 قیمت پایانی: `{close_p:,.0f} ریال`\n"
                f"📈 بالاترین / پایین‌ترین: `{hi:,.0f} / {lo:,.0f}`\n"
                f"📦 حجم معاملات: `{vol:,.0f}`\n"
            )
            await update.message.reply_text(resp, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"نماد {symbol} در دیتابیس یافت نشد.")
    except Exception as e:
        await update.message.reply_text(f"خطا در کوئری دیتابیس: {e}")

async def sh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update):
        return
    cmd = " ".join(context.args)
    if not cmd:
        await update.message.reply_text("دستور را بنویسید. مثال: `/sh git status`", parse_mode="Markdown")
        return
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=ROOT)
        out = (res.stdout + "\n" + res.stderr).strip()
        if len(out) > 3800:
            out = out[:3800] + "\n...(خروجی کوتاه شد)..."
        if not out:
            out = "(دستور با موفقیت بدون خروجی اجرا شد)"
        await update.message.reply_text(f"```bash\n{out}\n```", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"خطا در اجرا: {e}")

def main():
    if not BOT_TOKEN:
        print("[-] لطفاً متغیر محیطی TELEGRAM_BOT_TOKEN را ست کنید.")
        sys.exit(1)
    print(f"[+] Starting BorsTerminal Telegram Gateway on {ROOT}...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("price", price_cmd))
    app.add_handler(CommandHandler("sh", sh_cmd))
    app.run_polling()

if __name__ == "__main__":
    main()
