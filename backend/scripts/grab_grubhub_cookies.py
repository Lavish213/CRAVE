#!/usr/bin/env python3
"""
grab_grubhub_cookies.py
=======================
Opens a real Chromium browser via Playwright, navigates to a Grubhub
restaurant page, intercepts the API request to api-gtm.grubhub.com, and
prints the exact Cookie string + perimeter-x token you need.

Usage
-----
    # Install playwright once:
    pip install playwright
    playwright install chromium

    # Run (headful by default so you can log in):
    python backend/scripts/grab_grubhub_cookies.py

    # Run against a specific restaurant page:
    python backend/scripts/grab_grubhub_cookies.py --url "https://www.grubhub.com/restaurant/in-n-out-burger/20513692237"

    # Run headless (only works if already logged in via saved state):
    python backend/scripts/grab_grubhub_cookies.py --headless

Output
------
The script prints export commands ready to paste into your shell:

    export GRUBHUB_COOKIES='_px2=abc...; _pxvid=def...; ...'
    export GRUBHUB_PERIMETER_X='eyJ...'
    export GRUBHUB_FEED_ID='1717110'

It also saves them to backend/.grubhub_env for convenience.

Notes
-----
- If not logged in, the browser will open Grubhub's homepage. Log in
  manually, then the script will proceed automatically.
- The intercepted request is the first XHR to api-gtm.grubhub.com after
  the restaurant page loads.
- Cookies expire. Re-run whenever you get 401 errors.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time


DEFAULT_URL = "https://www.grubhub.com/restaurant/in-n-out-burger-3600-sutter-st/20513692237"
TIMEOUT_MS = 60_000  # 60 seconds to wait for the API request


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture Grubhub API cookies via Playwright")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Grubhub restaurant page URL to navigate to",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (requires already-saved auth state)",
    )
    parser.add_argument(
        "--save-state",
        metavar="FILE",
        default=None,
        help="Save browser auth state to this JSON file for headless reuse",
    )
    parser.add_argument(
        "--load-state",
        metavar="FILE",
        default=None,
        help="Load previously saved browser auth state (enables headless without re-login)",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright, Request
    except ImportError:
        print(
            "ERROR: playwright not installed.\n"
            "Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    captured: dict = {}

    def on_request(request: Request) -> None:
        """Intercept the CATEGORY menu feed request to api-gtm.grubhub.com."""
        if "api-gtm.grubhub.com/restaurant_gateway/feed" not in request.url:
            return
        # Skip early POPULAR_ITEMS requests — they fire before restaurant_id
        # is resolved and have None/null as the restaurant_id path segment.
        # We want task=CATEGORY which has the real restaurant_id and full menu.
        if "task=CATEGORY" not in request.url:
            return
        if captured:
            return  # already got one

        headers = request.all_headers()
        cookie_str = headers.get("cookie", "")
        perimeter_x = headers.get("perimeter-x", "")

        # Extract feed_id from URL: /feed/{feed_id}/{restaurant_id}
        feed_id_match = re.search(r"/restaurant_gateway/feed/(\d+)/", request.url)
        feed_id = feed_id_match.group(1) if feed_id_match else ""

        # Extract restaurant_id (second numeric segment after feed_id)
        restaurant_id_match = re.search(r"/restaurant_gateway/feed/\d+/(\d+)", request.url)
        restaurant_id = restaurant_id_match.group(1) if restaurant_id_match else ""

        captured["cookie"] = cookie_str
        captured["perimeter_x"] = perimeter_x
        captured["feed_id"] = feed_id
        captured["restaurant_id"] = restaurant_id
        captured["api_url"] = request.url

        print(f"\n[FULL API URL]\n  {request.url}", flush=True)

        print(f"\n[INTERCEPTED] {request.url[:100]}...", flush=True)

    with sync_playwright() as p:
        launch_kwargs: dict = {
            "headless": args.headless,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        }

        context_kwargs: dict = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/110.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 800},
            "locale": "en-US",
        }

        if args.load_state and os.path.exists(args.load_state):
            context_kwargs["storage_state"] = args.load_state
            print(f"Loading auth state from {args.load_state}", flush=True)

        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        # Listen for API requests
        page.on("request", on_request)

        if not args.headless:
            print(
                "\n[BROWSER OPENED]\n"
                "If not logged in to Grubhub, log in now in the browser window.\n"
                "The script will capture cookies once you land on the restaurant page.\n",
                flush=True,
            )

        print(f"Navigating to: {args.url}", flush=True)
        page.goto(args.url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

        # Wait briefly for initial requests, then scroll to trigger CATEGORY load.
        # POPULAR_ITEMS fires immediately on page load (but has no restaurant_id).
        # CATEGORY fires after the page has resolved the restaurant_id — scrolling
        # into the menu section triggers it reliably.
        page.wait_for_timeout(3000)

        if not captured:
            print("Scrolling to trigger CATEGORY menu load...", flush=True)
            page.evaluate("window.scrollTo(0, 600)")
            deadline = time.time() + 30
            while not captured and time.time() < deadline:
                page.wait_for_timeout(500)

        if not captured:
            print("Scrolling further...", flush=True)
            page.evaluate("window.scrollTo(0, 1200)")
            deadline = time.time() + 20
            while not captured and time.time() < deadline:
                page.wait_for_timeout(500)

        if args.save_state:
            context.storage_state(path=args.save_state)
            print(f"\nAuth state saved to {args.save_state}", flush=True)

        browser.close()

    if not captured:
        print(
            "\nERROR: No api-gtm.grubhub.com/restaurant_gateway/feed request intercepted.\n"
            "Possible causes:\n"
            "  - Not logged in (run without --headless and log in)\n"
            "  - Restaurant page didn't load the menu (try a different URL)\n"
            "  - Bot detection blocked the page load\n",
            file=sys.stderr,
        )
        sys.exit(1)

    cookie_str = captured.get("cookie", "")
    perimeter_x = captured.get("perimeter_x", "")
    feed_id = captured.get("feed_id", "")
    restaurant_id = captured.get("restaurant_id", "")
    api_url = captured.get("api_url", "")

    print("\n" + "=" * 70)
    print("CAPTURED GRUBHUB CREDENTIALS")
    print("=" * 70)

    if feed_id:
        print(f"\nFeed ID: {feed_id}")
    if restaurant_id:
        print(f"Restaurant ID: {restaurant_id}")

    print(f"\nAPI URL (full):\n  {api_url}")

    if perimeter_x:
        print(f"\nperimeter-x (first 60 chars): {perimeter_x[:60]}...")

    print("\n" + "-" * 70)
    print("PASTE THESE INTO YOUR SHELL (or ~/.zshrc / .env):")
    print("-" * 70)

    if cookie_str:
        print(f"\nexport GRUBHUB_COOKIES='{cookie_str}'")

    if perimeter_x:
        print(f"\nexport GRUBHUB_PERIMETER_X='{perimeter_x}'")

    if feed_id:
        print(f"\nexport GRUBHUB_FEED_ID='{feed_id}'")

    if restaurant_id:
        print(f"\nexport GRUBHUB_RESTAURANT_ID='{restaurant_id}'")

    # Save to file
    env_path = os.path.join(os.path.dirname(__file__), "..", ".grubhub_env")
    env_path = os.path.abspath(env_path)

    lines = []
    if cookie_str:
        lines.append(f"export GRUBHUB_COOKIES='{cookie_str}'\n")
    if perimeter_x:
        lines.append(f"export GRUBHUB_PERIMETER_X='{perimeter_x}'\n")
    if feed_id:
        lines.append(f"export GRUBHUB_FEED_ID='{feed_id}'\n")
    if restaurant_id:
        lines.append(f"export GRUBHUB_RESTAURANT_ID='{restaurant_id}'\n")

    if lines:
        with open(env_path, "w") as f:
            f.writelines(lines)
        print(f"\nAlso saved to: {env_path}")
        print(f"To load: source {env_path}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
