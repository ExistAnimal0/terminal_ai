"""
Open a URL in the user's default browser, positioned in a screen quadrant.

Uses Windows ctypes to get screen size and move/resize the browser window.
Quadrants: top_left, top_right, bottom_left, bottom_right.

If new_window=True, launches a fresh browser window via the browser's CLI
flag instead of opening a tab in an existing window.
"""

import ctypes
import os
import subprocess
import time
import webbrowser

user32 = ctypes.windll.user32

QUADRANTS = ("top_left", "top_right", "bottom_left", "bottom_right")

# Common browser install paths and their "new window" flags
_BROWSERS = [
    # (exe candidates, new-window flag)
    (
        [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ],
        "--new-window",
    ),
    (
        [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "--new-window",
    ),
    (
        [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Mozilla\Firefox\firefox.exe"),
        ],
        "--new-window",
    ),
]


def _screen_size():
    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return w, h


def _quadrant_rect(quadrant, sw, sh):
    hw, hh = sw // 2, sh // 2
    return {
        "top_left":      (0,    0,    hw, hh),
        "top_right":     (hw,   0,    hw, hh),
        "bottom_left":   (0,    hh,   hw, hh),
        "bottom_right":  (hw,   hh,   hw, hh),
    }[quadrant]


def _find_browser():
    """Return (exe_path, new_window_flag) for the first installed browser found."""
    for candidates, flag in _BROWSERS:
        for path in candidates:
            if os.path.isfile(path):
                return path, flag
    return None, None


def tool(url: str, quadrant: str, new_window: bool = False) -> str:
    """Open a URL in the default browser, snapped to a screen quadrant."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    quadrant = (quadrant or "").strip().lower()
    if quadrant not in QUADRANTS:
        return f"Unknown quadrant '{quadrant}'. Use: {', '.join(QUADRANTS)}"

    sw, sh = _screen_size()
    x, y, w, h = _quadrant_rect(quadrant, sw, sh)

    # Launch the browser
    if new_window:
        exe, flag = _find_browser()
        if not exe:
            return "new_window=True but no supported browser (Chrome/Edge/Firefox) found."
        try:
            subprocess.Popen([exe, flag, url])
        except Exception as e:
            return f"Failed to launch {os.path.basename(exe)}: {e}"
    else:
        try:
            webbrowser.open(url)
        except Exception as e:
            return f"Failed to open {url}: {e}"

    # Give the browser a moment to launch / focus
    time.sleep(2)

    # Find the foreground window (the browser)
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return f"Opened {url} but could not find the browser window to reposition."

    # Move and resize to the quadrant
    user32.MoveWindow(hwnd, x, y, w, h, True)

    mode = "new window" if new_window else "existing window"
    return f"Opened {url} in {mode}, {quadrant} quadrant ({x},{y} {w}x{h} of {sw}x{sh})."
