"""
Execution tools for terminal_ai.
"""

import subprocess


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _err(msg):
    return f"Error: {msg}"


def _clip(text, n=4000):
    text = str(text)
    return text if len(text) <= n else text[:n] + f"\n... [truncated, {len(text)} chars total]"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def run_python(code: str, timeout: int = 30) -> str:
    """Run a Python snippet and return its stdout (and any traceback)."""
    if not code or not code.strip():
        return "No code provided."
    try:
        r = subprocess.run(
            ["python", "-c", code],
            capture_output=True, text=True, timeout=timeout
        )
        out = r.stdout.strip()
        err = r.stderr.strip()
        if r.returncode != 0:
            return _err(f"exit {r.returncode}\n{err or '(no stderr)'}")
        return out if out else "(ran OK, no output)"
    except subprocess.TimeoutExpired:
        return _err(f"timed out after {timeout}s")
    except Exception as e:
        return _err(f"could not run: {e}")


def run_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command and return its combined output."""
    if not command or not command.strip():
        return "No command provided."
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        out = (r.stdout.strip() + ("\n" + r.stderr.strip() if r.stderr.strip() else ""))
        if r.returncode != 0:
            return _err(f"exit {r.returncode}\n{out or '(no output)'}")
        return out if out else "(ran OK, no output)"
    except subprocess.TimeoutExpired:
        return _err(f"timed out after {timeout}s")
    except Exception as e:
        return _err(f"could not run: {e}")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def _p(props, required=None):
    return {"type": "object", "properties": props, "required": required or []}


def _s(desc):
    return {"type": "string", "description": desc}


def _i(desc):
    return {"type": "integer", "description": desc}


TOOLS = {
    "run_python": {
        "description": "Run a Python code snippet and return its stdout/traceback.",
        "parameters": _p({"code": _s("Python code to run."),
                         "timeout": _i("Seconds before timeout (default 30)")},
                        ["code"]),
        "fn": run_python,
    },
    "run_shell": {
        "description": "Run a shell command and return its output.",
        "parameters": _p({"command": _s("Shell command to run."),
                         "timeout": _i("Seconds before timeout (default 30)")},
                        ["command"]),
        "fn": run_shell,
    },
}
