"""
Aggregated tool registry for terminal_ai.

Imports TOOLS from each genre subfolder and merges them into one dict.
Uses direct file-path imports so it works when loaded via
importlib.util.spec_from_file_location (no package context needed).
"""

import importlib.util
import os

_dir = os.path.dirname(os.path.abspath(__file__))

def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_dir, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

TOOLS = {}
TOOLS.update(_load("_agg_web", "web/web.py").TOOLS)
TOOLS.update(_load("_agg_files", "files/files.py").TOOLS)
TOOLS.update(_load("_agg_execution", "execution/execution.py").TOOLS)
TOOLS.update(_load("_agg_data", "data/data.py").TOOLS)
TOOLS.update(_load("_agg_media", "media/media.py").TOOLS)
TOOLS.update(_load("_agg_ask", "ask/ask.py").TOOLS)
