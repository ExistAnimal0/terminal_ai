"""
Sub-agent tool for terminal_ai.

Spawns sub-agents that run on the SAME model and SAME context window as the
main agent, with the SAME tool set. Sub-agents (and the main agent) can talk
to each other through a shared in-memory message bus.

Actions:
  spawn   - create a sub-agent with a task.            (task)
  run     - run ONE sub-agent for N tool-rounds.       (agent_id, rounds)
  run_all - run MANY sub-agents in PARALLEL (threads). (agent_ids, rounds)
  send    - post a message onto the shared bus.        (agent_id, message, to)
  read    - read bus messages addressed to an agent.   (agent_id)
  status  - peek at a sub-agent's state without running. (agent_id)
  list    - list all active sub-agents.
  kill    - remove a sub-agent.                         (agent_id)
  clear   - clear the message bus.

Sub-agents can call this same tool (action=send / read) to communicate, so a
coordinator can spawn several agents and let them exchange notes. run_all
executes them concurrently on a thread pool, so several agents work at once.

Shared state (AGENTS, BUS, locks, tool cache) is anchored to a single
sys.modules module so that every load of this file - under whatever name the
app or a sub-agent uses - shares the SAME in-memory state. Without this, the
app's copy and a sub-agent's copy would be different objects and the bus would
never line up.
"""

import os
import re
import sys
import json
import time
import types
import threading
import importlib.util
from concurrent.futures import ThreadPoolExecutor

import ollama

# --- locate the app so we can mirror its config and tool set -------------
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))          # tools/subagent
_BASE = os.path.dirname(_TOOLS_DIR)                              # tools/
_APP = os.path.dirname(_BASE)                                    # terminal_ai/
_APP_PY = os.path.join(_APP, "terminal_ai.py")

# --- model + context (kept in sync with the main agent) ------------------
def _read_app_config():
    model = "orcarouter/Qwen3.8-27B-Uncensored:q3_K_S"
    max_ctx = 40000
    try:
        txt = open(_APP_PY, encoding="utf-8").read()
        m = re.search(r'^MODEL\s*=\s*["\']([^"\']+)', txt, re.M)
        if m:
            model = m.group(1)
        m = re.search(r'^MAX_CTX\s*=\s*(\d+)', txt, re.M)
        if m:
            max_ctx = int(m.group(1))
    except Exception:
        pass
    return model, max_ctx

MODEL, MAX_CTX = _read_app_config()

# --- shared state, anchored to ONE module so all loads share it ----------
_STATE_NAME = "reesk_subagent_state"
if _STATE_NAME in sys.modules:
    _state = sys.modules[_STATE_NAME]
else:
    _state = types.ModuleType(_STATE_NAME)
    _state.AGENTS = {}          # id -> {id, name, task, messages, status, created, sent}
    _state.BUS = []            # [{from, to, text, ts}]
    _state._counter = [0]
    _state._bus_lock = threading.Lock()
    _state._load_lock = threading.Lock()
    _state._tool_cache = {"loaded": False, "tools": {}, "defs": []}
    sys.modules[_STATE_NAME] = _state

AGENTS = _state.AGENTS
BUS = _state.BUS
_counter = _state._counter
_bus_lock = _state._bus_lock
_load_lock = _state._load_lock
_tool_cache = _state._tool_cache

