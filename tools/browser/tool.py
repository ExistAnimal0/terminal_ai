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
  close      close the browser and free resources
"""

import os
import re

try:
    from playwright.sync_api import sync_playwright
    _HAS_PW = True
except Exception:
    _HAS_PW = False


# Persistent browser state (survives across tool() calls in one session)
_PW = None
_BROWSER = None
_CONTEXT = None
_PAGE = None


def _err(msg):
    return f"Error: {msg}"


def _clip(text, n=8000):
    text = str(text)
    return text if len(text) <= n else text[:n] + f"\n... [truncated, {len(text)} chars total]"


def _ensure_browser():
    """Lazily start the browser/context/page. Returns (page, error)."""
    global _PW, _BROWSER, _CONTEXT, _PAGE
    if not _HAS_PW:
        return None, _err("playwright not installed (pip install playwright && playwright install chromium)")
    if _PAGE is not None:
        return _PAGE, None
    try:
        _PW = sync_playwright().start()
        _BROWSER = _PW.chromium.launch(headless=False)
        _CONTEXT = _BROWSER.new_context(viewport={"width": 1280, "height": 900})
        _PAGE = _CONTEXT.new_page()
        return _PAGE, None
    except Exception as e:
        _teardown()
        return None, _err(f"failed to start browser: {e}")


def _teardown():
    global _PW, _BROWSER, _CONTEXT, _PAGE
    for obj in (_PAGE, _CONTEXT, _BROWSER):
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
    _PAGE = _CONTEXT = _BROWSER = _PW = None


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


def tool(action, url=None, selector=None, text=None, expression=None,
         output=None, wait_ms=1500, timeout=10000, max_chars=8000):
    if not _HAS_PW:
        return _err("playwright not installed (pip install playwright && playwright install chromium)")

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

        return f"Unknown action: {action}. Use goto, text, html, title, screenshot, click, type, wait, eval, or close."

    except Exception as e:
        return _err(f"{action} failed: {e}")
