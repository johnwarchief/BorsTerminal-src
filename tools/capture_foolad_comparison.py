import sys
import os
import time
from playwright.sync_api import sync_playwright

def main():
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    out_dir = r"C:\Users\PCMOD\.gemini\antigravity\brain\00b24b19-1649-494d-a325-5f1d7eb1028b"
    os.makedirs(out_dir, exist_ok=True)

    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    browser_exe = edge_path if os.path.exists(edge_path) else brave_path

    print(f"Launching browser: {browser_exe}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=browser_exe, headless=True)
        context = browser.new_context(
            viewport={"width": 1680, "height": 980},
            device_scale_factor=1.25,
        )
        page = context.new_page()

        # Capture Technical Workspace for فولاد
        print("Navigating to Technical Workspace (فولاد)...")
        page.goto("http://127.0.0.1:5180/#/technical/فولاد", wait_until="networkidle")
        page.wait_for_timeout(3500)

        # Toggle the prediction cone on
        try:
            cone_btn = page.locator('button[role="switch"]:has-text("کان پیش‌بینی")').first
            if cone_btn.is_visible():
                print("Clicking forecast cone toggle button...")
                cone_btn.click()
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Could not click cone toggle: {e}")

        foolad_shot = os.path.join(out_dir, "preview_technical_foolad_functional.png")
        page.screenshot(path=foolad_shot)
        print(f"Saved: {foolad_shot}")

        # Capture close up of chart canvas with corporate event markers
        try:
            chart_canvas = page.locator("[data-testid='kline-chart-wrapper']").first
            if chart_canvas.is_visible():
                canvas_shot = os.path.join(out_dir, "preview_foolad_chart_detail.png")
                chart_canvas.screenshot(path=canvas_shot)
                print(f"Saved: {canvas_shot}")
        except Exception as e:
            print(f"Could not capture chart detail: {e}")

        browser.close()
        print("Done capturing Foolad comparison.")

if __name__ == "__main__":
    main()
