#!/usr/bin/env python3
"""
Terminal AI Assistant - Ollama Edition (Streaming + Tools)
Uses the ollama Python library with token-by-token streaming output.
Auto-loads tools from the tools/ directory and feeds them to Ollama.
Requires: pip install ollama
"""

import sys
import os
import json
import time
import glob
import shutil
import importlib.util
import urllib.request
import urllib.error
import ollama
from datetime import datetime

# Config
MODEL = "orcarouter/Qwen3.8-27B-Uncensored:q3_K_S"
SYSTEM_PROMPT = (
    "You are Reesk, an assistant. You have to be professional and concise. Do not inflate anything. Do not exaggerate. Be realistic. Send short, understandable, correct phrases. Treat user with respect. Do not use unneeded filler words. Be snarky when appropriate. THINK FOR YOURSELF. USE TOOL CALLS. ALWAYS REPLY WITH CONTENT, NOT JUST THINKING. ALWAYS RETURN TO USER IF SOMETHING HAS GONE CATASTROPHICALLY WRONG. Your emails is reeskassistant@gmail.com"
    f"Today is {datetime.now().strftime('%Y-%m-%d')}."
)

def load_context_file():
    """Append reesk.md (project context) to the system prompt, if present."""
    base = os.getcwd()
    path = os.path.join(base, "reesk.md")
    if not os.path.isfile(path):
        return ""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            return ""
    return ""

def full_system_prompt():
    """System prompt plus the project context (reesk.md) and the current
    working directory, so the model knows where relative file paths resolve
    to. The context file is re-read each call so it tracks the working
    directory, including after /cd. Also appends the thinking-level
    prompt suffix if one is configured."""
    ctx = load_context_file()
    prompt = SYSTEM_PROMPT + (("\n\n" + ctx) if ctx else "")
    prompt += f"\n\nCurrent working directory: {os.getcwd()}"
    level = THINKING_LEVEL if isinstance(THINKING_LEVEL, bool) else str(THINKING_LEVEL).lower()
    if level in THINKING_LEVELS and THINKING_LEVELS[level]["prompt"]:
        prompt += "\n\n" + THINKING_LEVELS[level]["prompt"]
    return prompt

