"""
Web tools for terminal_ai.
"""

import re
import urllib.request

try:
    from ddgs import DDGS
    _HAS_DDGS = True
except Exception:
    _HAS_DDGS = False


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
def search(query: str, max_results: int = 5) -> str:
    """Search the web (DuckDuckGo). Use for current facts, docs, or anything external."""
    if not _HAS_DDGS:
        return _err("ddgs package not installed (pip install ddgs)")
    if not query or not query.strip():
        return "No query provided."
    max_results = max(1, min(int(max_results), 10))
    try:
        results = DDGS().text(query.strip(), max_results=max_results)
    except Exception as e:
        return _err(f"search failed: {e}")
    if not results:
        return f"No results for: {query}"
    lines = [f"Results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '(no title)')}")
        if r.get("href"):
            lines.append(f"   URL: {r['href']}")
        body = (r.get("body") or "").strip()
        if body:
            lines.append(f"   {body[:300]}")
        lines.append("")
    return _clip("\n".join(lines).strip())


def http_get(url: str, max_chars: int = 8000) -> str:
    """Fetch a URL and return its body (text). Good for reading pages, APIs, raw files."""
    if not url:
        return "No URL provided."
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "terminal_ai/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1", "ignore")
        if "<" in text and ">" in text:
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
        return _clip(text, max_chars)
    except Exception as e:
        return _err(f"GET {url} failed: {e}")


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
    "search": {
        "description": "Search the web (DuckDuckGo) for current facts, docs, or external info.",
        "parameters": _p({"query": _s("The search query."),
                         "max_results": _i("Number of results (1-10, default 5)")},
                        ["query"]),
        "fn": search,
    },
    "http_get": {
        "description": "Fetch a URL and return its (cleaned) text content.",
        "parameters": _p({"url": _s("The URL to fetch."),
                         "max_chars": _i("Max characters to return (default 8000)")},
                        ["url"]),
        "fn": http_get,
    },
}
