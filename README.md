# Terminal AI Assistant

A terminal-based AI assistant that runs on a local Ollama model, with token-by-token
streaming output and a pluggable tool system.

## Requirements

- Python 3.8+
- Ollama running locally (default: http://localhost:11434)
- A pulled Ollama model (default: orcarouter/Qwen3.8-27B-Uncensored:q3_K_S)
- Optional, per-tool:
  - `ddgs` - required by the search tool
  - `playwright` + Chromium - required by the browser tool
  - `ffmpeg` - required by the analyze_video tool

```bash
ollama serve
ollama pull orcarouter/Qwen3.8-27B-Uncensored:q3_K_S
pip install ddgs
pip install playwright && playwright install chromium
```

## Running

```bash
cd terminal_ai
python terminal_ai.py
```

On Windows, double-click `assistant.bat` (cds to the script dir and runs python).

On startup the app:
1. Applies a saved working directory from settings.json (if set and valid).
2. Loads all tools from the tools/ directory.
3. Verifies the Ollama server is reachable and the configured model is installed.
4. Prints the current working directory under the banner.
5. Drops you into an interactive prompt.

## Configuration

All settings live at the top of terminal_ai.py:

| Setting | Default | Purpose |
|---|---|---|
| MODEL | orcarouter/Qwen3.8-27B-Uncensored:q3_K_S | Model to chat with |
| SYSTEM_PROMPT | (see file) | Persona / behavior instructions |
| MAX_CTX | 40000 | Context window size |
| MAX_TOOL_ROUNDS | 50 | Max tool-call iterations per turn |
| THINKING_LEVEL | basic | Default thinking level |
| THINKING_LEVELS | (see file) | Map of level -> {think param, prompt suffix} |
| SAVE_DIR | <script dir>/saves | Where conversations are saved (anchored to the script, not the CWD) |
| SETTINGS_FILE | settings.json | Persistent settings (next to the script) |

There is no OLLAMA_URL constant. The app uses the `ollama` Python library,
which talks to the default server at http://localhost:11434.

Change MODEL to use any other installed Ollama model.

Persistent settings live in settings.json (next to the script). Currently it stores
working_directory, which /cd writes and startup re-applies.

## Thinking Levels

/think <level> sets the thinking level. Valid levels:
off, low, basic, medium, xmedium, high, max

Each maps to an Ollama `think` value (False / "low" / "medium" / "high")
and an optional prompt suffix appended to the system prompt.
Default is "basic" (think=medium, prompt "Don't think too hard.").

## Commands

Type / at the prompt to list all commands.

| Command | Description |
|---|---|
| / | Show the command list |
| /help | Show the command list |
| /clear | Clear the terminal screen |
| /history | Show past Q&A for this session |
| /info | Show model, server, tools, and session info |
| /model | Show the current model |
| /tools | List loaded tools and their descriptions |
| /save [name] | Save the conversation to saves/ (adds .json and conv_ prefix if missing) |
| /load [name] | Load a saved conversation (restores full context and replays it). Accepts a filename or a 1-based index into the /saves list. |
| /saves | List saved conversations |
| /ctx | Show context usage with a percentage bar. Prefers Ollama's real prompt_eval_count; falls back to a chars/4 estimate. |
| /compact | Summarizes all thinking blocks except the last one via the model, then reprints the compacted conversation. Reports tokens freed. |
| /rst | Reset the conversation (clears context back to the system prompt) |
| /frst | Reset the conversation AND reload all tools |
| /cd [path] | Set the working directory (supports ~ and %vars%; persisted to settings.json, re-applied on startup). The system prompt is rebuilt so the model sees the new CWD. |
| /files | Open the current working directory in the OS file explorer |
| /think [level] | Set thinking level: off, low, basic, medium, xmedium, high, max |
| /theme | Toggle colored output on/off |
| /exit / /quit | Exit the app |

Anything that does not start with / is sent to the model as a chat message.

## Tool System

Tools live in tools/. Three loading patterns are supported (auto-discovered
on startup, no edits to terminal_ai.py needed):

1. Single tool per folder:  <tool>/config.json + <tool>/tool.py
   tool.py defines one tool() function returning a string.
   config.json holds name, description, and the parameter schema.

2. Package (multiple tools in one folder):  <genre>/__init__.py
   __init__.py imports a sibling module (e.g. web.py) and exposes a TOOLS dict
   of {name: {description, parameters, fn}}.

3. Flat fallback:  tools/tools.py
   A single module exposing a TOOLS dict. tools.py aggregates the genre
   packages (web, files, execution, data, media, ask) via direct file-path
   imports so it works under importlib without a package context.

Folder-based tools take priority over the tools.py fallback.

### How it works at runtime

1. Startup - load_tools() scans tools/ for subdirectories, imports each
   tool.py or __init__.py, and reads each config.json or TOOLS dict.
2. Each turn - tool definitions are passed to Ollama in the tools field of
   the chat request.
3. Model decides to act - instead of plain text, Ollama returns a tool_calls array.
4. App executes the matching tool() function and prints the call + a result preview.
5. Result fed back to Ollama as a tool-role message.
6. Model continues - it may call more tools (up to MAX_TOOL_ROUNDS) or produce
   a final streamed answer.

### Adding a new tool

Drop a new folder into tools/ with a tool.py and a config.json (single tool),
or add an entry to a genre package's TOOLS dict. No changes to terminal_ai.py
are needed - it is auto-discovered on the next start.

### Memory

The memory tool is a persistent key-value store (memory.json) with semantic
search via nomic-embed-text through Ollama. Two conventions:

- Use it often. Proactively store any fact, name, email, preference, or detail
  you learn that you may need later - do not wait to be asked.
- Store specific keys, not blobs. One fact per key, with a specific descriptive
  key name (e.g. `verna_email`, `verna_maker`, `verna_model`). Never cram several
  unrelated facts into one key - a blob only matches as a whole, so a specific
  detail buried in it will not be found by semantic search.

## Included Tools

Genre packages (via tools.py aggregation):

| Genre | Tools |
|---|---|
| web/ | search, http_get |
| files/ | read_file, write_file, list_dir, find_files, rename_file, edit_file, delete_file, create_folder, move_file |
| execution/ | run_python, run_shell |
| data/ | calculator, json_parse, text_stats, base64_codec, hash_text, url_parse, random_pick, convert_units, diff_text, get_datetime, sleep |
| media/ | analyze_image, analyze_video (vision model + ffmpeg) |
| ask/ | ask (interactive arrow-key menu with a free-text 'custom' option) |

Standalone folders (config.json + tool.py):

| Tool | Folder | Description |
|---|---|---|
| browser | tools/browser/ | Headless Chromium via Playwright (goto, text, html, title, screenshot, click, type, wait, eval, close) |
| clipboard | tools/clipboard/ | Get / set system clipboard |
| csv_parse | tools/csv_parse/ | Read, filter, or summarize a CSV |
| download | tools/download/ | Download a file from a URL |
| git_ops | tools/git_ops/ | status, log, diff, commit |
| gmail | tools/gmail/ | list, read, send, download attachments (user: existanimal0@gmail.com) |
| grep | tools/grep/ | Regex search across files in a directory |
| image_downloader | tools/image_downloader/ | Download an image from a URL |
| image_search | tools/image_search/ | Image search via DuckDuckGo |
| open_file | tools/open_file/ | Open a file in its default app |
| open_quadrant | tools/open_quadrant/ | Open a URL in a browser quadrant (optionally a new window) |
| open_url | tools/open_url/ | Open a URL in the default browser |
| regex | tools/regex/ | Match or replace text with a regex |
| spotify | tools/spotify/ | Control Spotify playback (status, play, pause, next, previous, volume, search, play_id) |
| subagent | tools/subagent/ | Spawn and manage sub-agents (spawn, run, run_all, send, read, status, list, kill, clear) with a shared message bus |
| memory | tools/memory/ | Persistent key-value memory with semantic search (nomic-embed-text via Ollama, cosine similarity, threshold 0.55; falls back to substring if Ollama is down) |

## Output

- Streaming - assistant text prints token-by-token as it is generated.
- Colors - ANSI colors (auto-detected; disable with the NO_COLOR env var or /theme).
  - you> prompt: cyan (bold)
  - assistant text: #f9f1a5
  - thinking: dim
  - tool calls: #2563eb (blue)
  - tool results: #800080 (purple)
  - errors: red

## Project Structure

```
terminal_ai/
+-- terminal_ai.py          # main app (all config at the top)
+-- terminal_ai.py.bak      # backup of an earlier revision
+-- reesk.md               # project context / conventions (auto-loaded into the system prompt)
+-- README.md              # this file
+-- LICENSE                # MIT
+-- assistant.bat          # Windows launcher (cd to script dir, run python)
+-- settings.json         # persistent settings (working_directory)
+-- spotify.json          # Spotify OAuth tokens (client_id, access/refresh)
+-- inbox/               # drop folder for files to process
+-- saves/               # saved conversations (created on first /save)
+-- tools/               # tool definitions (see Tool System above)
```
