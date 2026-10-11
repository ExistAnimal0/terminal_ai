import urllib.request
from pathlib import Path


def tool(url: str, output: str = "") -> str:
    """Download an image from a URL to a local file."""
    if not url:
        return "Error: url is required"

    # Default filename: last path segment, or "download"
    if not output:
        name = url.split("/")[-1].split("?")[0] or "download"
        output = name

    dest = Path(output)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return f"Saved {dest} ({len(data)} bytes)"
    except Exception as e:
        return f"Error: {e}"
