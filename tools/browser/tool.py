"""
Playwright browser tool for terminal_ai.

Drives a headless Chromium browser. A single browser/context/page is kept
alive at module level so multi-step interactions (navigate, then click,
then read) work across separate tool() calls within the same session.

Actions:
  goto       navigate to a URL and confirm the load (returns title)
  text       return the rendered text of the current (or given) page
  html       return the raw HTML of the current (or given) page
  title      return the current page title
  screenshot save a PNG screenshot to a file
  click      click an element (CSS selector) on the current page
  type       type text into an element (CSS selector) on the current page
  wait       wait for a selector to appear
  eval       run a JS expression on the current page, return the result
  cookies    import cookies from a JSON file (cookie_file param) into the context
  cookies_export  dump current context cookies to a JSON file (output param)
  close      close the browser and free resources
"""

import os
import re
import concurrent.futures

try:
    from playwright.sync_api import sync_playwright
    _HAS_PW = True
except Exception:
    _HAS_PW = False

# Dedicated worker thread for Playwright's sync API.
# The main thread may already have a running asyncio event loop (e.g. from
# httpx/ollama), which makes sync_playwright() raise
# "Playwright sync API inside an asyncio loop".  A fresh thread has no
# event loop, so the sync API works there.
_PW_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="pw")


# Persistent browser state (survives across tool() calls in one session)
_PW = None
_CONTEXT = None
_PAGE = None

# On-disk profile dir so cookies/logins survive across terminal_ai restarts.
# Lives in the project root; gitignored so it is per-user.
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "browser_profile")


def _err(msg):
    return f"Error: {msg}"


def _clip(text, n=8000):
    text = str(text)
    return text if len(text) <= n else text[:n] + f"\n... [truncated, {len(text)} chars total]"


def _ensure_browser():
    """Lazily start the persistent browser context/page. Returns (page, error)."""
    global _PW, _CONTEXT, _PAGE
    if not _HAS_PW:
        return None, _err("playwright not installed (pip install playwright && playwright install chromium)")
    if _PAGE is not None:
        return _PAGE, None
    try:
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        _PW = sync_playwright().start()
        _CONTEXT = _PW.chromium.launch_persistent_context(
            USER_DATA_DIR, headless=False, viewport={"width": 1280, "height": 900}
        )
        _PAGE = _CONTEXT.new_page()
        return _PAGE, None
    except Exception as e:
        _teardown()
        return None, _err(f"failed to start browser: {e}")


def _teardown():
    global _PW, _CONTEXT, _PAGE
    for obj in (_PAGE, _CONTEXT):
        try:
            if obj is not None:
                obj.close()
        except Exception:
            pass
    if _PW is not None:
        try:
            _PW.stop()
        except Exception:
            pass
    _PAGE = _CONTEXT = _PW = None


def _goto(page, url, wait_ms=1500):
    if not re.match(r"^https?://", url):
        url = "https://" + url
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    if wait_ms > 0:
        page.wait_for_timeout(wait_ms)
    return url


def _clean_text(html):
    """Strip scripts/styles/tags from HTML into readable text."""
    if not html:
        return ""
    text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _pw_tool(action, url=None, selector=None, text=None, expression=None,
             output=None, wait_ms=1500, timeout=10000, max_chars=8000,
             cookie_file=None):
    """Playwright logic. Runs in the dedicated worker thread."""
    action = (action or "").strip().lower()

    # close: tear down and report
    if action == "close":
        _teardown()
        return "Browser closed."

    page, err = _ensure_browser()
    if err:
        return err

    try:
        if action == "goto":
            if not url:
                return "No URL provided for goto."
            _goto(page, url, wait_ms)
            return f"Loaded {url}. Title: {page.title()}"

        if action == "text":
            if url:
                _goto(page, url, wait_ms)
            return _clip(_clean_text(page.content()), max_chars)

        if action == "html":
            if url:
                _goto(page, url, wait_ms)
            return _clip(page.content(), max_chars)

        if action == "title":
            if url:
                _goto(page, url, wait_ms)
            return page.title()

        if action == "screenshot":
            if url:
                _goto(page, url, wait_ms)
            out = output or "screenshot.png"
            if not out.lower().endswith(".png"):
                out += ".png"
            page.screenshot(path=out, full_page=False)
            return f"Saved screenshot to {os.path.abspath(out)}"

        if action == "click":
            if not selector:
                return "No selector provided for click."
            page.click(selector, timeout=timeout)
            page.wait_for_timeout(500)
            return f"Clicked '{selector}'. Page title: {page.title()}"

        if action == "type":
            if not selector:
                return "No selector provided for type."
            page.fill(selector, text or "", timeout=timeout)
            return f"Typed into '{selector}'."

        if action == "wait":
            if not selector:
                return "No selector provided for wait."
            try:
                page.wait_for_selector(selector, timeout=timeout)
                return f"Element '{selector}' is present."
            except Exception:
                return f"Timed out waiting for '{selector}' after {timeout}ms."

        if action == "eval":
            if not expression:
                return "No expression provided for eval."
            result = page.evaluate(expression)
            return _clip(str(result), max_chars)

        if action == "cookies":
            if not cookie_file:
                return "No cookie_file provided for cookies. Pass a path to a JSON file of cookies."
            import json as _json
            if not os.path.isfile(cookie_file):
                return _err(f"Cookie file not found: {cookie_file}")
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    cookies = _json.load(f)
            except Exception as e:
                return _err(f"Failed to parse cookie file: {e}")
            if not isinstance(cookies, list):
                return _err("Cookie file must contain a JSON array of cookie objects.")
            # Normalize: ensure required fields have defaults
            for c in cookies:
                c.setdefault("path", "/")
                c.setdefault("expires", -1)
                c.setdefault("httpOnly", False)
                c.setdefault("secure", False)
                c.setdefault("sameSite", "Lax")
            _CONTEXT.add_cookies(cookies)
            return f"Imported {len(cookies)} cookies from {cookie_file}."

        if action == "cookies_export":
            out = output or "cookies_export.json"
            cookies = _CONTEXT.cookies()
            import json as _json
            with open(out, "w", encoding="utf-8") as f:
                _json.dump(cookies, f, indent=2)
            return f"Exported {len(cookies)} cookies to {os.path.abspath(out)}."

        return f"Unknown action: {action}. Use goto, text, html, title, screenshot, click, type, wait, eval, cookies, cookies_export, or close."

    except Exception as e:
        return _err(f"{action} failed: {e}")


def tool(action, url=None, selector=None, text=None, expression=None,
         output=None, wait_ms=1500, timeout=10000, max_chars=8000,
         cookie_file=None):
    """Entry point called by the main app. Submits Playwright work to a
    dedicated thread so the sync API never collides with a running
    asyncio event loop in the main thread."""
    if not _HAS_PW:
        return _err("playwright not installed (pip install playwright && playwright install chromium)")
    try:
        future = _PW_EXECUTOR.submit(
            _pw_tool, action, url, selector, text, expression,
            output, wait_ms, timeout, max_chars, cookie_file,
        )
        return future.result()
    except Exception as e:
        return _err(f"browser tool error: {e}")
