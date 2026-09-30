"""Optional local UI smoke check; run against Start-preview.cmd on port 8000."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto("http://127.0.0.1:8000")
        expect(page.get_by_role("heading", name="YouTube is blocked")).to_be_visible(timeout=20000)
        page.screenshot(path=str(ARTIFACTS / "desktop.png"), full_page=True)
        print(page.locator("body").inner_text().encode("ascii", errors="replace").decode(), flush=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(ARTIFACTS / "mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        print("PASS: desktop and mobile render without overflow or JavaScript errors", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
