import json
import math
import os

MEM_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "memory.json")
EMBED_MODEL = "nomic-embed-text"
SIM_THRESHOLD = 0.55


def _load():
    if os.path.exists(MEM_FILE):
        with open(MEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(mem):
    with open(MEM_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)


def _embed(text):
    """Embed text via Ollama nomic-embed-text. Returns list of floats or None."""
    try:
        import ollama
        client = ollama.Client()
        result = client.embed(model=EMBED_MODEL, input=text)
        return result["embeddings"][0]
    except Exception:
        return None


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _val(entry):
    """Extract the string value from a memory entry (dict or plain string)."""
    return entry["value"] if isinstance(entry, dict) else entry


def tool(action, key=None, value=None, query=None):
    mem = _load()

    if action == "store":
        if not key:
            return "No key provided for store."
        if value is None:
            return "No value provided for store."
        emb = _embed(f"{key}: {value}")
        mem[key] = {"value": value, "embedding": emb}
        _save(mem)
        note = f" (embedded, {len(emb)} dims)" if emb else " (no embedding - Ollama unavailable)"
        return f"Stored '{key}' ({len(value)} chars){note}."

    elif action == "get":
        if not key:
            return "No key provided for get."
        if key in mem:
            return f"{key} is: {_val(mem[key])}"
        return f"No memory for '{key}'."

    elif action == "list":
        if not mem:
            return "Memory is empty."
        lines = [f"  {k} ({len(_val(v))} chars)" for k, v in mem.items()]
        return f"{len(mem)} entries:\n" + "\n".join(lines)

    elif action == "search":
        if not query:
            return "No query provided for search."

        q_emb = _embed(query)
        if q_emb:
            scored = []
            for k, v in mem.items():
                emb = v.get("embedding") if isinstance(v, dict) else None
                if emb and len(emb) == len(q_emb):
                    sim = _cosine(q_emb, emb)
                    if sim >= SIM_THRESHOLD:
                        scored.append((sim, k, _val(v)))
            scored.sort(key=lambda x: -x[0])
            if scored:
                lines = [f"  {k} is: {val} (similarity {s:.2f})" for s, k, val in scored]
                return f"{len(scored)} match(es):\n" + "\n".join(lines)
            return f"No matches for '{query}'."

        # Fallback: substring search when Ollama is down
        q = query.lower()
        hits = [
            f"  {k} is: {_val(v)}"
            for k, v in mem.items()
            if q in k.lower() or q in _val(v).lower()
        ]
        if hits:
            return f"{len(hits)} match(es) (substring fallback):\n" + "\n".join(hits)
        return f"No matches for '{query}'."

    elif action == "delete":
        if not key:
            return "No key provided for delete."
        if key in mem:
            del mem[key]
            _save(mem)
            return f"Deleted '{key}'."
        return f"Key '{key}' not found."

    else:
        return f"Unknown action: {action}. Use store, get, list, search, or delete."
