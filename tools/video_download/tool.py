import os

def tool(url, output=None, format=None, audio=False, list=False, title=None, no_playlist=False):
    try:
        import yt_dlp
    except ImportError:
        return "yt-dlp is not installed. Run:  pip install yt-dlp"

    # Resolve output: a directory, or a full file path.
    if output and os.path.splitext(output)[1]:
        out_dir = os.path.dirname(output) or "."
        out_file = output
    else:
        out_dir = output or "downloads"
        out_file = None

    os.makedirs(out_dir, exist_ok=True)

    def build_opts():
        if out_file:
            outtmpl = out_file
        elif title:
            outtmpl = os.path.join(out_dir, f"{title}.%(ext)s")
        else:
            outtmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
        opts = {
            "outtmpl": outtmpl,
            "noplaylist": bool(no_playlist),
            "quiet": True,
            "noprogress": True,
            "nocheckcertif": True,
            "no_warnings": True,
        }
        if audio:
            opts["format"] = "bestaudio"
            opts["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        else:
            opts["format"] = format or "bestvideo+bestaudio/best"
        return opts

    # List mode: show formats, no download.
    if list:
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            lines = [f"Title: {info.get('title')}",
                     f"Duration: {info.get('duration') or '?'}s",
                     "Available formats:"]
            for f in info.get("formats", []):
                lines.append(f"  [{f.get('format_id')}] {f.get('ext')} "
                             f"{f.get('height') or '-'}p  "
                             f"{(f.get('filesize') or 0)/1e6:.1f}MB  {f.get('acodec') or 'none'}")
            return "\n".join(lines)
        except Exception as e:
            return f"Could not read formats for {url}: {e}"

    # Download mode.
    try:
        opts = build_opts()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = ydl.prepare_filename(info)
        if audio:
            # postprocessor rewrites the container to mp3; report that, drop the leftover source
            path = os.path.splitext(base)[0] + ".mp3"
            if os.path.exists(base) and os.path.getsize(base) == 0:
                os.remove(base)
        else:
            path = base
        size = os.path.getsize(path) if path and os.path.exists(path) else 0
        return f"Downloaded '{info.get('title')}' -> {path} ({size} bytes)"
    except Exception as e:
        return f"Download failed for {url}: {e}"
