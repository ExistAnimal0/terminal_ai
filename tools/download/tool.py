import os
import urllib.request

def tool(url, output=None):
    if not output:
        output = os.path.basename(url.split('?')[0]) or 'downloaded_file'
    d = os.path.dirname(output)
    if d:
        os.makedirs(d, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, output)
        size = os.path.getsize(output)
        return f"Downloaded {url} -> {output} ({size} bytes)"
    except Exception as e:
        return f"Download failed: {e}"
