# Terminal AI Assistant

A terminal-based AI assistant that runs on a local Ollama model, with streaming output and a pluggable tool system.

## Requirements

- Python 3.8+
- Ollama running locally (default: http://localhost:11434)
- DDGS (ddgs package) - required by the search tool
- A pulled Ollama model (default: lumos_vision:latest)

```bash
ollama serve
ollama pull lumos_vision:latest
pip install ddgs
```

## Running

```bash
cd terminal_ai
python terminal_ai.py
```

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
| OLLAMA_URL | http://localhost:11434 | Ollama server address |
| MODEL | lumos_vision:latest | Model to chat with |
| SYSTEM_PROMPT | (see file) | Persona / behavior instructions |
| num_ctx | 40000 | Context window size |
| SAVE_DIR | <script dir>/saves | Where conversations are saved (anchored to the script, not the CWD) |
| MAX_TOOL_ROUNDS | 10 | Max tool-call iterations per turn |

Change MODEL to use any other installed Ollama model.

Persistent settings live in settings.json (next to the script). Currently it stores
working_directory, which /cd writes and startup re-applies.

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
| /save [name] | Save the conversation to saves/ (auto-timestamped, or saved as conv_<name>.json) |
| /load [name] | List saves, or load a specific one (restores full context) |
| /saves | List saved conversations |
| /ctx | Show context usage (with a percentage bar) |
| /compact | Summarize all thinking blocks except the last one via model, then reprint the compacted conversation |
| /rst | Reset the conversation (clears context) |
| /cd [path] | Set the working directory to any directory on the system (supports ~ and %vars%; saved to settings.json) |
| /files | Open the current working directory in the OS file explorer |
| /think [level] | Set thinking level: off, low, medium, xhigh |
| /theme | Toggle colored output on/off |
| /exit / /quit | Exit the app |

Anything that does not start with / is sent to the model as a chat message.

## Tool System

Tools are the core extensibility feature. Each tool is a folder inside tools/ containing two files:

```
tools/
+-- search/
|   +-- tool.py        # the implementation
|   +-- config.json    # metadata + parameter schema
```

### tool.py

Must define a single tool() function. It accepts keyword arguments matching the schema in config.json and returns a string (the result fed back to the model).

```python
def tool(query: str, max_results: int = 5) -> str:
    ...
    return "formatted result text"
```

### config.json

Describes the tool to Ollama so the model knows when and how to call it.

```json
{
  "name": "search",
  "description": "Search the web using DuckDuckGo. Use this to find current information...",
  "parameters": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "The search query." },
      "max_results": { "type": "integer", "description": "Number of results (1-10)." }
    },
    "required": ["query"]
  }
}
```

### How it works at runtime

1. Startup - load_tools() scans tools/ for subdirectories, imports each tool.py, and reads each config.json.
2. Each turn - tool definitions are passed to Ollama in the tools field of the chat request.
3. Model decides to act - instead of plain text, Ollama returns a tool_calls array.
4. App executes the matching tool() function and prints the call + a result preview.
5. Result fed back to Ollama as a tool-role message.
6. Model continues - it may call more tools (up to MAX_TOOL_ROUNDS) or produce a final streamed answer.

### Adding a new tool

Drop a new folder into tools/ with a tool.py and a config.json. No changes to terminal_ai.py are needed - it is auto-discovered on the next start.

## Included Tools

| Tool | Folder | Description |
|---|---|---|
| search | tools/search/ | Web search via DuckDuckGo (DDGS). Returns titles, URLs, and short snippets. |
| read_file | tools/files/ | Read a text file's contents. |
| write_file | tools/files/ | Write (or append) text to a file. |
| list_dir | tools/files/ | List files and folders in a directory. |
| find_files | tools/files/ | Recursively find files matching a glob pattern. |
| rename_file | tools/files/ | Rename a file or folder. |
| edit_file | tools/files/ | Replace the first occurrence of a text string in a file. |
| delete_file | tools/files/ | Delete a file or folder. |
| move_file | tools/files/ | Move a file or folder to a new path. |

## Output

- Streaming - assistant text prints token-by-token as it is generated.
- Colors - ANSI colors (auto-detected; disable with the NO_COLOR env var or /theme).
  - you> prompt: cyan
  - assistant text: #f9f1a5
  - tool calls: yellow
  - tool results: dim
  - errors: red

## Project Structure

```
terminal_ai/
+-- terminal_ai.py          # main app
+-- reesk.md               # project context (auto-loaded into the system prompt)
+-- README.md              # this file
+-- settings.json         # persistent settings (working_directory)
+-- saves/                 # created on first /save
+-- tools/
|   +-- search/
|   |   +-- tool.py
|   |   +-- config.json
```
