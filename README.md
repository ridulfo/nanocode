# nanocode

Minimal coding agent. Single Python file, zero dependencies, ~270 lines. Uses [llama.cpp](https://github.com/ggerganov/llama.cpp) for local LLM inference.

Built using Claude Code, then used to build itself.

![screenshot](screenshot.png)

## Features

- Full agentic loop with tool use
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output

## Usage

Requires [llama.cpp](https://github.com/ggerganov/llama.cpp) server running locally.

```bash
# Uses default model
python nanocode.py

# Specify a different model
LLAMACPP_MODEL="my-model" python nanocode.py

# Custom llama.cpp URL
LLAMACPP_URL="http://remote-server:8080" python nanocode.py
```

### Container Mode (Podman/Docker)

Run nanocode in an isolated container:

```bash
# Uses default model
./nanocode-llamacpp

# Specify model and work directory
LLAMACPP_MODEL="my-model" ./nanocode-llamacpp ~/dev/project

# Custom llama.cpp URL
LLAMACPP_URL="http://remote-server:8080" ./nanocode-llamacpp

# Configure git identity
GIT_USER_NAME="Your Name" GIT_USER_EMAIL="you@example.com" ./nanocode-llamacpp
```

**How it works:**
- Creates a fresh container for each session
- Mounts your work directory into the container
- Accesses host's llama.cpp server via network
- Changes and commits persist to the mounted directory
- Container auto-removes after exit

**Requirements:**
- Podman or Docker installed (script auto-detects)
- llama.cpp server running on host (default: `http://localhost:8080`)

## Commands

- `/c` - Clear conversation
- `/q` or `exit` - Quit

## Tools

| Tool | Description |
|------|-------------|
| `read` | Read file with line numbers, offset/limit |
| `write` | Write content to file |
| `edit` | Replace string in file (must be unique) |
| `glob` | Find files by pattern, sorted by mtime |
| `grep` | Search files for regex |
| `bash` | Run shell command |

## Example

```
────────────────────────────────────────
❯ what files are here?
────────────────────────────────────────

⏺ Glob(**/*.py)
  ⎿  nanocode.py

⏺ There's one Python file: nanocode.py
```

## License

MIT
