"""
Media analysis tools for terminal_ai.
Uses ollama.chat with a vision-capable model to analyze images and video.
The Python SDK accepts file paths directly in the images array (no base64 needed).
"""

import os
import subprocess
import tempfile
import shutil

import ollama

MODEL = "orcarouter/Qwen3.8-27B-Uncensored:q3_K_S"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff", ".ico"}
VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv"}



def _err(msg):
    return f"Error: {msg}"


def _clip(text, n=6000):
    text = str(text)
    return text if len(text) <= n else text[:n] + f"\n... [truncated, {len(text)} chars total]"


def _resolve(path):
    """Resolve a relative path against the current working directory."""
    if not os.path.isabs(path):
        return os.path.join(os.getcwd(), path)
    return path


def _ask(prompt, image_paths):
    """Send a prompt + image path(s) to the model. Returns the response text."""
    messages = [{"role": "user", "content": prompt, "images": image_paths}]
    response = ollama.chat(
        model=MODEL,
        messages=messages,
        options={"num_ctx": 40000, "temperature": 0.1},
    )
    return response["message"]["content"]


def _extract_frames(video_path, count=1):
    """Extract frames from a video using ffmpeg. Returns list of frame file paths."""
    frames = []
    tmpdir = tempfile.mkdtemp(prefix="media_frames_")
    for i in range(count):
        out = os.path.join(tmpdir, f"frame_{i}.png")
        # Seek to evenly spaced positions
        if count == 1:
            cmd = ["ffmpeg", "-y", "-ss", "5", "-i", video_path,
                   "-frames:v", "1", out]
        else:
            interval = max(1, 25 * count)
            cmd = ["ffmpeg", "-y", "-i", video_path,
                   "-vf", f"select='not(mod(n\\,{interval}))'",
                   "-vsync", "vfr", "-frames:v", str(count),
                   os.path.join(tmpdir, "frames_%03d.png")]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
        except Exception:
            pass
        if count == 1:
            if os.path.isfile(out):
                frames.append(out)
        else:
            for f in sorted(os.listdir(tmpdir)):
                if f.startswith("frames_"):
                    frames.append(os.path.join(tmpdir, f))
    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)
    return frames


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def analyze_image(path: str, prompt: str = "Describe this image in detail.") -> str:
    """Analyze an image file using the vision model. Supports png, jpg, gif, webp, bmp, svg, tiff."""
    if not path:
        return "No file path provided."
    path = _resolve(path)
    if not os.path.isfile(path):
        return _err(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in IMAGE_EXTS:
        return _err(f"Not an image file (got '{ext}'). Supported: {', '.join(sorted(IMAGE_EXTS))}")
    try:
        result = _ask(prompt, [path])
        return _clip(result)
    except Exception as e:
        return _err(f"Model call failed: {e}")


def analyze_video(path: str, prompt: str = "Describe what is shown in this video.", frames: int = 3) -> str:
    """Analyze a video by extracting frames and sending them to the vision model. Requires ffmpeg."""
    if not path:
        return "No file path provided."
    path = _resolve(path)
    if not os.path.isfile(path):
        return _err(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in VIDEO_EXTS:
        return _err(f"Not a video file (got '{ext}'). Supported: {', '.join(sorted(VIDEO_EXTS))}")
    frame_paths = _extract_frames(path, max(1, min(int(frames), 8)))
    if not frame_paths:
        return _err("Could not extract any frames. Is ffmpeg installed?")
    try:
        result = _ask(prompt, frame_paths)
        return _clip(result)
    except Exception as e:
        return _err(f"Model call failed: {e}")


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
    "analyze_image": {
        "description": "Analyze an image file (png/jpg/gif/webp/bmp/svg/tiff) using the vision model.",
        "parameters": _p(
            {"path": _s("Path to the image file."),
             "prompt": _s("What to ask about the image (default: describe it).")},
            ["path"],
        ),
        "fn": analyze_image,
    },
    "analyze_video": {
        "description": "Analyze a video file by extracting frames and sending them to the vision model. Requires ffmpeg.",
        "parameters": _p(
            {"path": _s("Path to the video file."),
             "prompt": _s("What to ask about the video (default: describe it)."),
             "frames": _i("Number of frames to extract (1-8, default 3).")},
            ["path"],
        ),
        "fn": analyze_video,
    },
}
