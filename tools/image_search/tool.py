from ddgs import DDGS


def tool(query, max_results=10):
    try:
        results = DDGS().images(query, max_results=max_results)
    except Exception as e:
        return f"Image search failed: {e}"

    if not results:
        return f"No image results found for: {query}"

    lines = [f"Image search: {query} ({len(results)} results)", ""]
    for i, r in enumerate(results, 1):
        title = r.get("title") or "(no title)"
        img = r.get("image") or r.get("thumbnail", "")
        src = r.get("source") or r.get("url", "")
        lines.append(f"{i}. {title}")
        lines.append(f"   image: {img}")
        if src:
            lines.append(f"   source: {src}")
    return "\n".join(lines)