def estimate_context_tokens(messages):
    """Estimate total tokens in a message list (content + thinking + tool
    call args) using a chars/4 heuristic. Keeps the context bar accurate,
    since Ollama's streaming prompt_eval_count is unreliable (often None)."""
    total = 0
    for m in messages:
        content = m.get("content") or ""
        if content:
            total += max(0, len(content) // 4)
        thinking = m.get("thinking") or ""
        if thinking:
            total += max(0, len(thinking) // 4)
        for tc in (m.get("tool_calls") or []):
            func = tc.get("function", {})
            args = func.get("arguments", {}) or {}
            if isinstance(args, str):
                total += max(0, len(args) // 4)
            else:
                total += max(0, len(json.dumps(args)) // 4)
    return total

def load_token_log():
    """Load the persistent token log (list of per-turn token counts)."""
    try:
        with open(TOKEN_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def save_token_log(log):
    """Persist the token log to disk."""
    try:
        with open(TOKEN_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass


def filter_tokens_by_date(date_str):
    """Return token-log entries whose timestamp date matches date_str (YYYY-MM-DD)."""
    return [e for e in TOKEN_LOG if e.get("timestamp", "")[:10] == date_str]

def log_turn_tokens(content_tokens, thinking_tokens, total_tokens):
    """Append one turn's token counts to the log and save it."""
    global TOKEN_LOG
    TOKEN_LOG.append({
        "timestamp": datetime.now().isoformat(),
        "tokens": content_tokens,
        "thinking_tokens": thinking_tokens,
        "total": total_tokens,
    })
    save_token_log(TOKEN_LOG)

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")
SETTINGS_FILE = "settings.json"
TOKEN_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_log.json")
MAX_TOOL_ROUNDS = 50
MAX_CTX = 40000
THINKING_LEVEL = "basic"
THINKING_LEVELS = {
    "off":      {"think": False,     "prompt": ""},
    "low":      {"think": "low",     "prompt": ""},
    "basic":    {"think": "medium",  "prompt": "Don't think too hard."},
    "medium":   {"think": "medium",  "prompt": ""},
    "xmedium":  {"think": "medium",  "prompt": "Think carefully."},
    "high":     {"think": "high",   "prompt": ""},
    "max":      {"think": "high",   "prompt": "Think VERY carefully about everything."},
}
SESSION_TOKENS = 0
CTX_USED = 0
LAST_REAL_CTX = 0
CUR_LINE = 1
LINE_CHARS = 0

# Colors
class C:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    AI_TEXT = '\033[38;2;249;241;165m'
    TOOL = '\033[38;2;37;99;235m'
    TOOL_RESULT = '\033[38;2;128;0;128m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

def supports_color():
    if os.environ.get('NO_COLOR'):
        return False
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

USE_COLOR = supports_color()

def c(text, code):
    if USE_COLOR:
        return f"{code}{text}{C.RESET}"
    return text

def clear_terminal():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_status_block():
    """Print a compact status block (banner + key info) after clearing."""
    print(get_banner())
    print(c(f"  Working directory: {os.getcwd()}", C.DIM))
    print(c(f"  Model: {MODEL}", C.GREEN))
    if TOOLS:
        print(c(f"  Tools: {', '.join(TOOLS.keys())}", C.GREEN))
    print(c(f"  Thinking: {THINKING_LEVEL}", C.DIM))
    print(c(f"  Context: {CTX_USED}/{MAX_CTX} tokens", C.DIM))
    print()

# Tool Loading
TOOLS = {}
TOOLS_DEFS = []

def load_tools():
    """Scan tools/ for subdirectories. Supports two patterns:
    1. config.json + tool.py  (single tool per folder)
    2. __init__.py            (package exposing a TOOLS dict)
    Plus a top-level tools.py fallback (flat TOOLS dict).
    """
    base = os.path.dirname(os.path.abspath(__file__))
    tools_dir = os.path.join(base, "tools")
    if not os.path.isdir(tools_dir):
        return

    for entry in sorted(os.listdir(tools_dir)):
        tool_path = os.path.join(tools_dir, entry)
        if not os.path.isdir(tool_path):
            continue

        # Pattern 1: config.json + tool.py (single tool)
        config_file = os.path.join(tool_path, "config.json")
        tool_file = os.path.join(tool_path, "tool.py")
        if os.path.isfile(config_file) and os.path.isfile(tool_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                spec = importlib.util.spec_from_file_location(f"tool_{entry}", tool_file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                name = config.get("name", entry)
                TOOLS[name] = mod.tool
                TOOLS_DEFS.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": config.get("description", ""),
                        "parameters": config.get(
                            "parameters",
                            {"type": "object", "properties": {}}
                        )
                    }
                })
            except Exception as e:
                print(c(f"  [warn] Failed to load tool '{entry}': {e}", C.YELLOW))
            continue

        # Pattern 2: __init__.py (package with TOOLS dict)
        init_file = os.path.join(tool_path, "__init__.py")
        if os.path.isfile(init_file):
            try:
                spec = importlib.util.spec_from_file_location(
                    f"tools_{entry}", init_file,
                    submodule_search_locations=[tool_path]
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for name, cfg in mod.TOOLS.items():
                    if name in TOOLS:
                        continue
                    TOOLS[name] = cfg["fn"]
                    TOOLS_DEFS.append({
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": cfg.get("description", ""),
                            "parameters": cfg.get(
                                "parameters",
                                {"type": "object", "properties": {}}
                            )
                        }
                    })
            except Exception as e:
                print(c(f"  [warn] Failed to load package '{entry}': {e}", C.YELLOW))
            continue

    # Fallback: a single tools.py that registers many tools at once.
    # Expected shape:  TOOLS = { "name": {"description":..., "parameters":..., "fn": callable} }
    single = os.path.join(tools_dir, "tools.py")
    if os.path.isfile(single):
        try:
            spec = importlib.util.spec_from_file_location("tools_all", single)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for name, cfg in mod.TOOLS.items():
                if name in TOOLS:
                    continue  # folder-based tools win
                TOOLS[name] = cfg["fn"]
                TOOLS_DEFS.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": cfg.get("description", ""),
                        "parameters": cfg.get(
                            "parameters",
                            {"type": "object", "properties": {}}
                        )
                    }
                })
        except Exception as e:
            print(c(f"  [warn] Failed to load tools.py: {e}", C.YELLOW))

def execute_tool(name, args):
    """Run a tool by name. Always returns a string."""
    if name not in TOOLS:
        return f"Unknown tool: {name}"
    try:
        result = TOOLS[name](**args)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        return f"Tool '{name}' error: {e}"

def tool_args_display(name, args):
    """Compact display of tool args for the [tool] line. For write/edit tools
    the content strings can be huge, so show only a length summary instead of
    dumping the full payload."""
    if name == "write_file":
        content = args.get("content", "")
        parts = [f"path={args.get('path','')!r}", f"content={len(content)} chars"]
        if args.get("append"):
            parts.append("append")
        return "  ".join(parts)
    if name == "edit_file":
        find = args.get("find", "")
        replace = args.get("replace", "")
        return (f"path={args.get('path','')!r}  "
                f"find={len(find)} chars  replace={len(replace)} chars")
    return json.dumps(args)

# Ollama API

def ollama_chat_round(messages, leading_newline=False):
    """One streaming round via ollama.chat(). Returns:
    (tool_calls, content, thinking, token_count, context_used)
    token_count = content + thinking tokens. context_used includes thinking.
    If leading_newline is True, a blank line is printed before the first
    streamed token (used to separate a tool result from the next stream).
    """
    global LAST_REAL_CTX
    # Thinking level -> think parameter (bool or str).
    level = THINKING_LEVEL if isinstance(THINKING_LEVEL, bool) else str(THINKING_LEVEL).lower()
    if level in THINKING_LEVELS:
        think_param = THINKING_LEVELS[level]["think"]
    else:
        think_param = True

    tool_calls = []
    content_parts = []
    thinking_parts = []
    context_used = 0
    thinking_printed = False
    content_tokens = 0
    thinking_tokens = 0
    total_tokens = 0

    try:
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=TOOLS_DEFS if TOOLS_DEFS else None,
            think=think_param,
            options={
                "num_ctx": MAX_CTX,
                "temperature": 0.1
            },
            stream=True
        )

        stream_started = False

        for chunk in response:
            msg = chunk.message

            # Thinking
            think_token = msg.thinking if msg.thinking else ""
            if think_token:
                if leading_newline and not stream_started:
                    print()
                    stream_started = True
                thinking_parts.append(think_token)
                print(c(think_token, C.DIM), end="")
                sys.stdout.flush()
                thinking_printed = True

            # Normal response
            token = msg.content if msg.content else ""
            if token:
                if leading_newline and not stream_started:
                    print()
                    stream_started = True
                content_parts.append(token)
                if thinking_printed:
                    print("\n", end="")
                    thinking_printed = False
                print(c(token, C.AI_TEXT), end="")
                sys.stdout.flush()

            # Tool calls can arrive during streaming.
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": dict(tc.function.arguments)
                        }
                    })

            if chunk.done:
                # prompt_eval_count is Ollama's real prompt token count.
                # Record it so /ctx can show the true figure; fall back to
                # the chars/4 estimate only when it is None.
                if chunk.prompt_eval_count:
                    LAST_REAL_CTX = chunk.prompt_eval_count
                # Add this round's own thinking (chars/4) so the bar
                # reflects the true context size including all thinking.
                context_used = (chunk.prompt_eval_count or 0) + max(0, sum(len(t) for t in thinking_parts) // 4)
                # Real completion token count (content + thinking) from Ollama.
                total_tokens = chunk.eval_count if chunk.eval_count else (len(content_parts) + len(thinking_parts))
                thinking_tokens = len(thinking_parts)
                content_tokens = max(0, total_tokens - thinking_tokens)
                break

    except Exception as e:
        print(c(f"\n[ERROR] {e}", C.RED))
        return None, None, None, 0, 0, 0, 0

    return (
        tool_calls,
        "".join(content_parts),
        "".join(thinking_parts),
        content_tokens,
        thinking_tokens,
        total_tokens,
        context_used
    )

def check_ollama():
    """Verify Ollama is reachable and model is available."""
    try:
        result = ollama.list()
        models = [m.model for m in result.models]
        if MODEL in models:
            return True, f"Connected. Model '{MODEL}' is available."
        elif models:
            return False, f"Connected, but '{MODEL}' not found. Available: {', '.join(models)}"
        else:
            return False, "Connected, but no models installed. Run: ollama pull ..."
    except Exception as e:
        return False, f"Cannot reach Ollama ({e}). Is it running? Try: ollama serve"

# Save/Load helpers
def save_conversation(messages, history, filename=None):
    """Save conversation to a JSON file in the saves/ directory."""
    if not os.path.isdir(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conv_{timestamp}.json"

    filepath = os.path.join(SAVE_DIR, filename)
    data = {
        "model": MODEL,
        "saved_at": datetime.now().isoformat(),
        "messages": messages,
        "history": [list(h) for h in history]
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath

def load_conversation(filename):
    """Load a saved conversation. Returns (messages, history) or None."""
    filepath = os.path.join(SAVE_DIR, filename)
    if not os.path.isfile(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        messages = data["messages"]
        history = [tuple(h) for h in data["history"]]
        return messages, history
    except Exception:
        return None

def replay_conversation(messages):
    """Replay a saved conversation in the same visual style as a live chat
    (you> / ai> / [tool] / [result] lines), so /load shows the full
    conversation exactly as it originally appeared."""
    turns = []
    current = None
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        if role == "user":
            if current is not None:
                turns.append(current)
            current = {"user": m, "rest": []}
        else:
            if current is None:
                current = {"user": None, "rest": []}
            current["rest"].append(m)
    if current is not None:
        turns.append(current)

    for turn in turns:
        if turn["user"] is not None:
            print(c("you> ", C.BOLD + C.CYAN) + (turn["user"].get("content") or ""))
        if not turn["rest"]:
            continue
        print(c("ai>  ", C.AI_TEXT), end="")
        had_output = False
        for m in turn["rest"]:
            role = m.get("role")
            if role == "assistant":
                thinking = m.get("thinking") or ""
                content = m.get("content") or ""
                tool_calls = m.get("tool_calls") or []
                if thinking:
                    print(c(thinking, C.DIM), end="")
                    had_output = True
                if content:
                    if thinking:
                        print("\n", end="")
                    print(c(content, C.AI_TEXT), end="")
                    had_output = True
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args = func.get("arguments", {}) or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    print(c(f"\n  [tool] {name}  {tool_args_display(name, args)}", C.TOOL))
                    had_output = True
            elif role == "tool":
                content = m.get("content") or ""
                preview = content if len(content) <= 200 else content[:200] + "..."
                print(c(f"  [result] {preview}", C.TOOL_RESULT))
        if not had_output:
            print(c("  (no output)", C.YELLOW))
        print()

def list_saves():
    """List all saved conversations."""
    if not os.path.isdir(SAVE_DIR):
        return []
    files = sorted(glob.glob(os.path.join(SAVE_DIR, "conv_*.json")))
    return [os.path.basename(f) for f in files]

def settings_path():
    """Absolute path to settings.json (lives next to this script)."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, SETTINGS_FILE)

def load_settings():
    """Load settings.json. Returns a dict (empty if missing/invalid)."""
    path = settings_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_settings(settings):
    """Write settings to settings.json. Returns the path."""
    path = settings_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    return path

# Commands
COMMANDS = {
    "/help": "Show available commands.",
    "/clear": "Clear the terminal screen.",
    "/history": "Show conversation history.",
    "/info": "Show assistant info.",
    "/model": "Show current model.",
    "/tools": "List loaded tools.",
    "/save": "Save conversation to a file.",
    "/load": "Load a saved conversation.",
    "/saves": "List saved conversations.",
    "/theme": "Toggle color theme (on/off).",
    "/ctx": "Show context usage.",
    "/tokens": "Show token usage for a date (default today). Optional: /tokens YYYY-MM-DD.",
    "/ttl": "Show only content/thinking/total for a date (default today). Optional: /ttl YYYY-MM-DD.",
    "/compact": "Summarize all thinking blocks except the last one, then reprint the conversation.",
    "/rst": "Reset the conversation.",
    "/frst": "Reset the conversation and reload all tools.",
    "/cd": "Set the working directory (saved to settings.json).",
    "/files": "Open the current working directory in the file explorer.",
    "/think": "Set thinking level (off, low, basic, medium, xmedium, high, max).",
    "/exit": "Exit the assistant.",
    "/quit": "Exit the assistant.",
}

def get_banner():
    return f"""
{c("  +==========================================+", C.CYAN)}
{c("  |", C.CYAN)}   {c("  T E R M I N A L   A I   A S S I S T A N T  ", C.BOLD + C.WHITE)}   {c("|", C.CYAN)}
{c("  +==========================================+", C.CYAN)}
"""

def show_commands():
    """Print the command list."""
    print(c("\n-- Commands --------------------------", C.BOLD))
    for key, desc in COMMANDS.items():
        print(f"  {c(key, C.CYAN):<10} {desc}")
    print(c("  ----------------------------------------", C.BOLD))
    print(c("  Type anything else to chat with the AI.", C.DIM))

def handle_command(cmd, history, messages):
    """Handle a slash command. Returns (should_continue, new_messages)."""
    global CTX_USED, LAST_REAL_CTX, TOOLS, TOOLS_DEFS
    cmd = cmd.strip()

    if cmd == "/":
        show_commands()
        return True, messages

    cmd_lower = cmd.lower()
    cmd_parts = cmd_lower.split(None, 1)
    cmd_name = cmd_parts[0]
    cmd_arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

    if cmd_name in ("/exit", "/quit"):
        print(c("\nGoodbye!", C.GREEN))
        return False, messages
    elif cmd_name == "/clear":
        os.system('cls' if os.name == 'nt' else 'clear')
        print(get_banner())
        return True, messages
    elif cmd_name == "/help":
        show_commands()
        return True, messages
    elif cmd_name == "/history":
        if not history:
            print(c("  No history yet.", C.DIM))
        else:
            print(c("\n-- History ---------------------------", C.BOLD))
            for i, (q, a) in enumerate(history):
                print(f"  {c(f'[{i+1}]', C.DIM)} {c('Q:', C.YELLOW)} {q}")
                print(f"     {c('A:', C.GREEN)} {a}")
            print(c("  ----------------------------------------", C.BOLD))
        return True, messages
    elif cmd_name == "/info":
        print(c("\n-- Info ---------------------------------", C.BOLD))
        print(f"  {c('Name:', C.YELLOW)}  Reesk Terminal AI")
        print(f"  {c('Model:', C.YELLOW)} {MODEL}")
        print(f"  {c('Client:', C.YELLOW)} ollama Python library")
        print(f"  {c('Tools:', C.YELLOW)} {', '.join(TOOLS.keys()) if TOOLS else 'none'}")
        print(f"  {c('Started:', C.YELLOW)} {datetime.now().strftime('%H:%M:%S')}")
        print(c("  ----------------------------------------", C.BOLD))
        return True, messages
    elif cmd_name == "/model":
        print(c(f"  Current model: {MODEL}", C.GREEN))
        return True, messages
    elif cmd_name == "/tools":
        if not TOOLS:
            print(c("  No tools loaded.", C.DIM))
        else:
            print(c("\n-- Loaded Tools ------------------------", C.BOLD))
            for d in TOOLS_DEFS:
                fn = d["function"]
                print(f"  {c(fn['name'], C.CYAN):<12} {fn['description']}")
            print(c("  ----------------------------------------", C.BOLD))
        return True, messages
    elif cmd_name == "/save":
        if cmd_arg:
            filename = cmd_arg
            if not filename.endswith(".json"):
                filename += ".json"
            if not filename.startswith("conv_"):
                filename = f"conv_{filename}"
        else:
            filename = None
        if not history:
            print(c("  Nothing to save yet.", C.DIM))
            return True, messages
        filepath = save_conversation(messages, history, filename)
        print(c(f"  Saved to: {filepath}", C.GREEN))
        return True, messages
    elif cmd_name == "/load":
        if cmd_arg:
            # If the arg is a number, treat it as a 1-based index into the saves list.
            if cmd_arg.isdigit():
                idx = int(cmd_arg)
                saves = list_saves()
                if idx < 1 or idx > len(saves):
                    print(c(f"  Index {idx} out of range (1-{len(saves)}).", C.RED))
                    return True, messages
                filename = saves[idx - 1]
            else:
                filename = cmd_arg
            result = load_conversation(filename)
            if result is None:
                print(c(f"  Could not load '{filename}'.", C.RED))
                return True, messages
            new_messages, new_history = result
            CTX_USED = estimate_context_tokens(new_messages)
            LAST_REAL_CTX = 0
            clear_terminal()
            print_status_block()
            print(c(f"  Loaded '{filename}'.", C.GREEN))
            print()
            replay_conversation(new_messages)
            print()
            return True, new_messages
        else:
            saves = list_saves()
            if not saves:
                print(c("  No saved conversations found.", C.DIM))
            else:
                print(c("\n-- Saved Conversations -----------------", C.BOLD))
                for i, s in enumerate(saves):
                    print(f"  {c(f'[{i+1}]', C.DIM)} {s}")
                print(c("  ----------------------------------------", C.BOLD))
                print(c("  Use /load <index> or /load <filename> to load one.", C.DIM))
            return True, messages
    elif cmd_name == "/saves":
        saves = list_saves()
        if not saves:
            print(c("  No saved conversations found.", C.DIM))
        else:
            print(c("\n-- Saved Conversations -----------------", C.BOLD))
            for i, s in enumerate(saves):
                print(f"  {c(f'[{i+1}]', C.DIM)} {s}")
            print(c("  ----------------------------------------", C.BOLD))
        return True, messages
    elif cmd_name == "/ctx":
        # Prefer Ollama's real prompt token count; fall back to the
        # chars/4 estimate only when the real count is unavailable.
        shown = LAST_REAL_CTX if LAST_REAL_CTX > 0 else CTX_USED
        pct = (shown / MAX_CTX * 100) if MAX_CTX > 0 else 0
        bar_width = 30
        filled = int(bar_width * pct / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        if pct > 90:
            color = C.RED
        elif pct > 70:
            color = C.YELLOW
        else:
            color = C.GREEN
        print(c(f"\n  Context: {shown}/{MAX_CTX} tokens ({pct:.1f}%)", C.CYAN))
        print(c(f"  {bar}", color))
        print(c("  ----------------------------------------", C.BOLD))
        return True, messages
    elif cmd_name == "/compact":
        def _est_tokens(text):
            return max(1, len(text) // 4)
        think_idx = [i for i, m in enumerate(messages)
                     if m.get("role") == "assistant" and m.get("thinking")]
        if not think_idx:
            print(c("  No thinking blocks in this conversation.", C.DIM))
            return True, messages
        targets = think_idx[:-1] if len(think_idx) > 1 else []
        if not targets:
            print(c(f"  Only {len(think_idx)} thinking block(s). Nothing to compact.", C.DIM))
            return True, messages
        old_ctx = estimate_context_tokens(messages)
        print(c(f"  Compacting {len(targets)} thinking block(s) via model...", C.CYAN))
        if len(targets) > 20:
            print(c("  This may take a while.", C.CYAN))
        new_total = 0
        for n, i in enumerate(targets):
            t = messages[i]["thinking"]
            try:
                resp = ollama.chat(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": "SUMMARIZE THE THINKING BLOCK BELOW. KEEP ONLY KEY DECISIONS, CONCLUSIONS, AND IMPORTANT FACTS. REMOVE ALL STEP-BY-STEP REASONING. BE CONCISE. OUTPUT ONLY THE SUMMARY - NO PREAMBLE, NO EXPLANATION, NO META-COMMENTS."},
                        {"role": "user", "content": t}
                    ],
                    think="low",
                    options={"num_ctx": MAX_CTX, "temperature": 0.1}
                )
                summary = resp.message.content.strip()
                if summary:
                    messages[i]["thinking"] = summary
            except Exception as e:
                print(c(f"  [warn] block {n+1}/{len(targets)}: {e}", C.YELLOW))
            new_total += _est_tokens(messages[i]["thinking"])
            sys.stdout.write(f"\r  {n+1}/{len(targets)} compacted")
            sys.stdout.flush()
        print()
        new_ctx = estimate_context_tokens(messages)
        saved = max(0, old_ctx - new_ctx)
        CTX_USED = new_ctx
        LAST_REAL_CTX = 0
        clear_terminal()
        print_status_block()
        replay_conversation(messages)
        print()
        print(c(f"  Context: {old_ctx} -> {new_ctx} / {MAX_CTX}  ({saved} tokens freed)", C.CYAN))
        return True, messages
    elif cmd_name == "/rst":
        messages = [{"role": "system", "content": full_system_prompt()}]
        CTX_USED = 0
        LAST_REAL_CTX = 0
        clear_terminal()
        print_status_block()
        print(c("  Conversation reset. Context cleared.", C.GREEN))
        print()
        return True, messages
    elif cmd_name == "/frst":
        messages = [{"role": "system", "content": full_system_prompt()}]
        CTX_USED = 0
        LAST_REAL_CTX = 0
        TOOLS.clear()
        TOOLS_DEFS.clear()
        load_tools()
        clear_terminal()
        print_status_block()
        print(c("  Conversation reset. Tools reloaded.", C.GREEN))
        print()
        return True, messages
    elif cmd_name == "/cd":
        if not cmd_arg:
            print(c(f"\n  Working directory: {os.getcwd()}", C.CYAN))
            print(c("  Usage: /cd <path>  (any directory on the system; ~ and %vars% work)", C.DIM))
            print(c("  ----------------------------------------", C.BOLD))
            return True, messages
        target = os.path.expandvars(os.path.expanduser(cmd_arg))
        if not os.path.isabs(target):
            target = os.path.abspath(target)
        if not os.path.isdir(target):
            print(c(f"  Not a directory: {target}", C.RED))
            print(c("  ----------------------------------------", C.BOLD))
            return True, messages
        os.chdir(target)
        settings = load_settings()
        settings["working_directory"] = target
        save_settings(settings)
        messages[0]["content"] = full_system_prompt()
        print(c(f"  Working directory set to: {target}", C.GREEN))
        print(c(f"  Saved to: {settings_path()}", C.DIM))
        print(c("  ----------------------------------------", C.BOLD))
        return True, messages
    elif cmd_name == "/files":
        wd = os.getcwd()
        if os.name == 'nt':
            os.startfile(wd)
        elif os.uname().sysname == 'Darwin':
            os.system(f'open "{wd}"')
        else:
            os.system(f'xdg-open "{wd}"')
        print(c(f"  Opened: {wd}", C.GREEN))
        return True, messages
    elif cmd_name == "/think":
        global THINKING_LEVEL
        if not cmd_arg or cmd_arg.lower() not in THINKING_LEVELS:
            print(c(f"\n  Current thinking level: {THINKING_LEVEL}", C.CYAN))
            print(c("  Usage: /think <off|low|basic|medium|xmedium|high|max>", C.DIM))
            print(c("  ----------------------------------------", C.BOLD))
            return True, messages
        THINKING_LEVEL = cmd_arg.lower()
        messages[0]["content"] = full_system_prompt()
        print(c(f"\n  Thinking level set to: {THINKING_LEVEL}", C.GREEN))
        print(c("  ----------------------------------------", C.BOLD))
        return True, messages
    elif cmd_name == "/theme":
        global USE_COLOR
        USE_COLOR = not USE_COLOR
        print(c(f"  Color theme {'ON' if USE_COLOR else 'OFF'}.", C.GREEN))
        return True, messages
    elif cmd_name == "/tokens":
        if cmd_arg:
            target_date = cmd_arg
            try:
                datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                print(c(f"  Invalid date '{cmd_arg}'. Use YYYY-MM-DD (e.g. 2026-10-12).", C.RED))
                return True, messages
        else:
            target_date = datetime.now().strftime("%Y-%m-%d")
        entries = filter_tokens_by_date(target_date)
        if not entries:
            print(c(f"  No token data logged for {target_date}.", C.DIM))
            return True, messages
        label = "today" if target_date == datetime.now().strftime("%Y-%m-%d") else target_date
        print(c("\n-- Token Log ---------------------------", C.BOLD))
        print(c(f"  Date: {target_date} ({label})", C.DIM))
        print(c(f"  Turns logged: {len(entries)}", C.CYAN))
        for e in entries[-10:]:
            print(f"  {e.get('timestamp','?')}  content={e.get('tokens',0)}  thinking={e.get('thinking_tokens',0)}  total={e.get('total',0)}")
        sum_t = sum(e.get("tokens", 0) for e in entries)
        sum_th = sum(e.get("thinking_tokens", 0) for e in entries)
        sum_tot = sum(e.get("total", 0) for e in entries)
        print(c("  ----------------------------------------", C.BOLD))
        print(c(f"  Totals for {label}: content={sum_t}  thinking={sum_th}  total={sum_tot}", C.CYAN))
        return True, messages
    elif cmd_name == "/ttl":
        if cmd_arg:
            target_date = cmd_arg
            try:
                datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                print(c(f"  Invalid date '{cmd_arg}'. Use YYYY-MM-DD (e.g. 2026-10-12).", C.RED))
                return True, messages
        else:
            target_date = datetime.now().strftime("%Y-%m-%d")
        entries = filter_tokens_by_date(target_date)
        if not entries:
            print(c(f"  No token data for {target_date}.", C.DIM))
            return True, messages
        sum_t = sum(e.get("tokens", 0) for e in entries)
        sum_th = sum(e.get("thinking_tokens", 0) for e in entries)
        sum_tot = sum(e.get("total", 0) for e in entries)
        print(c(f"  content={sum_t}  thinking={sum_th}  total={sum_tot}", C.CYAN))
        return True, messages
    else:
        print(c(f"  Unknown command: {cmd}. Type / for a list.", C.RED))
        return True, messages

def main():
    global CTX_USED, TOKEN_LOG
    # Load the persistent token log.
    TOKEN_LOG = load_token_log()
    # Apply a saved working directory, if set.
    settings = load_settings()
    wd = settings.get("working_directory", "")
    if wd and os.path.isdir(wd):
        os.chdir(wd)

    print(get_banner())
    print(c(f"  Working directory: {os.getcwd()}", C.DIM))

    # Load tools
    load_tools()
    if TOOLS:
        print(c(f"  Loaded {len(TOOLS)} tool(s): {', '.join(TOOLS.keys())}", C.GREEN))
    else:
        print(c("  No tools found in tools/ directory.", C.DIM))

    # Check Ollama connection
    ok, msg = check_ollama()
    if ok:
        print(c(f"  {msg}", C.GREEN))
    else:
        print(c(f"  {msg}", C.RED))
        print(c("  You can still type /help or /exit. Chat will fail until Ollama is up.\n", C.DIM))

    print(c("  Type a message to chat, or / for commands.", C.DIM))
    print(c("  Type /exit to quit.\n", C.DIM))

    # Build message history for Ollama (chat format)
    messages = [{"role": "system", "content": full_system_prompt()}]
    history = []

    while True:
        try:
            user_input = input(c("you> ", C.BOLD + C.CYAN))
        except (EOFError, KeyboardInterrupt):
            print(c("\nGoodbye!", C.GREEN))
            break

        if not user_input.strip():
            continue

        if user_input.startswith("/"):
            continue_flag, messages = handle_command(user_input, history, messages)
            if not continue_flag:
                break
            if messages and messages[0]["role"] == "system":
                history = [(messages[i]["content"], messages[i+1]["content"])
                          for i in range(1, len(messages) - 1, 2)
                          if messages[i]["role"] == "user"
                          and i + 1 < len(messages)
                          and messages[i+1]["role"] == "assistant"]
            continue

        # Send to Ollama with streaming + tool loop
        pre_turn_count = len(messages)
        messages.append({"role": "user", "content": user_input})
        start = time.time()

        print(c("ai>  ", C.AI_TEXT), end="")
        is_error = False
        final_text = ""
        final_thinking = ""
        total_tokens = 0
        turn_content_tokens = 0
        turn_thinking_tokens = 0

        stopped = False
        content = None
        thinking = None
        for round_num in range(MAX_TOOL_ROUNDS):
            tool_results_this_round = 0
            current_round_has_assistant_msg = False
            try:
                tool_calls, content, thinking, content_tokens, thinking_tokens, round_total, ctx = ollama_chat_round(
                    messages, leading_newline=(round_num > 0)
                )
            except KeyboardInterrupt:
                stopped = True
                break
            if tool_calls is None:
                is_error = True
                break
            total_tokens += round_total
            turn_content_tokens += content_tokens
            turn_thinking_tokens += thinking_tokens
            if ctx:
                global CTX_USED
                CTX_USED = ctx
            if not tool_calls:
                final_text = content
                final_thinking = thinking
                break
            # Model wants to call tools - execute them.
            # Append the assistant message (with tool_calls) FIRST so the
            # tool results are correctly linked to the calls.
            assistant_msg = {
                "role": "assistant",
                "content": content if content else "",
                "tool_calls": tool_calls
            }
            if thinking:
                assistant_msg["thinking"] = thinking
            messages.append(assistant_msg)
            current_round_has_assistant_msg = True
            try:
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    args = func.get("arguments", {}) or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    print(c(f"\n  [tool] {name}  {tool_args_display(name, args)}", C.TOOL))
                    result = execute_tool(name, args)
                    preview = result if len(result) <= 200 else result[:200] + "..."
                    print(c(f"  [result] {preview}", C.TOOL_RESULT))
                    messages.append({
                        "role": "tool",
                        "content": result
                    })
                    tool_results_this_round += 1
            except KeyboardInterrupt:
                stopped = True
                break

        elapsed = time.time() - start

        if stopped:
            print()
            print(c("  [stopped]", C.YELLOW))
            partial_content = content or ""
            partial_thinking = thinking or ""
            if not current_round_has_assistant_msg:
                # Stopped mid-stream: keep the partial assistant message.
                if partial_content or partial_thinking:
                    am = {"role": "assistant", "content": partial_content}
                    if partial_thinking:
                        am["thinking"] = partial_thinking
                    messages.append(am)
                else:
                    # Nothing generated yet - revert the user message.
                    del messages[pre_turn_count:]
            else:
                # Stopped mid-tool-execution: trim unexecuted tool_calls.
                for m in reversed(messages[pre_turn_count:]):
                    if m.get("role") == "assistant" and m.get("tool_calls"):
                        m["tool_calls"] = m["tool_calls"][:tool_results_this_round]
                        break
            CTX_USED = estimate_context_tokens(messages)
            if total_tokens > 0:
                log_turn_tokens(turn_content_tokens, turn_thinking_tokens, total_tokens)
            print()
        elif not is_error:
            print()
            if final_text:
                display_text = final_text
            elif final_thinking:
                display_text = final_thinking
                print(c("  (model produced thinking but no answer or tool call)", C.YELLOW))
            else:
                display_text = ""
            if display_text:
                messages.append({"role": "assistant", "content": display_text})
                history.append((user_input, display_text))
            CTX_USED = estimate_context_tokens(messages)
            tps = (total_tokens / elapsed) if elapsed > 0 else 0
            print(c(f"  ({elapsed:.1f}s, {tps:.1f} tk/s, {total_tokens} tokens)", C.DIM))
            if total_tokens > 0:
                log_turn_tokens(turn_content_tokens, turn_thinking_tokens, total_tokens)
            if not final_text and not final_thinking:
                print(c("  (model returned no output)", C.YELLOW))
        print()

if __name__ == "__main__":
    main()
