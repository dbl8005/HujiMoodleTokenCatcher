# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.45"]
# ///
"""Get a Moodle mobile web-service token for an SSO-only Moodle (e.g. HUJI).

Opens a real browser window; the user logs in themselves (any method: password,
temporary code, OTP). The script catches the moodlemobile:// redirect that
Moodle sends to its mobile app and prints the token.

Usage:
    uv run get_token.py [MOODLE_URL]
"""
import base64
import subprocess
import sys
import time

from playwright.sync_api import Error, sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://moodle.huji.ac.il/2026-27").rstrip("/")
LAUNCH = f"{BASE}/admin/tool/mobile/launch.php?service=moodle_mobile_app&passport=12345&urlscheme=moodlemobile"
TIMEOUT_S = 300


def decode(url: str) -> str:
    payload = url.split("token=", 1)[1].split("&")[0]
    payload += "=" * (-len(payload) % 4)
    parts = base64.b64decode(payload).decode().split(":::")
    return parts[1]  # sig:::TOKEN[:::privatetoken]


def launch_browser(p):
    # Prefer the user's installed Chrome; fall back to Playwright's Chromium.
    try:
        return p.chromium.launch(channel="chrome", headless=False)
    except Error:
        try:
            return p.chromium.launch(headless=False)
        except Error:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            return p.chromium.launch(headless=False)


def main():
    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page()
        found = []
        page.on("request", lambda r: r.url.startswith("moodlemobile://") and found.append(r.url))
        page.on("framenavigated", lambda f: f.url.startswith("moodlemobile://") and found.append(f.url))

        print("Log in to Moodle in the browser window that just opened...", file=sys.stderr)
        try:
            page.goto(LAUNCH)
        except Error:
            pass  # navigation to moodlemobile:// aborts; that's expected

        deadline = time.time() + TIMEOUT_S
        while not found and time.time() < deadline:
            page.wait_for_timeout(500)
        browser.close()

    if not found:
        sys.exit("Timed out: no token received. Did the login finish?")
    print(decode(found[0]))


if __name__ == "__main__":
    main()
