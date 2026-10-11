import csv
import os


def tool(path: str, action: str = "read", filter_col: str = "", filter_val: str = "", max_rows: int = 50) -> str:
    if not os.path.isfile(path):
        return f"File not found: {path}"

    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            cols = reader.fieldnames or []
    except Exception as e:
        return f"Failed to parse CSV: {e}"

    if not rows:
        return "CSV is empty (no data rows)."

    if action == "read":
        rows = rows[:max_rows]
        lines = [", ".join(cols)]
        for r in rows:
            lines.append(", ".join(str(r.get(c, "")) for c in cols))
        suffix = f" (showing {len(rows)} of {len(rows)})" if len(rows) == max_rows else ""
        return f"Columns: {', '.join(cols)}\nRows: {len(rows)}{suffix}\n\n" + "\n".join(lines)

    elif action == "filter":
        if not filter_col:
            return "filter_col is required for action='filter'."
        filtered = [r for r in rows if r.get(filter_col, "") == filter_val]
        if not filtered:
            return f"No rows where {filter_col} == '{filter_val}'."
        filtered = filtered[:max_rows]
        lines = [", ".join(cols)]
        for r in filtered:
            lines.append(", ".join(str(r.get(c, "")) for c in cols))
        return f"{len(filtered)} matching row(s) ({filter_col} == '{filter_val}')\n\n" + "\n".join(lines)

    elif action == "summarize":
        lines = [f"Total rows: {len(rows)}", f"Columns: {', '.join(cols)}"]
        for c in cols:
            values = [r.get(c, "") for r in rows]
            numeric = []
            for v in values:
                try:
                    numeric.append(float(v))
                except (ValueError, TypeError):
                    pass
            if numeric and len(numeric) == len(values):
                lines.append(f"  {c}: min={min(numeric)}, max={max(numeric)}, mean={sum(numeric)/len(numeric):.2f}")
            else:
                unique = set(values)
                lines.append(f"  {c}: {len(unique)} unique value(s)" + (f" (top: {', '.join(list(unique)[:5])})" if len(unique) <= 10 else ""))
        return "\n".join(lines)

    else:
        return f"Unknown action: {action}. Use 'read', 'filter', or 'summarize'."