# --- tool discovery (mirrors load_tools in terminal_ai.py) ---------------
def _load_spec(name, path, search=None):
    spec = importlib.util.spec_from_file_location(name, path)
    if search:
        spec.submodule_search_locations = [search]
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def _load_all_tools():
    """Re-scan tools/ and return (TOOLS_dict, TOOLS_DEFS_list). Cached + locked."""
    with _load_lock:
        if _tool_cache["loaded"]:
            return _tool_cache["tools"], _tool_cache["defs"]

        tools, defs = {}, []

        def add(name, fn, desc, params):
            if name in tools:
                return
            tools[name] = fn
            defs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params or {"type": "object", "properties": {}},
                },
            })

        if os.path.isdir(_BASE):
            for entry in sorted(os.listdir(_BASE)):
                p = os.path.join(_BASE, entry)
                if not os.path.isdir(p):
                    continue
                cfg_f = os.path.join(p, "config.json")
                tool_f = os.path.join(p, "tool.py")
                init_f = os.path.join(p, "__init__.py")
                try:
                    if os.path.isfile(cfg_f) and os.path.isfile(tool_f):
                        with open(cfg_f, encoding="utf-8") as f:
                            cfg = json.load(f)
                        mod = _load_spec("subagent_tool_" + entry, tool_f)
                        add(cfg.get("name", entry), mod.tool,
                            cfg.get("description", ""), cfg.get("parameters"))
                    elif os.path.isfile(init_f):
                        mod = _load_spec("subagent_pkg_" + entry, init_f, p)
                        for name, c in (mod.TOOLS or {}).items():
                            add(name, c["fn"], c.get("description", ""),
                                c.get("parameters"))
                except Exception:
                    continue

        single = os.path.join(_BASE, "tools.py")
        if os.path.isfile(single):
            try:
                mod = _load_spec("subagent_flat", single)
                for name, c in (mod.TOOLS or {}).items():
                    add(name, c["fn"], c.get("description", ""), c.get("parameters"))
            except Exception:
                pass

        _tool_cache["loaded"] = True
        _tool_cache["tools"] = tools
        _tool_cache["defs"] = defs
        return tools, defs

def _exec_tool(name, args, tools):
    if name not in tools:
        return f"Unknown tool: {name}"
    try:
        result = tools[name](**args)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        return f"Tool '{name}' error: {e}"

def _new_id(name):
    _counter[0] += 1
    return f"agent_{_counter[0]}_{(name or 'sub').replace(' ', '_')}"

def _subagent_system(task):
    parts = [
        "You are a sub-agent of Reesk, a terminal AI assistant. Be concise, "
        "professional, and to the point. You have the same tools as the main "
        "agent and the same context window.",
        "You can communicate with the main agent and other sub-agents using the "
        "'subagent' tool: action='send' to post a message, action='read' to read "
        "messages from others. Use it to share findings, ask questions, or "
        "coordinate. When your task is complete, state your result clearly.",
    ]
    reesk = os.path.join(_APP, "reesk.md")
    if os.path.isfile(reesk):
        try:
            parts.append(open(reesk, encoding="utf-8").read())
        except Exception:
            pass
    parts.append(f"Current working directory: {os.getcwd()}")
    parts.append(f"Your task: {task}")
    return "\n\n".join(parts)

def _run_agent(agent, rounds, tools, defs):
    """Run a sub-agent for up to `rounds` tool-rounds. Returns final text.
    Safe to call from multiple threads: each agent owns its own messages list."""
    client = ollama.Client()
    msgs = agent["messages"]
    last = ""
    for _ in range(max(1, rounds)):
        try:
            resp = client.chat(
                model=MODEL,
                messages=msgs,
                tools=defs if defs else None,
                options={"num_ctx": MAX_CTX, "temperature": 0.1},
            )
        except Exception as e:
            agent["status"] = f"error: {e}"
            break
        msg = resp.get("message", {})
        tcs = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        if content:
            last = content
        if not tcs:
            agent["status"] = "done"
            break
        am = {"role": "assistant", "content": content, "tool_calls": tcs}
        if msg.get("thinking"):
            am["thinking"] = msg["thinking"]
        msgs.append(am)
        for tc in tcs:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result = _exec_tool(name, args, tools)
            msgs.append({"role": "tool", "content": result})
        agent["messages"] = msgs
    return last

