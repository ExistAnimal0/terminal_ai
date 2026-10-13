"""
Interactive menu tool for terminal_ai.
Presents options with arrow-key navigation and a free-text 'custom' option.
"""

import sys
import os


# ---------------------------------------------------------------------------
# Key reading (cross-platform)
# ---------------------------------------------------------------------------
def _read_key_windows():
    """Read one keypress on Windows. Returns (char, ext_code_or_None)."""
    import msvcrt
    ch = msvcrt.getwch()
    if ch == '\x00':
        ext = msvcrt.getwch()
        return ('\x00', ext)
    return (ch, None)


def _read_key_linux(fd):
    """Read one keypress on Linux (terminal already in raw mode)."""
    ch = os.read(fd, 1)
    if ch == b'\x1b':
        seq = os.read(fd, 2)
        return ('\x00', seq[1:2].decode() if len(seq) >= 2 else '')
    return (ch.decode(), None)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------
def ask(question: str, options: str, allow_custom: bool = False) -> str:
    """
    Show an interactive menu in the terminal.
    - Arrow up/down to navigate
    - Enter to select
    - 'custom' option (if enabled) lets the user type a free-form answer
    - Ctrl+C cancels
    """
    opts = [o.strip() for o in options.split(',') if o.strip()]
    if not opts:
        return "No options provided."

    if allow_custom:
        opts.append("custom")

    n = len(opts)
    is_windows = (os.name == 'nt')

    # Print the question header
    print(f"\n  {question}")
    print("  " + "-" * 36)
    sys.stdout.flush()

    selected = 0
    first_render = True

    def render():
        nonlocal first_render
        if not first_render:
            # Move cursor back up to the first option line
            sys.stdout.write(f"\033[{n}A")
        first_render = False
        for i, opt in enumerate(opts):
            if i == selected:
                line = f"  \033[1m> {opt}\033[0m"
            else:
                line = f"    {opt}"
            sys.stdout.write(f"\r\033[K{line}\n")
        sys.stdout.flush()

    render()

    # --- Key loop ---
    if is_windows:
        import msvcrt
        while True:
            ch, ext = _read_key_windows()
            # Arrow keys may arrive as \x00+ext OR as a plain char,
            # depending on the terminal. Handle both.
            key = ext if ch == '\x00' else ch
            if key in ('H', 'M'):
                selected = (selected - 1) % n
                render()
            elif key in ('P', 'M'):
                selected = (selected + 1) % n
                render()
            elif ch == '\r':
                break
            elif ch == '\x03':
                print()
                return "cancelled"
    else:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch, ext = _read_key_linux(fd)
                if ch == '\x00':
                    if ext == 'A':
                        selected = (selected - 1) % n
                        render()
                    elif ext == 'B':
                        selected = (selected + 1) % n
                        render()
                elif ch in ('\r', '\n'):
                    break
                elif ch == '\x03':
                    print()
                    return "cancelled"
        finally:
            termios.tcsetattr(fd, termios.TCSADOWN, old)

    choice = opts[selected]

    if choice == "custom":
        print("  Type your answer: ", end='')
        sys.stdout.flush()
        answer = input()
        print()
        return answer.strip() if answer.strip() else "(empty)"
    else:
        print(f"  Selected: {choice}")
        return choice


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def _p(props, required=None):
    return {"type": "object", "properties": props, "required": required or []}


def _s(desc):
    return {"type": "string", "description": desc}


def _b(desc):
    return {"type": "boolean", "description": desc}


TOOLS = {
    "ask": {
        "description": (
            "Present an interactive menu in the terminal. "
            "User navigates with arrow up/down and presses Enter to select. "
            "A 'custom' option at the bottom lets them type a free-form answer. "
            "Use this when you need the user to pick from a list or provide input."
        ),
        "parameters": _p(
            {
                "question": _s("The question/prompt to display above the menu."),
                "options": _s("Comma-separated list of options, e.g. 'yes,no,maybe'."),
                "allow_custom": _b("If true, add a 'custom' option so the user can type their own answer. Default true."),
            },
            ["question", "options"],
        ),
        "fn": ask,
    },
}
