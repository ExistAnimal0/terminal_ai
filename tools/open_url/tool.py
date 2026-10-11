import webbrowser

def tool(url: str) -> str:
    """Open a URL in the default browser."""
    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return f"Opened in browser: {url}"
    except Exception as e:
        return f"Error opening {url}: {e}"
