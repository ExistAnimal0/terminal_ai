import os
import sys
import tempfile
import time
import subprocess
import pyautogui
from PIL import Image

# Disable pyautogui fail-safe (moving mouse to corner raises exception)
pyautogui.FAILSAFE = False

# Screenshot save dir
SHOT_DIR = os.path.join(tempfile.gettempdir(), "computer_use")
os.makedirs(SHOT_DIR, exist_ok=True)

# Vision model - read from .env or fall back
def _get_model():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("MODEL="):
                    return line.strip().split("=", 1)[1]
    return "orcarouter/Qwen3.8-27B-Uncensored:q3_K_S"

def _screenshot(region=None):
    """Capture screen (or a region) and save to a temp PNG. Returns the path."""
    os.makedirs(SHOT_DIR, exist_ok=True)
    path = os.path.join(SHOT_DIR, f"shot_{int(time.time())}.png")
    if region:
        # region is "x,y,w,h"
        parts = region.split(",")
        x, y, w, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        img = pyautogui.screenshot(region=(x, y, w, h))
    else:
        img = pyautogui.screenshot()
    img.save(path)
    return path

def _analyze_screen(prompt, region=None):
    """Screenshot (or crop) + vision model. Returns the model's text response."""
    path = _screenshot(region)
    try:
        import ollama
        model = _get_model()
        resp = ollama.chat(
            model=model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [path],
            }],
        )
        return resp["message"]["content"]
    finally:
        # Clean up the temp screenshot
        try:
            os.remove(path)
        except OSError:
            pass

def _mouse_move(x, y):
    pyautogui.moveTo(x, y, duration=0.15)
    return f"moved to ({x}, {y})"

def _mouse_click(x, y, button="left"):
    pyautogui.click(x, y, button=button)
    return f"{button}-clicked at ({x}, {y})"

def _mouse_double_click(x, y):
    pyautogui.doubleClick(x, y)
    return f"double-clicked at ({x}, {y})"

def _mouse_drag(x, y, x2, y2):
    pyautogui.moveTo(x, y, duration=0.1)
    time.sleep(0.05)
    pyautogui.drag(x2 - x, y2 - y, duration=0.3)
    return f"dragged ({x},{y}) -> ({x2},{y2})"

def _mouse_scroll(x, y, amount):
    pyautogui.moveTo(x, y, duration=0.1)
    time.sleep(0.05)
    pyautogui.scroll(amount)
    direction = "up" if amount > 0 else "down"
    return f"scrolled {direction} {abs(amount)} at ({x}, {y})"

def _keyboard_type(text):
    # Use clipboard for non-ASCII or long strings
    if any(ord(c) > 127 for c in text) or len(text) > 200:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        return f"typed {len(text)} chars (via clipboard)"
    else:
        pyautogui.typewrite(text, interval=0.02)
        return f"typed {len(text)} chars"

def _keyboard_press(key):
    pyautogui.press(key)
    return f"pressed {key}"

def _keyboard_hotkey(keys):
    parts = [k.strip() for k in keys.split("+")]
    pyautogui.hotkey(*parts)
    return f"hotkey {keys}"

def _app_launch(name):
    # Try as a path first, then as a registered app name
    if os.path.exists(name):
        if sys.platform == "win32":
            os.startfile(name)
        else:
            subprocess.Popen([name])
        return f"launched {name}"
    else:
        if sys.platform == "win32":
            # Use shell: to handle .exe and registered apps
            subprocess.Popen(f'shell:{name}', shell=True)
        else:
            subprocess.Popen(["open", name])
        return f"launched {name}"

def tool(action, x=None, y=None, x2=None, y2=None, button="left",
         amount=0, text="", key="", keys="", name="", prompt="", region=None):
    if action == "screenshot":
        path = _screenshot(region)
        return f"screenshot saved to {path}"

    elif action == "analyze_screen":
        if not prompt:
            prompt = "Describe what is visible on this screen."
        return _analyze_screen(prompt, region)

    elif action == "mouse_move":
        return _mouse_move(x, y)

    elif action == "mouse_click":
        return _mouse_click(x, y, button)

    elif action == "mouse_double_click":
        return _mouse_double_click(x, y)

    elif action == "mouse_drag":
        return _mouse_drag(x, y, x2, y2)

    elif action == "mouse_scroll":
        return _mouse_scroll(x, y, amount)

    elif action == "keyboard_type":
        return _keyboard_type(text)

    elif action == "keyboard_press":
        return _keyboard_press(key)

    elif action == "keyboard_hotkey":
        return _keyboard_hotkey(keys)

    elif action == "app_launch":
        return _app_launch(name)

    else:
        return f"unknown action: {action}"
