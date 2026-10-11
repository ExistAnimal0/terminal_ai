import os
import re
import fnmatch

def tool(pattern, path='.', file_pattern='*', max_results=50):
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"Invalid regex: {e}"

    results = []
    for root, dirs, files in os.walk(path):
        for f in files:
            if file_pattern and file_pattern != '*' and not fnmatch.fnmatch(f, file_pattern):
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, 'r', encoding='utf-8', errors='replace') as fh:
                    for i, line in enumerate(fh, 1):
                        if rx.search(line):
                            results.append(f"{fp}:{i}: {line.rstrip()}")
                            if len(results) >= max_results:
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    if not results:
        return f"No matches for /{pattern}/ under {path} (files: {file_pattern})"
    return f"{len(results)} match(es) for /{pattern}/ under {path}:\n" + "\n".join(results)
