import os
import sys
from playwright.sync_api import sync_playwright

def main():
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    out_dir = r"C:\Users\PCMOD\.gemini\antigravity\brain\00b24b19-1649-494d-a325-5f1d7eb1028b"
    os.makedirs(out_dir, exist_ok=True)

    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    browser_exe = edge_path if os.path.exists(edge_path) else brave_path

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=browser_exe, headless=True)
        context = browser.new_context(
            viewport={"width": 1680, "height": 980},
            device_scale_factor=1.25,
        )
        page = context.new_page()

        print("Navigating to Technical Workspace...")
        page.goto("http://127.0.0.1:5180/#/technical/فولاد", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # 1. Capture clean chart (default state: SMC off, no forced indicators)
        clean_shot = os.path.join(out_dir, "preview_clean_chart_default.png")
        page.screenshot(path=clean_shot)
        print(f"Captured clean chart: {clean_shot}")

        # 2. Open the Indicators Dropdown in top toolbar
        try:
            drop_btn = page.locator("[data-testid='indicator-dropdown-btn']").first
            if drop_btn.is_visible():
                print("Opening Indicator Dropdown...")
                drop_btn.click()
                page.wait_for_timeout(1000)
                drop_shot = os.path.join(out_dir, "preview_indicator_dropdown_open.png")
                page.screenshot(path=drop_shot)
                print(f"Captured indicator dropdown: {drop_shot}")
        except Exception as e:
            print(f"Error opening indicator dropdown: {e}")

        # 3. Open the left drawer (Wide Workspace Drawer with 50 top symbols, signals column, asset filter)
        try:
            # Click the top50 icon on slim activity bar
            top50_icon = page.locator("[data-testid='activity-item-top50']").first
            if top50_icon.is_visible():
                print("Opening Top 50 drawer...")
                top50_icon.click()
                page.wait_for_timeout(1500)
                drawer_shot = os.path.join(out_dir, "preview_top50_signals_drawer.png")
                page.screenshot(path=drawer_shot)
                print(f"Captured top 50 drawer: {drawer_shot}")
        except Exception as e:
            print(f"Error opening drawer: {e}")

        # 4. Switch to light theme to verify contrast
        try:
            light_toggle = page.locator("[data-testid='theme-toggle']").first
            if light_toggle.is_visible():
                print("Toggling light theme...")
                light_toggle.click()
                page.wait_for_timeout(1500)
                light_shot = os.path.join(out_dir, "preview_light_theme_indicators.png")
                page.screenshot(path=light_shot)
                print(f"Captured light theme: {light_shot}")
        except Exception as e:
            print(f"Error toggling theme: {e}")

        browser.close()
        print("Done capturing final UI previews.")

if __name__ == '__main__':
    main()
