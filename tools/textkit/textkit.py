#!/usr/bin/env python3
"""
textkit - Professional Text Toolkit
===================================
A single-file CLI utility for common text operations.
No external dependencies. Python 3.8+.

Usage:
  python textkit.py <command> [options]

Commands:
  case      Convert text between naming conventions
  clean     Normalize and clean whitespace
  stats     Text statistics (chars, words, lines, sentences)
  hash      Hash text (md5, sha1, sha256, sha512)
  base64    Encode or decode base64
  url       Percent-encode or decode a string
  slug      Generate a URL-safe slug
  password  Generate a secure random password
  json      Pretty-print or minify JSON
  diff      Line-by-line diff of two inputs
"""

import argparse
import base64
import hashlib
import json
import math
import os
import re
import secrets
import string
import sys
import unicodedata
from pathlib import Path


# ─── Output helpers ────────────────────────────────────────────────────────────

def _dim(s: str) -> str:
    """Wrap in dim ANSI (respects NO_COLOR)."""
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return s
    return f"\033[2m{s}\033[0m"


def _bold(s: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return s
    return f"\033[1m{s}\033[0m"


def _cyan(s: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return s
    return f"\033[36m{s}\033[0m"


def _green(s: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return s
    return f"\033[32m{s}\033[0m"


def _red(s: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return s
    return f"\033[31m{s}\033[0m"


def _yellow(s: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return s
    return f"\033[33m{s}\033[0m"


def print_kv(label: str, value: str, width: int = 14) -> None:
    """Print a label/value pair, aligned."""
    print(f"  {_dim(label.ljust(width))} {value}")


def print_header(title: str) -> None:
    """Print a section header."""
    print(f"\n{_bold(title)}")
    print(_dim("-" * 40))


def error(msg: str) -> None:
    print(_red(f"  error: {msg}"), file=sys.stderr)
    sys.exit(1)


# ─── Text helpers ──────────────────────────────────────────────────────────────

def split_words(text: str) -> list[str]:
    """Split text into words on non-alphanumeric boundaries."""
    return re.findall(r"[A-Za-z0-9]+", text)


def to_camel(text: str) -> str:
    words = split_words(text)
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def to_pascal(text: str) -> str:
    words = split_words(text)
    return "".join(w.capitalize() for w in words)


def to_snake(text: str) -> str:
    words = split_words(text)
    return "_".join(w.lower() for w in words)


def to_kebab(text: str) -> str:
    words = split_words(text)
    return "-".join(w.lower() for w in words)


def to_constant(text: str) -> str:
    words = split_words(text)
    return "_".join(w.upper() for w in words)


def to_slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text.strip().lower())
    return text.strip("-")


def clean_text(text: str, collapse: bool = True, strip: bool = True) -> str:
    if collapse:
        text = re.sub(r"\s+", " ", text)
    if strip:
        text = text.strip()
    return text


def count_sentences(text: str) -> int:
    return len(re.findall(r"[.!?]+(?:\s|$)", text))


def reading_time(words: int, wpm: int = 200) -> str:
    secs = words / wpm * 60
    if secs < 60:
        return f"{secs:.0f}s"
    mins, s = divmod(int(secs), 60)
    if mins >= 60:
        h, m = divmod(mins, 60)
        return f"{h}h {m}m"
    return f"{mins}m {s}s"


# ─── Commands ──────────────────────────────────────────────────────────────────

def cmd_case(args: argparse.Namespace) -> None:
    text = _read_input(args)
    if not text:
        error("no input text")
    converters = {
        "camel": to_camel,
        "pascal": to_pascal,
        "snake": to_snake,
        "kebab": to_kebab,
        "constant": to_constant,
        "slug": to_slug,
    }
    result = converters[args.style](text)
    if args.json:
        print(json.dumps({"input": text, "style": args.style, "output": result}))
    else:
        print_header(f"Case conversion -> {args.style}")
        print_kv("input", text[:80] + ("…" if len(text) > 80 else ""))
        print_kv("output", _cyan(result))


def cmd_clean(args: argparse.Namespace) -> str:
    text = _read_input(args)
    if not text:
        error("no input text")
    result = clean_text(text, collapse=not args.no_collapse, strip=not args.no_strip)
    if args.json:
        print(json.dumps({"input": text, "output": result}))
    else:
        print_header("Clean whitespace")
        print_kv("before", f"{len(text)} chars")
        print_kv("after", f"{len(result)} chars")
        print_kv("result", _cyan(result[:200] + ("…" if len(result) > 200 else "")))
    return result


def cmd_stats(args: argparse.Namespace) -> None:
    text = _read_input(args)
    if not text:
        error("no input text")
    chars = len(text)
    words = len(text.split())
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    sentences = count_sentences(text)
    rt = reading_time(words)
    if args.json:
        print(json.dumps({
            "chars": chars, "words": words, "lines": lines,
            "sentences": sentences, "reading_time": rt,
        }))
    else:
        print_header("Text statistics")
        print_kv("characters", str(chars))
        print_kv("words", str(words))
        print_kv("lines", str(lines))
        print_kv("sentences", str(sentences))
        print_kv("reading time", _cyan(rt))


def cmd_hash(args: argparse.Namespace) -> None:
    text = _read_input(args)
    if not text:
        error("no input text")
    h = hashlib.new(args.algo, text.encode("utf-8"))
    digest = h.hexdigest()
    if args.json:
        print(json.dumps({"algo": args.algo, "digest": digest}))
    else:
        print_header(f"Hash ({args.algo.upper()})")
        print_kv("input", text[:60] + ("…" if len(text) > 60 else ""))
        print_kv("digest", _cyan(digest))


def cmd_base64(args: argparse.Namespace) -> None:
    text = _read_input(args)
    if not text:
        error("no input text")
    if args.mode == "encode":
        result = base64.b64encode(text.encode("utf-8")).decode("ascii")
        label = "encoded"
    else:
        try:
            result = base64.b64decode(text.encode("ascii")).decode("utf-8")
        except Exception as e:
            error(f"decode failed: {e}")
        label = "decoded"
    if args.json:
        print(json.dumps({"mode": args.mode, "output": result}))
    else:
        print_header(f"Base64 {label}")
        print_kv("input", text[:60] + ("…" if len(text) > 60 else ""))
        print_kv(label, _cyan(result[:120] + ("…" if len(result) > 120 else "")))


def cmd_url(args: argparse.Namespace) -> None:
    from urllib.parse import quote, unquote
    text = _read_input(args)
    if not text:
        error("no input text")
    if args.mode == "encode":
        result = quote(text, safe="")
        label = "encoded"
    else:
        result = unquote(text)
        label = "decoded"
    if args.json:
        print(json.dumps({"mode": args.mode, "output": result}))
    else:
        print_header(f"URL {label}")
        print_kv("input", text[:80] + ("…" if len(text) > 80 else ""))
        print_kv(label, _cyan(result[:120] + ("…" if len(result) > 120 else "")))


def cmd_slug(args: argparse.Namespace) -> None:
    text = _read_input(args)
    if not text:
        error("no input text")
    result = to_slug(text)
    if args.json:
        print(json.dumps({"input": text, "slug": result}))
    else:
        print_header("Slug")
        print_kv("input", text[:80] + ("…" if len(text) > 80 else ""))
        print_kv("slug", _cyan(result))


def cmd_password(args: argparse.Namespace) -> None:
    length = args.length
    if length < 4:
        error("length must be >= 4")
    if length > 256:
        error("length must be <= 256")
    alphabet = string.ascii_letters + string.digits
    if args.symbols:
        alphabet += "!@#$%^&*()-_=+[]{}|;:,.<>/?~"
    if args.no_ambiguous:
        alphabet = "".join(c for c in alphabet if c not in "Il1O0oBbSsGg")
    pwd = "".join(secrets.choice(alphabet) for _ in range(length))
    if args.json:
        print(json.dumps({"length": length, "password": pwd}))
    else:
        print_header(f"Password ({length} chars)")
        print_kv("length", str(length))
        print_kv("charset", f"{len(alphabet)} chars" + (" +symbols" if args.symbols else ""))
        print_kv("password", _cyan(pwd))


def cmd_json(args: argparse.Namespace) -> None:
    text = _read_input(args)
    if not text:
        error("no input text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        error(f"invalid JSON: {e}")
    if args.mode == "pretty":
        result = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        result = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if args.json:
        print(json.dumps({"mode": args.mode, "output": result}))
    else:
        print_header(f"JSON {args.mode}")
        print(_cyan(result))


def cmd_diff(args: argparse.Namespace) -> None:
    a = _read_input(args, "text_a", "file_a")
    b = _read_input(args, "text_b", "file_b")
    if not a and not b:
        error("no input (provide --text-a / --text-b or --file-a / --file-b)")
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    import difflib
    diff = list(difflib.unified_diff(a_lines, b_lines, fromfile=args.label_a or "a",
                                    tofile=args.label_b or "b", lineterm=""))
    if not diff:
        if args.json:
            print(json.dumps({"identical": True, "diff": []}))
        else:
            print_header("Diff")
            print(_green("  (no differences)"))
        return
    if args.json:
        print(json.dumps({"identical": False, "diff": diff}))
    else:
        print_header("Diff")
        for line in diff:
            if line.startswith("+"):
                print(_green(line))
            elif line.startswith("-"):
                print(_red(line))
            elif line.startswith("@@"):
                print(_yellow(line))
            else:
                print(_dim(line))


# ─── Input resolution ──────────────────────────────────────────────────────────

def _read_input(args: argparse.Namespace, text_attr: str = "text", file_attr: str = "file") -> str:
    """Resolve input from a text attribute, a file attribute, or stdin."""
    t = getattr(args, text_attr, None)
    if t:
        return t
    f = getattr(args, file_attr, None)
    if f:
        p = Path(f)
        if not p.exists():
            error(f"file not found: {f}")
        return p.read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


# ─── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="textkit",
        description="Professional Text Toolkit - a single-file CLI for common text operations.",
        epilog=(
            "Examples:\n"
            "  textkit.py case --style snake 'HelloWorld'\n"
            "  textkit.py stats --text 'The quick brown fox'\n"
            "  textkit.py hash --algo sha256 --text 'hello'\n"
            "  textkit.py base64 --mode encode --text 'hello world'\n"
            "  textkit.py slug --text 'Hello, World! (2025)'\n"
            "  textkit.py password --length 24 --symbols\n"
            "  textkit.py json --mode pretty --file config.json\n"
            "  textkit.py diff --file-a old.txt --file-b new.txt\n"
            "\nAll commands accept --json for machine-readable output.\n"
            "Pipe input:  echo 'text' | textkit.py stats\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # case
    sp = sub.add_parser("case", help="Convert text between naming conventions")
    sp.add_argument("--style", required=True,
                    choices=["camel", "pascal", "snake", "kebab", "constant", "slug"])
    sp.add_argument("--text", help="Input text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_case)

    # clean
    sp = sub.add_parser("clean", help="Normalize and clean whitespace")
    sp.add_argument("--text", help="Input text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--no-collapse", action="store_true", help="Don't collapse whitespace")
    sp.add_argument("--no-strip", action="store_true", help="Don't strip edges")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_clean)

    # stats
    sp = sub.add_parser("stats", help="Text statistics")
    sp.add_argument("--text", help="Input text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_stats)

    # hash
    sp = sub.add_parser("hash", help="Hash text")
    sp.add_argument("--algo", default="sha256",
                    choices=["md5", "sha1", "sha256", "sha512"])
    sp.add_argument("--text", help="Input text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_hash)

    # base64
    sp = sub.add_parser("base64", help="Encode or decode base64")
    sp.add_argument("--mode", default="encode", choices=["encode", "decode"])
    sp.add_argument("--text", help="Input text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_base64)

    # url
    sp = sub.add_parser("url", help="Percent-encode or decode a string")
    sp.add_argument("--mode", default="encode", choices=["encode", "decode"])
    sp.add_argument("--text", help="Input text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_url)

    # slug
    sp = sub.add_parser("slug", help="Generate a URL-safe slug")
    sp.add_argument("--text", help="Input text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_slug)

    # password
    sp = sub.add_parser("password", help="Generate a secure random password")
    sp.add_argument("--length", type=int, default=16, help="Password length (4-256)")
    sp.add_argument("--symbols", action="store_true", help="Include symbols")
    sp.add_argument("--no-ambiguous", action="store_true",
                    help="Exclude ambiguous chars (Il1O0oBbSsGg)")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_password)

    # json
    sp = sub.add_parser("json", help="Pretty-print or minify JSON")
    sp.add_argument("--mode", default="pretty", choices=["pretty", "minify"])
    sp.add_argument("--text", help="Input JSON text")
    sp.add_argument("--file", help="Read input from file")
    sp.add_argument("--json", action="store_true", help="Wrap in JSON envelope")
    sp.set_defaults(func=cmd_json)

    # diff
    sp = sub.add_parser("diff", help="Line-by-line diff of two inputs")
    sp.add_argument("--text-a", help="First text")
    sp.add_argument("--file-a", help="First file")
    sp.add_argument("--text-b", help="Second text")
    sp.add_argument("--file-b", help="Second file")
    sp.add_argument("--label-a", default="a", help="Label for first input")
    sp.add_argument("--label-b", default="b", help="Label for second input")
    sp.add_argument("--json", action="store_true", help="JSON output")
    sp.set_defaults(func=cmd_diff)

    return p


def main() -> None:
    # Fix Windows console encoding (cp850 can't handle unicode)
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
