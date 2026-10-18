"""textkit tool - wraps the textkit.py CLI for the terminal AI tool system."""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "textkit.py"


def tool(command: str) -> str:
    """Run a textkit subcommand.

    Args:
        command: The subcommand and flags as a single string.
                 e.g. 'case --style snake --text HelloWorld'
    """
    if not command or not command.strip():
        return "error: empty command"

    # Split the command string into args (respects quotes)
    import shlex
    try:
        args = shlex.split(command)
    except ValueError:
        return f"error: could not parse command: {command!r}"

    if not args:
        return "error: no subcommand given"

    cmd = [sys.executable, str(SCRIPT)] + args

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return "error: textkit timed out (15s)"
    except Exception as e:
        return f"error: {e}"

    out = result.stdout.strip()
    err = result.stderr.strip()

    if result.returncode != 0:
        return f"error: {err or out or 'exit ' + str(result.returncode)}"

    # Strip ANSI codes for clean tool output
    import re
    out = re.sub(r"\033\[[0-9;]*m", "", out)
    return out
