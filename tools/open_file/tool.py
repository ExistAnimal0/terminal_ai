import os
import sys

def tool(path: str) -> str:
    """Open a file in its default application."""
    if not os.path.exists(path):
        return f"Error: file not found: {path}"
    if not os.path.isfile(path):
        return f"Error: not a file: {path}"
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
        return f"Opened: {path}"
    except Exception as e:
        return f"Error opening {path}: {e}"
