import subprocess
import os


def _run(args: list, cwd: str) -> str:
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=15)
        out = r.stdout.strip()
        err = r.stderr.strip()
        if r.returncode != 0:
            return f"git {' '.join(args)} failed:\n{err}"
        return out if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "git command timed out."
    except FileNotFoundError:
        return "git not found on PATH."


def tool(action: str, path: str = ".", message: str = "", ref: str = "") -> str:
    if not os.path.isdir(path):
        return f"Directory not found: {path}"

    if action == "status":
        return _run(["status", "--short"], path)

    elif action == "log":
        args = ["log", "--oneline", "--max-count=20"]
        if ref:
            args = ["log", "--oneline", "--max-count=20", ref]
        return _run(args, path)

    elif action == "diff":
        args = ["diff"]
        if ref:
            args = ["diff", ref]
        return _run(args, path)

    elif action == "commit":
        if not message:
            return "message is required for action='commit'."
        _run(["add", "-A"], path)
        return _run(["commit", "-m", message], path)

    else:
        return f"Unknown action: {action}. Use 'status', 'log', 'diff', or 'commit'."
