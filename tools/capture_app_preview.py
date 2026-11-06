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

        # 1. Capture Market Board
        print("Navigating to Market Board...")
        page.goto("http://127.0.0.1:5180/#/market", wait_until="networkidle")
        page.wait_for_timeout(3000)
        market_shot = os.path.join(out_dir, "preview_market_board.png")
        page.screenshot(path=market_shot)
        print(f"Saved: {market_shot}")

        # 2. Capture Technical Workspace for مارون
        print("Navigating to Technical Workspace (مارون)...")
        page.goto("http://127.0.0.1:5180/#/technical/مارون", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Toggle the prediction cone on
        try:
            cone_btn = page.locator('button[role="switch"]:has-text("کان پیش‌بینی")').first
            if cone_btn.is_visible():
                print("Clicking forecast cone toggle button...")
                cone_btn.click()
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Could not click cone toggle: {e}")

        tech_shot = os.path.join(out_dir, "preview_technical_workspace.png")
        page.screenshot(path=tech_shot)
        print(f"Saved: {tech_shot}")

        # 3. Open Drawing Tools Popover to showcase TV-style tools
        try:
            line_tool_btn = page.locator('button[title*="خطوط"]').first
            if line_tool_btn.is_visible():
                print("Opening drawing tools popover...")
                line_tool_btn.click()
                page.wait_for_timeout(1000)
                toolbar_shot = os.path.join(out_dir, "preview_drawing_toolbar.png")
                page.screenshot(path=toolbar_shot)
                print(f"Saved: {toolbar_shot}")
        except Exception as e:
            print(f"Could not open drawing popover: {e}")

        # 4. Capture CandleEdgeCard detail
        try:
            edge_card = page.locator("[data-testid='candle-edge-card']").first
            if edge_card.is_visible():
                edge_shot = os.path.join(out_dir, "preview_candle_edge_card.png")
                edge_card.screenshot(path=edge_shot)
                print(f"Saved: {edge_shot}")
        except Exception as e:
            print(f"Could not capture edge card: {e}")

        # 5. Capture Forecast Controls detail
        try:
            forecast_ctrl = page.locator("[data-testid='forecast-controls']").first
            if forecast_ctrl.is_visible():
                fc_shot = os.path.join(out_dir, "preview_forecast_controls.png")
                forecast_ctrl.screenshot(path=fc_shot)
                print(f"Saved: {fc_shot}")
        except Exception as e:
            print(f"Could not capture forecast controls: {e}")

        browser.close()
        print("Done capturing previews.")

if __name__ == "__main__":
    main()
