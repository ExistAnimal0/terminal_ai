import pyperclip

def tool(action, text=None):
    if action == 'get':
        val = pyperclip.paste()
        return val if val else '(clipboard empty)'
    elif action == 'set':
        if text is None:
            return "No text provided for set."
        pyperclip.copy(text)
        return f"Set clipboard ({len(text)} chars)."
    else:
        return f"Unknown action: {action}. Use 'get' or 'set'."
