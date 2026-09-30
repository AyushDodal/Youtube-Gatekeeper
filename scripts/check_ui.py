"""Optional browser regression check against the built UI in simulation mode.

API fixtures below belong only to this test. Production assets contain no mocks.
Run with the virtual environment's Python: scripts/check_ui.py
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts"


def now():
    return datetime.now(timezone.utc)


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        initial = page.request.get("http://127.0.0.1:8000/api/status").json()
        assert initial["dry_run"], "Run Start-preview.cmd first; browser checks use simulation only."
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        fixture = {"phase": "blocked", "closed": False, "messages": [], "offline": False}
        session = {"id": "ui-session", "conversation_id": "ui-conversation", "reason": "A focused tutorial", "started_at": now().isoformat(), "expires_at": (now()+timedelta(minutes=5)).isoformat(), "duration_minutes": 5, "status": "active"}

        def status():
            return {**initial, "blocked": fixture["phase"] != "active", "session": session if fixture["phase"] == "active" else None,
                    "expires_at": session["expires_at"] if fixture["phase"] == "active" else None, "server_time": now().isoformat()}

        def route_api(route):
            path = route.request.url.split("/api/", 1)[1]
            if fixture["offline"]:
                route.abort()
                return
            if path == "status":
                payload = status()
            elif path == "usage":
                payload = {"today_minutes": 1, "daily_limit_minutes": 120, "remaining_minutes": 119,
                           "daily": [{"date": now().date().isoformat(), "minutes": 1}],
                           "history": [session] if fixture["closed"] else []}
            elif path == "chat":
                content = route.request.post_data_json["message"]
                fixture["messages"] = [{"id": "1", "role": "user", "content": content, "created_at": now().isoformat()},
                                       {"id": "2", "role": "assistant", "content": "Five minutes for that specific tutorial. Make them count.", "created_at": now().isoformat()}]
                fixture.update(phase="active", closed=True)
                payload = {"response": fixture["messages"][-1]["content"], "decision": "grant", "conversation_id": "ui-conversation", "youtube_status": status(),
                           "tool_events": [{"name": "grant_youtube_access", "status": "success", "detail": "Approved five minutes."}]}
            elif path.startswith("conversations/"):
                payload = {"id": "ui-conversation", "status": "closed", "messages": fixture["messages"]}
            elif path == "admin/block":
                fixture["phase"] = "blocked"
                session["status"] = "ended"
                payload = status()
            else:
                route.continue_()
                return
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        page.route("**/api/**", route_api)
        page.goto("http://127.0.0.1:8000")
        expect(page.get_by_role("heading", name="YouTube is blocked")).to_be_visible()
        page.get_by_role("button", name="Learn something").click()
        expect(page.get_by_label("Your reason for using YouTube")).to_have_value("I want to watch a tutorial about ")
        page.get_by_label("Your reason for using YouTube").fill("Five minutes for a specific tutorial.")
        page.get_by_role("button", name="Send message", exact=True).click()
        expect(page.get_by_role("heading", name="YouTube is unlocked")).to_be_visible(timeout=15000)
        expect(page.get_by_role("timer")).to_be_visible()
        expect(page.get_by_role("button", name="Start a new request")).to_be_visible()
        page.screenshot(path=str(OUT / "active-session.png"), full_page=True)
        page.reload()
        expect(page.get_by_role("button", name="Start a new request")).to_be_visible()
        expect(page.get_by_text("Five minutes for that specific tutorial. Make them count.")).to_be_visible()
        print("PASS: starter, send, approved session, timer, completed request and reload", flush=True)
        page.get_by_role("button", name="I’m done. Block YouTube.").click()
        expect(page.get_by_role("heading", name="YouTube is blocked")).to_be_visible()
        page.get_by_role("link", name="Usage history", exact=True).click()
        expect(page.get_by_role("cell", name="A focused tutorial")).to_be_visible()
        page.screenshot(path=str(OUT / "history.png"), full_page=True)
        page.get_by_role("link", name="How it works", exact=True).click()
        expect(page.get_by_role("heading", name="Your ground rules")).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("link", name="Big Bro", exact=True).click()
        page.get_by_role("button", name="Start a new request").click()
        expect(page.get_by_label("Your reason for using YouTube")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(OUT / "mobile.png"), full_page=True)
        print("PASS: early block, history, policy, mobile navigation and new request", flush=True)
        fixture["phase"] = "active"
        session["expires_at"] = (now() + timedelta(seconds=2)).isoformat()
        page.reload()
        expect(page.get_by_role("heading", name="Reblocking pending")).to_be_visible(timeout=15000)
        fixture["phase"] = "blocked"
        expect(page.get_by_role("heading", name="YouTube is blocked")).to_be_visible(timeout=15000)
        fixture["offline"] = True
        expect(page.get_by_role("heading", name="Protection unverified")).to_be_visible(timeout=15000)
        assert not errors, errors
        print("PASS: countdown waits for backend confirmation; offline never claims protection", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
