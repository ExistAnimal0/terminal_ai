"""
Data / text tools for terminal_ai.
"""

import re
import json
import math
import time
import base64
import hashlib
import random
import difflib
import urllib.parse
from datetime import datetime


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
def calculator(expression: str) -> str:
    """Evaluate a math expression, e.g. '2*(3+4)/5'. Supports + - * / ** % // and math funcs."""
    if not expression or not expression.strip():
        return "No expression provided."
    allowed = re.compile(r"^[\d\s+\-*/%().,eE^]+$")
    expr = expression.strip().replace("^", "**")
    if not allowed.match(expr):
        return _err("only digits and + - * / ** % // ( ) . allowed")
    try:
        val = eval(expr, {"__builtins__": {}}, {"abs": abs, "round": round,
                                                "sqrt": math.sqrt, "sin": math.sin,
                                                "cos": math.cos, "tan": math.tan,
                                                "log": math.log, "exp": math.exp,
                                                "floor": math.floor, "ceil": math.ceil,
                                                "pi": math.pi, "e": math.e})
        return f"{expression} = {val}"
    except Exception as e:
        return _err(f"could not evaluate: {e}")


def json_parse(text: str) -> str:
    """Validate/pretty-print a JSON string. Returns the formatted JSON or the parse error."""
    if not text or not text.strip():
        return "No JSON provided."
    try:
        data = json.loads(text)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return _err(f"invalid JSON: {e}")


