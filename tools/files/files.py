"""
File tools for terminal_ai.
"""

import os
import re


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
def read_file(path: str, max_chars: int = 8000) -> str:
    """Read a text file and return its contents."""
    if not path:
        return "No path provided."
    if not os.path.isfile(path):
        return _err(f"not a file: {path}")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return _clip(f.read(), max_chars)
    except Exception as e:
        return _err(f"could not read {path}: {e}")


def write_file(path: str, content: str, append: bool = False) -> str:
    """Write text to a file (creates parent dirs). Set append=true to append instead of overwrite."""
    if not path:
        return "No path provided."
    try:
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        mode = "a" if append else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"{'Appended to' if append else 'Wrote'} {path} ({len(content)} chars)"
    except Exception as e:
        return _err(f"could not write {path}: {e}")


def list_dir(path: str = ".") -> str:
    """List files and folders in a directory."""
    if not os.path.isdir(path):
        return _err(f"not a directory: {path}")
    try:
        entries = sorted(os.listdir(path))
        lines = [f"{path}/  ({len(entries)} entries)\n"]
        for e in entries:
            full = os.path.join(path, e)
            if os.path.isdir(full):
                lines.append(f"  [dir]  {e}/")
            else:
                lines.append(f"  [file] {e}  ({os.path.getsize(full)} bytes)")
        return _clip("\n".join(lines))
    except Exception as e:
        return _err(f"could not list {path}: {e}")


def find_files(pattern: str, path: str = ".", max_results: int = 50) -> str:
    """Recursively find files matching a glob pattern (e.g. '*.py')."""
    if not pattern:
        return "No pattern provided."
    if not os.path.isdir(path):
        return _err(f"not a directory: {path}")
    matches = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv"}]
        for fn in files:
            if re.match(pattern, fn) or (pattern.startswith("*") and fn.endswith(pattern[1:])):
                matches.append(os.path.join(root, fn))
                if len(matches) >= max_results:
                    break
        if len(matches) >= max_results:
            break
    if not matches:
        return f"No files matching '{pattern}' under {path}"
    return _clip(f"{len(matches)} match(es) for '{pattern}':\n" + "\n".join(matches))


def rename_file(old_path: str, new_name: str) -> str:
    """Rename a file (or folder). new_name is the new file/folder name in the same directory."""
    if not old_path:
        return "No path provided."
    if not new_name:
        return "No new name provided."
    if not os.path.exists(old_path):
        return _err(f"not found: {old_path}")
    new_path = os.path.join(os.path.dirname(os.path.abspath(old_path)), new_name)
    if os.path.exists(new_path):
        return _err(f"target already exists: {new_path}")
    try:
        os.rename(old_path, new_path)
        return f"Renamed {old_path} -> {new_path}"
    except Exception as e:
        return _err(f"could not rename: {e}")


def edit_file(path: str, find: str, replace: str) -> str:
    """Edit a file's contents by replacing the first occurrence of 'find' with 'replace'."""
    if not path:
        return "No path provided."
    if not os.path.isfile(path):
        return _err(f"not a file: {path}")
    if not find:
        return "No 'find' text provided."
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
        if find not in original:
            return _err(f"text not found in {path}: {find!r}")
        updated = original.replace(find, replace, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
        return f"Edited {path} (replaced 1 occurrence)"
    except Exception as e:
        return _err(f"could not edit {path}: {e}")


def delete_file(path: str) -> str:
    """Delete a file or folder."""
    if not path:
        return "No path provided."
    if not os.path.exists(path):
        return _err(f"not found: {path}")
    try:
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
            return f"Deleted folder {path}"
        else:
            os.remove(path)
            return f"Deleted {path}"
    except Exception as e:
        return _err(f"could not delete {path}: {e}")


def create_folder(path: str) -> str:
    """Create a directory (including any missing parent directories)."""
    if not path:
        return "No path provided."
    path = os.path.abspath(path)
    if os.path.isdir(path):
        return _err(f"directory already exists: {path}")
    try:
        os.makedirs(path, exist_ok=True)
        return f"Created folder: {path}"
    except Exception as e:
        return _err(f"could not create {path}: {e}")


def move_file(src: str, dst: str) -> str:
    """Move (or copy) a file/folder to a new path. dst is the full destination path."""
    if not src:
        return "No source provided."
    if not dst:
        return "No destination provided."
    if not os.path.exists(src):
        return _err(f"source not found: {src}")
    dst = os.path.abspath(dst)
    dst_dir = os.path.dirname(dst)
    if dst_dir and not os.path.isdir(dst_dir):
        return _err(f"destination directory not found: {dst_dir}")
    if os.path.exists(dst):
        return _err(f"destination already exists: {dst}")
    try:
        import shutil
        if os.path.isdir(src):
            shutil.move(src, dst)
        else:
            shutil.move(src, dst)
        return f"Moved {src} -> {dst}"
    except Exception as e:
        return _err(f"could not move: {e}")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def _p(props, required=None):
    return {"type": "object", "properties": props, "required": required or []}


def _s(desc):
    return {"type": "string", "description": desc}


def _i(desc):
    return {"type": "integer", "description": desc}


def _b(desc):
    return {"type": "boolean", "description": desc}


TOOLS = {
    "read_file": {
        "description": "Read a text file and return its contents.",
        "parameters": _p({"path": _s("File path."),
                         "max_chars": _i("Max characters (default 8000)")},
                        ["path"]),
        "fn": read_file,
    },
    "write_file": {
        "description": "Write text to a file (creates parent dirs). append=true to append.",
        "parameters": _p({"path": _s("File path."),
                         "content": _s("Text to write."),
                         "append": _b("Append instead of overwrite (default false)")},
                        ["path", "content"]),
        "fn": write_file,
    },
    "list_dir": {
        "description": "List files and folders in a directory.",
        "parameters": _p({"path": _s("Directory path (default current dir)")}, ["path"]),
        "fn": list_dir,
    },
    "find_files": {
        "description": "Recursively find files matching a glob pattern like '*.py'.",
        "parameters": _p({"pattern": _s("Glob pattern, e.g. '*.md'."),
                         "path": _s("Root directory to search (default current dir)."),
                         "max_results": _i("Max matches (default 50)")},
                        ["pattern"]),
        "fn": find_files,
    },
    "rename_file": {
        "description": "Rename a file or folder (stays in the same directory).",
        "parameters": _p({"old_path": _s("Current file/folder path."),
                         "new_name": _s("New file/folder name.")},
                        ["old_path", "new_name"]),
        "fn": rename_file,
    },
    "edit_file": {
        "description": "Edit a file's contents by replacing the first occurrence of 'find' with 'replace'.",
        "parameters": _p({"path": _s("File path."),
                         "find": _s("Exact text to find."),
                         "replace": _s("Text to replace it with.")},
                        ["path", "find", "replace"]),
        "fn": edit_file,
    },
    "delete_file": {
        "description": "Delete a file or folder.",
        "parameters": _p({"path": _s("File/folder path to delete.")}, ["path"]),
        "fn": delete_file,
    },
    "move_file": {
        "description": "Move a file or folder to a new path.",
        "parameters": _p({"src": _s("Source file/folder path."),
                         "dst": _s("Destination path.")},
                        ["src", "dst"]),
        "fn": move_file,
    },
    "create_folder": {
        "description": "Create a directory (including missing parent directories).",
        "parameters": _p({"path": _s("Folder path to create.")},
                        ["path"]),
        "fn": create_folder,
    },
}
