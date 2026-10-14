"""
Execution tools for terminal_ai.
"""

import os
import signal
import subprocess
import sys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _err(msg):
    return f"Error: {msg}"


def _clip(text, n=4000):
    text = str(text)
    return text if len(text) <= n else text[:n] + f"\n... [truncated, {len(text)} chars total]"


def _kill_tree(proc):
    """Kill a process and all of its descendants.

    subprocess.run(timeout=...) only kills the direct child. When the command
    spawns its own worker (shell=True, python -c, ...), that grandchild keeps
    the output pipe open, so communicate() blocks forever even after the kill.
    Killing the whole process tree closes the pipes and lets us return.
    """
    pid = proc.pid
    if sys.platform == "win32":
        # taskkill /T kills the entire process tree.
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True)
    else:
        # Child was started in its own session (start_new_session=True), so it
        # is a process-group leader; kill the whole group.
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _run(cmd, shell, timeout):
    """Run a command, killing the whole process tree on timeout.

    Returns (stdout, stderr) as strings, or raises _RunError with a message.
    """
    kwargs = {}
    if sys.platform != "win32":
        # Put the child in its own process group so we can kill the tree.
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(
            cmd, shell=shell,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, **kwargs,
        )
    except Exception as e:
        raise _RunError(f"could not run: {e}")

    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        # Drain whatever partial output was captured before the kill.
        try:
            out, err = proc.communicate(timeout=2)
        except Exception:
            out, err = "", ""
        raise _RunError(f"timed out after {timeout}s (process killed)")

    return out.strip(), err.strip()


class _RunError(Exception):
    pass


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def run_python(code: str, timeout: int = 30) -> str:
    """Run a Python snippet and return its stdout (and any traceback)."""
    if not code or not code.strip():
        return "No code provided."
    try:
        out, err = _run(["python", "-c", code], shell=False, timeout=timeout)
    except _RunError as e:
        return _err(str(e))
    if err:
        return _err(f"exit non-zero\n{err}")
    return out if out else "(ran OK, no output)"


def run_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command and return its combined output."""
    if not command or not command.strip():
        return "No command provided."
    try:
        out, err = _run(command, shell=True, timeout=timeout)
    except _RunError as e:
        return _err(str(e))
    combined = out + ("\n" + err if err else "")
    if err:
        return _err(f"exit non-zero\n{combined or '(no output)'}")
    return combined if combined else "(ran OK, no output)"


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
