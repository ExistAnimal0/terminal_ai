"""STT tool - transcribe an audio file to text using FasterWhisper.

The model is loaded once per size and cached in a module-level dict, so
repeated calls (and the /voice command in terminal_ai.py, which uses its own
cache) do not re-download or re-load the same model. The first use of a given
size downloads it from HuggingFace and caches it on disk.
"""
import os

# Work around a Windows OpenMP conflict: faster_whisper links both
# ctranslate2 (libiomp5md) and av (libomp), which clash at load time.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

_MODEL_CACHE = {}
_DEFAULT_MODEL = "base"


def _get_model(size=None):
    size = size or _DEFAULT_MODEL
    if size not in _MODEL_CACHE:
        from faster_whisper import WhisperModel
        _MODEL_CACHE[size] = WhisperModel(size, device="auto", compute_type="auto")
    return _MODEL_CACHE[size]


def tool(path, model=None, language=None):
    if not path:
        return "Error: 'path' is required."
    if not os.path.isfile(path):
        return f"Error: file not found: {path}"
    try:
        m = _get_model(model)
        segments, info = m.transcribe(path, language=language)
        text = " ".join(s.text for s in segments).strip()
    except Exception as e:
        return f"Error transcribing: {type(e).__name__}: {e}"
    if not text:
        return "No speech detected in the audio."
    lang = getattr(info, "language", "") or ""
    prefix = f"[{lang}] " if lang else ""
    return prefix + text
