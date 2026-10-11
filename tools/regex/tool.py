import re


def tool(pattern: str, text: str, mode: str = "match", replacement: str = "") -> str:
    flags = re.DOTALL
    try:
        if mode == "match":
            matches = re.findall(pattern, text, flags)
            if not matches:
                return "No matches found."
            if len(matches) > 50:
                return f"{len(matches)} matches (showing first 50):\n" + "\n".join(str(m) for m in matches[:50])
            return f"{len(matches)} match(es):\n" + "\n".join(str(m) for m in matches)
        elif mode == "replace":
            result = re.sub(pattern, replacement, text, flags=flags)
            count = len(re.findall(pattern, text, flags))
            return f"Replaced {count} occurrence(s).\n\n{result}"
        else:
            return f"Unknown mode: {mode}. Use 'match' or 'replace'."
    except re.error as e:
        return f"Regex error: {e}"
