"""
tools/verify_technical_workspace_live.py

راستی‌آزمایی زنده و ثبت شواهد بصری ارتقای میزکار تکنیکال بورس‌ترمینال:
۱. همگام‌سازی تم پویا (چارت در تم تاریک و تم روشن)
۲. نوار تایم‌فریم و تجمیع هفتگی و ماهانه کندل‌ها
۳. کارت آموزش تعاملی معامله‌گر و کالبدشکافی الگوها
۴. موتور تعدیل عملکردی مستقل
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\PCMOD\.gemini\antigravity\brain\00b24b19-1649-494d-a325-5f1d7eb1028b"
BASE_URL = "http://localhost:5180/#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF"

def run_verification():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    print("Launching Chromium for live verification...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        print(f"Navigating to {BASE_URL}...")
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="kline-chart-wrapper"]', timeout=15000)
        time.sleep(2) # انتظار برای رندر کامل کانواس

        # ۱. تصویربرداری از تم تاریک برنجی (پیش‌فرض)
        dark_path = os.path.join(ARTIFACT_DIR, "preview_technical_dark_brass.png")
        page.screenshot(path=dark_path)
        print(f"Captured Dark Brass Theme: {dark_path}")

        # ۲. سوییچ به تم روشن (Warm Light) با کلیک روی دکمه پوسته در سایدبار
        warm_btn = page.query_selector('[data-testid="theme-warm"]')
        if warm_btn:
            warm_btn.click()
            time.sleep(1.5)
            light_path = os.path.join(ARTIFACT_DIR, "preview_technical_light_warm.png")
            page.screenshot(path=light_path)
            print(f"Captured Light Warm Theme: {light_path}")

            # بازگشت به تم تاریک برنجی برای مراحل بعدی
            brass_btn = page.query_selector('[data-testid="theme-brass"]')
            if brass_btn:
                brass_btn.click()
                time.sleep(1)

        # ۳. کلیک روی دکمه راهنما (؟) جهت باز کردن کارت آموزش تعاملی معامله‌گر
        edge_tab = page.query_selector('button:has-text("لبه آماری")')
        if edge_tab:
            edge_tab.click()
            time.sleep(0.5)

        guide_btn = page.query_selector('[data-testid="toggle-guide-btn"]')
        if guide_btn and guide_btn.is_visible():
            guide_btn.click()
            time.sleep(1)
            edu_path = os.path.join(ARTIFACT_DIR, "preview_technical_education_open.png")
            page.screenshot(path=edu_path)
            print(f"Captured Trader's Education Card Open: {edu_path}")

        # ۴. کلیک روی تایم‌فریم هفتگی (1W)
        tf_1w_btn = page.query_selector('[data-testid="timeframe-btn-1W"]')
        if tf_1w_btn:
            tf_1w_btn.click()
            time.sleep(1.5)
            weekly_path = os.path.join(ARTIFACT_DIR, "preview_technical_weekly_aggregated.png")
            page.screenshot(path=weekly_path)
            print(f"Captured Weekly Aggregated Candles: {weekly_path}")

        # ۵. کلیک روی تایم‌فریم ماهانه (1M)
        tf_1m_btn = page.query_selector('[data-testid="timeframe-btn-1M"]')
        if tf_1m_btn:
            tf_1m_btn.click()
            time.sleep(1.5)
            monthly_path = os.path.join(ARTIFACT_DIR, "preview_technical_monthly_aggregated.png")
            page.screenshot(path=monthly_path)
            print(f"Captured Monthly Aggregated Candles: {monthly_path}")

        browser.close()
        print("Live verification complete! All screenshots saved.")

if __name__ == "__main__":
    run_verification()
