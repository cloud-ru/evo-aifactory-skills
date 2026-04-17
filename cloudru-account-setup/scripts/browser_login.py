#!/usr/bin/env python3
"""Open Cloud.ru console in a real browser, let the user log in,
then extract the project URL and bearer token automatically.

By default also runs cloudru_account_bootstrap.py to create credentials
immediately (the token expires in ~5 minutes).

Outputs JSON to stdout.

Requires: playwright  (pip install playwright && playwright install chromium)

Usage:
  python browser_login.py                   # login + bootstrap
  python browser_login.py --no-bootstrap    # login only, print token JSON
  python browser_login.py --timeout 300     # custom timeout in seconds
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

LOGIN_URL = "https://console.cloud.ru/static-page/login-destination"
CONSOLE_URL_PREFIX = "https://console.cloud.ru"

# JS to extract the OIDC access token from localStorage
TOKEN_JS = """() => {
    const knownKey = "oidc.user:https://id.cloud.ru/auth/system/:e95a1db5-a61c-425b-ae62-26d3a7e224f7";
    let raw = localStorage.getItem(knownKey);
    if (raw) {
        return JSON.parse(raw).access_token || null;
    }
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith("oidc.user:https://id.cloud.ru/auth/system/")) {
            raw = localStorage.getItem(key);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed.access_token) return parsed.access_token;
            }
        }
    }
    return null;
}"""

LIST_STORAGE_KEYS_JS = """() => {
    const keys = [];
    for (let i = 0; i < localStorage.length; i++) {
        keys.push(localStorage.key(i));
    }
    return keys;
}"""


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", file=sys.stderr, flush=True)


def parse_ids_from_url(url: str) -> dict:
    from urllib.parse import parse_qs, urlparse, unquote

    parsed = urlparse(url)
    path_segments = [s for s in parsed.path.split("/") if s]
    query = parse_qs(parsed.query, keep_blank_values=False)

    fragment = parsed.fragment or ""
    if "?" in fragment:
        frag_query = parse_qs(fragment.split("?", 1)[1], keep_blank_values=False)
        query.update(frag_query)

    def first_uuid_after(marker: str):
        try:
            idx = path_segments.index(marker)
        except ValueError:
            return None
        if idx + 1 < len(path_segments) and UUID_RE.fullmatch(path_segments[idx + 1]):
            return path_segments[idx + 1]
        return None

    def first_query(*keys):
        for k in keys:
            vals = query.get(k)
            if vals:
                return unquote(vals[-1])
        return None

    project_id = (
        first_query("project_id", "projectId", "project-id")
        or first_uuid_after("projects")
        or first_uuid_after("project")
    )
    customer_id = (
        first_query("customerId", "customer_id", "secret_id", "secretId", "secret-id")
        or first_uuid_after("customers")
        or first_uuid_after("customer")
        or first_uuid_after("organizations")
        or first_uuid_after("organization")
    )

    return {"project_id": project_id, "customer_id": customer_id}


def url_has_project(url: str) -> bool:
    if not url.startswith(CONSOLE_URL_PREFIX):
        return False
    ids = parse_ids_from_url(url)
    return bool(ids.get("project_id"))


def get_real_url(page) -> str | None:
    """Get the actual browser URL via JS — page.url can be stale during redirects."""
    try:
        return page.evaluate("window.location.href")
    except Exception:
        return None


def ensure_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            "Error: playwright is not installed.\n"
            "Install it with:\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Browser-assisted Cloud.ru login")
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Max seconds to wait for login + project navigation (default: 180)",
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Only extract token and URL, do not run cloudru_account_bootstrap.py",
    )
    parser.add_argument(
        "--skip-access-key",
        action="store_true",
        help="Pass --skip-access-key to bootstrap script",
    )
    parser.add_argument(
        "--service-account-name",
        default="foundation-models-account",
        help="Service account name (passed to bootstrap script)",
    )
    args = parser.parse_args()

    ensure_playwright()

    from playwright.sync_api import sync_playwright

    log("Starting browser login flow")
    log(f"Timeout: {args.timeout}s")

    with sync_playwright() as pw:
        log("Launching Chromium...")
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Track all pages (in case login opens a popup)
        all_pages = [page]

        def on_new_page(new_page):
            log(f"New tab/popup opened: {new_page.url[:100]}")
            all_pages.append(new_page)

        context.on("page", on_new_page)

        log(f"Navigating to {LOGIN_URL}")
        try:
            page.goto(LOGIN_URL, wait_until="commit", timeout=15000)
        except Exception as e:
            log(f"goto finished with: {e}")

        log("Browser is open. Please log in and navigate to your project.")
        log("The script will detect it automatically.\n")

        deadline = time.time() + args.timeout
        project_url = None
        target_page = None
        last_logged_url = ""

        while time.time() < deadline:
            # Check all open pages/tabs
            for p in list(all_pages):
                try:
                    if p.is_closed():
                        continue
                    url = get_real_url(p)
                    if not url:
                        continue
                except Exception:
                    continue

                # Log URL changes
                if url != last_logged_url:
                    domain = url.split("?")[0][:100]
                    log(f"  URL: {domain}")
                    last_logged_url = url

                if url_has_project(url):
                    project_url = url
                    target_page = p
                    break

            if project_url:
                break

            remaining = int(deadline - time.time())
            if remaining > 0 and remaining % 30 == 0:
                log(f"  Still waiting... {remaining}s left")

            time.sleep(1)

        if not project_url or not target_page:
            log(f"TIMEOUT after {args.timeout}s")
            # Last-ditch: check page.url (might have updated after redirects settled)
            for p in all_pages:
                try:
                    if p.is_closed():
                        continue
                    url = get_real_url(p)
                    log(f"  Final URL on tab: {url[:120] if url else 'N/A'}")
                    if url and url_has_project(url):
                        project_url = url
                        target_page = p
                        log("  Found project URL in final check!")
                        break
                except Exception:
                    pass

        if not project_url or not target_page:
            log("FAILED: never reached a project page")
            log("Expected: console.cloud.ru URL with projectId param or /projects/<uuid> path")
            browser.close()
            sys.exit(1)

        ids = parse_ids_from_url(project_url)
        log(f"Project detected!")
        log(f"  project_id:  {ids.get('project_id')}")
        log(f"  customer_id: {ids.get('customer_id')}")

        # Extract token from the page that's on console.cloud.ru
        log("Extracting token from localStorage...")

        storage_keys = target_page.evaluate(LIST_STORAGE_KEYS_JS)
        oidc_keys = [k for k in storage_keys if k and "oidc" in k.lower()]
        log(f"  localStorage: {len(storage_keys)} keys, {len(oidc_keys)} OIDC-related")
        for k in oidc_keys:
            log(f"  OIDC key: {k[:100]}")

        token = target_page.evaluate(TOKEN_JS)

        if token:
            log(f"  Token OK (length={len(token)})")
        else:
            log("  Token is NULL — will retry in 3s...")
            time.sleep(3)
            token = target_page.evaluate(TOKEN_JS)
            if token:
                log(f"  Token OK on retry (length={len(token)})")
            else:
                log("  Token still NULL")

        log("Closing browser")
        browser.close()

    if not token:
        log("FAILED: could not extract bearer token from localStorage")
        sys.exit(1)

    login_result = {
        "project_url": project_url,
        "token": token[:8] + "..." if token else None,
        "token_length": len(token) if token else 0,
        "project_id": ids.get("project_id"),
        "customer_id": ids.get("customer_id"),
    }

    if args.no_bootstrap:
        log("SUCCESS (--no-bootstrap mode)")
        log("Token is available but not printed to stdout for security.")
        log("Use the full browser_login flow (without --no-bootstrap) to pass it to bootstrap automatically.")
        print(json.dumps(login_result, indent=2))
        return

    # Run bootstrap immediately while token is fresh (~5 min TTL)
    log("Running cloudru_account_bootstrap.py (token expires in ~5 min)...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bootstrap_script = os.path.join(script_dir, "cloudru_account_bootstrap.py")

    # Pass all user-controlled data via stdin JSON to avoid leaking in process list or env
    stdin_data = json.dumps({
        "project_url": project_url,
        "token": token,
        "customer_id": ids.get("customer_id", ""),
        "service_account_name": args.service_account_name,
        "skip_access_key": args.skip_access_key,
    })

    cmd = [sys.executable, bootstrap_script, "--from-stdin"]
    log(f"  Command: python {os.path.basename(bootstrap_script)} --from-stdin")
    proc = subprocess.run(cmd, input=stdin_data, text=True, capture_output=False)

    if proc.returncode != 0:
        log(f"Bootstrap failed with exit code {proc.returncode}")
        sys.exit(proc.returncode)

    log("All done!")


if __name__ == "__main__":
    main()