def text_stats(text: str) -> str:
    """Count characters, words, lines, and sentences in a text."""
    if text is None:
        text = ""
    words = re.findall(r"\S+", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    return (f"chars: {len(text)}\n"
            f"words: {len(words)}\n"
            f"lines: {len(text.splitlines())}\n"
            f"sentences: {len(sentences)}")


def base64_codec(text: str, mode: str = "encode") -> str:
    """Encode or decode base64. mode is 'encode' or 'decode'."""
    if not text:
        return "No text provided."
    try:
        if mode == "decode":
            return base64.b64decode(text).decode("utf-8", "replace")
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    except Exception as e:
        return _err(f"base64 {mode} failed: {e}")


def hash_text(text: str, algo: str = "sha256") -> str:
    """Hash a string. algo: md5, sha1, sha256, sha512."""
    if not text:
        return "No text provided."
    algo = algo.lower()
    if algo not in hashlib.algorithms_available:
        return _err(f"unknown algo '{algo}'. Try md5, sha1, sha256, sha512.")
    return f"{algo}({text!r}) = {hashlib.new(algo, text.encode('utf-8')).hexdigest()}"


def url_parse(url: str) -> str:
    """Break a URL into scheme, host, path, query params."""
    if not url:
        return "No URL provided."
    if not re.match(r"^https?://", url):
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(p.query)
    lines = [f"scheme: {p.scheme}", f"host: {p.netloc}", f"path: {p.path or '(none)'}"]
    if params:
        lines.append("query params:")
        for k, v in params.items():
            lines.append(f"  {k} = {', '.join(v)}")
    return "\n".join(lines)


def random_pick(items: str, count: int = 1) -> str:
    """Pick random item(s) from a comma-separated list."""
    if not items or not items.strip():
        return "No items provided."
    pool = [x.strip() for x in items.split(",") if x.strip()]
    if not pool:
        return _err("empty list")
    count = max(1, int(count))
    if count > len(pool):
        picks = pool[:]
        random.shuffle(picks)
    else:
        picks = random.sample(pool, count)
    return " | ".join(picks)


def convert_units(value: float, unit_from: str, unit_to: str) -> str:
    """Convert between common units (length, mass, temperature, data, time)."""
    length = {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000, "in": 0.0254,
              "ft": 0.3048, "mi": 1609.344}
    mass = {"mg": 1e-6, "g": 0.001, "kg": 1, "t": 1000, "oz": 0.0283495, "lb": 0.453592}
    data = {"bit": 1/8, "B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    time_u = {"ms": 0.001, "s": 1, "min": 60, "h": 3600, "d": 86400}
    try:
        v = float(value)
    except Exception:
        return _err(f"'{value}' is not a number")
    uf, ut = unit_from.lower(), unit_to.lower()
    if uf in {"c", "f", "k"} and ut in {"c", "f", "k"}:
        t = v
        if uf == "c":
            t = v if ut == "c" else (v * 9/5 + 32 if ut == "f" else v + 273.15)
        elif uf == "f":
            t = (v - 32) * 5/9 if ut == "c" else (v - 32) * 5/9 + 273.15 if ut == "k" else v
        elif uf == "k":
            t = v - 273.15 if ut == "c" else (v - 273.15) * 9/5 + 32 if ut == "f" else v
        return f"{v} {uf.upper()} = {t:.6g} {ut.upper()}"
    for table in (length, mass, data, time_u):
        if uf in table and ut in table:
            return f"{v} {uf} = {v * table[uf] / table[ut]:.6g} {ut}"
    return _err(f"unknown or mismatched units: {uf} -> {ut}")


def diff_text(a: str, b: str) -> str:
    """Show line-by-line differences between two texts."""
    la, lb = a.splitlines(), b.splitlines()
    lines = []
    for line in difflib.unified_diff(la, lb, "a", "b", lineterm=""):
        lines.append(line)
    if not lines:
        return "No differences."
    return _clip("\n".join(lines))


def get_datetime() -> str:
    """Return the current local date and time."""
    now = datetime.now()
    return f"{now.strftime('%Y-%m-%d %H:%M:%S')}  (weekday: {now.strftime('%A')})"


def sleep(seconds: float) -> str:
    """Wait for N seconds (0-60)."""
    s = max(0, min(float(seconds), 60))
    time.sleep(s)
    return f"Slept {s}s"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def _p(props, required=None):
    return {"type": "object", "properties": props, "required": required or []}


def _s(desc):
    return {"type": "string", "description": desc}


def _i(desc):
    return {"type": "integer", "description": desc}


def _f(desc):
    return {"type": "number", "description": desc}


def _b(desc):
    return {"type": "boolean", "description": desc}


TOOLS = {
    "calculator": {
        "description": "Evaluate a math expression (supports + - * / ** % and math funcs).",
        "parameters": _p({"expression": _s("e.g. '2*(3+4)/5' or 'sqrt(16)'")},
                        ["expression"]),
        "fn": calculator,
    },
    "json_parse": {
        "description": "Validate and pretty-print a JSON string.",
        "parameters": _p({"text": _s("JSON string to validate.")}, ["text"]),
        "fn": json_parse,
    },
    "text_stats": {
        "description": "Count characters, words, lines, and sentences in a text.",
        "parameters": _p({"text": _s("Text to analyze.")}, ["text"]),
        "fn": text_stats,
    },
    "base64_codec": {
        "description": "Encode or decode base64. mode is 'encode' or 'decode'.",
        "parameters": _p({"text": _s("Text to process."),
                         "mode": _s("'encode' or 'decode' (default encode)")},
                        ["text"]),
        "fn": base64_codec,
    },
    "hash_text": {
        "description": "Hash a string (md5, sha1, sha256, sha512).",
        "parameters": _p({"text": _s("Text to hash."),
                         "algo": _s("Algorithm (default sha256)")},
                        ["text"]),
        "fn": hash_text,
    },
    "url_parse": {
        "description": "Break a URL into scheme, host, path, and query params.",
        "parameters": _p({"url": _s("URL to parse.")}, ["url"]),
        "fn": url_parse,
    },
    "random_pick": {
        "description": "Pick random item(s) from a comma-separated list.",
        "parameters": _p({"items": _s("Comma-separated list of items."),
                         "count": _i("How many to pick (default 1)")},
                        ["items"]),
        "fn": random_pick,
    },
    "convert_units": {
        "description": "Convert between length, mass, temperature, data, or time units.",
        "parameters": _p({"value": _f("Numeric value."),
                         "unit_from": _s("Source unit, e.g. 'km', 'kg', 'c', 'MB', 'h'."),
                         "unit_to": _s("Target unit.")},
                        ["value", "unit_from", "unit_to"]),
        "fn": convert_units,
    },
    "diff_text": {
        "description": "Show line-by-line differences between two texts.",
        "parameters": _p({"a": _s("First text."), "b": _s("Second text.")},
                        ["a", "b"]),
        "fn": diff_text,
    },
    "get_datetime": {
        "description": "Return the current local date, time, and weekday.",
        "parameters": _p({}),
        "fn": get_datetime,
    },
    "sleep": {
        "description": "Wait for N seconds (0-60).",
        "parameters": _p({"seconds": _f("Seconds to wait (0-60)")}, ["seconds"]),
        "fn": sleep,
    },
}