# --- the tool ------------------------------------------------------------
def tool(action="list", task="", name="", agent_id="", agent_ids="",
         rounds=10, message="", to="all"):
    tools, defs = _load_all_tools()

    if action == "spawn":
        if not task or not task.strip():
            return "spawn needs a 'task'."
        aid = _new_id(name)
        AGENTS[aid] = {
            "id": aid,
            "name": name or "sub",
            "task": task.strip(),
            "messages": [
                {"role": "system", "content": _subagent_system(task.strip())},
                {"role": "user", "content": task.strip()},
            ],
            "status": "idle",
            "created": time.strftime("%H:%M:%S"),
            "sent": [],
        }
        return (f"Spawned {aid} (model={MODEL}, ctx={MAX_CTX}). "
                f"Run it with action='run' (or 'run_all' for parallel).")

    if action == "run":
        agent = AGENTS.get(agent_id)
        if not agent:
            return f"No sub-agent '{agent_id}'. See action='list'."
        agent["status"] = "running"
        final = _run_agent(agent, rounds, tools, defs)
        sent = list(agent["sent"])
        out = [f"[{agent_id}] status={agent['status']}"]
        if final:
            out.append(f"result: {final}")
        if sent:
            out.append("posted to bus: " + " | ".join(sent))
        return "\n".join(out)

    if action == "run_all":
        ids = [x.strip() for x in (agent_ids or "").split(",") if x.strip()]
        if not ids:
            return "run_all needs 'agent_ids' (comma-separated)."
        missing = [i for i in ids if i not in AGENTS]
        if missing:
            return f"Unknown agent_id(s): {', '.join(missing)}. See action='list'."
        def _run_one(aid):
            a = AGENTS[aid]
            a["status"] = "running"
            final = _run_agent(a, rounds, tools, defs)
            return aid, a["status"], final, list(a["sent"])
        lines = [f"Ran {len(ids)} sub-agent(s) in PARALLEL (model={MODEL}, ctx={MAX_CTX}):"]
        with ThreadPoolExecutor(max_workers=max(1, len(ids))) as ex:
            futs = [ex.submit(_run_one, aid) for aid in ids]
            for f in futs:
                try:
                    aid, status, final, sent = f.result()
                except Exception as e:
                    aid, status, final, sent = aid, f"error: {e}", "", []
                lines.append(f"[{aid}] status={status}")
                if final:
                    lines.append(f"  result: {final}")
                if sent:
                    lines.append("  posted: " + " | ".join(sent))
        return "\n".join(lines)

    if action == "send":
        if not message or not message.strip():
            return "send needs a 'message'."
        sender = agent_id if agent_id in AGENTS else "main"
        entry = {"from": sender, "to": to or "all",
                 "text": message.strip(), "ts": time.strftime("%H:%M:%S")}
        with _bus_lock:
            BUS.append(entry)
        if sender in AGENTS:
            AGENTS[sender]["sent"].append(f"to:{entry['to']} {entry['text'][:120]}")
        return f"Posted to bus ({entry['from']} -> {entry['to']}): {entry['text']}"

    if action == "read":
        reader = agent_id if agent_id in AGENTS else "main"
        with _bus_lock:
            msgs = [b for b in BUS if b["to"] in (reader, "all")]
        if not msgs:
            return f"No bus messages for '{reader}'."
        lines = [f"{b['ts']}  {b['from']} -> {b['to']}: {b['text']}" for b in msgs]
        return f"{len(msgs)} message(s) for '{reader}':\n" + "\n".join(lines)

    if action == "status":
        a = AGENTS.get(agent_id)
        if not a:
            return f"No sub-agent '{agent_id}'. See action='list'."
        lines = [f"{a['id']}  [{a['status']}]  task: {a['task'][:100]}"]
        if a["sent"]:
            lines.append("posted: " + " | ".join(a["sent"]))
        return "\n".join(lines)

    if action == "list":
        if not AGENTS:
            return "No active sub-agents."
        lines = [f"{len(AGENTS)} sub-agent(s) (model={MODEL}, ctx={MAX_CTX}):"]
        for aid, a in AGENTS.items():
            lines.append(f"  {aid}  [{a['status']}]  {a['task'][:80]}")
        with _bus_lock:
            n_bus = len(BUS)
        if n_bus:
            lines.append(f"bus: {n_bus} message(s)")
        return "\n".join(lines)

    if action == "kill":
        a = AGENTS.pop(agent_id, None)
        if not a:
            return f"No sub-agent '{agent_id}'."
        return f"Killed {agent_id}."

    if action == "clear":
        with _bus_lock:
            n = len(BUS)
            BUS.clear()
        for a in AGENTS.values():
            a["sent"] = []
        return f"Cleared {n} bus message(s)."

    return (f"Unknown action '{action}'. Use: spawn, run, run_all, send, read, "
            f"status, list, kill, clear.")
