# nanocode

Minimal coding agent. Single Python file, zero dependencies, ~270 lines. Uses [Ollama](https://ollama.com) for local LLM inference.

Built using Claude Code, then used to build itself.

![screenshot](screenshot.png)

## Features

- Full agentic loop with tool use
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output

## Usage

Requires [Ollama](https://ollama.com) running locally.

```bash
# Uses qwen3 by default
python nanocode.py

# Specify a different model
OLLAMA_MODEL="llama3.1" python nanocode.py

# Custom Ollama URL
OLLAMA_URL="http://remote-server:11434" python nanocode.py
```

### Container Mode (Podman/Docker)

Run nanocode in an isolated container:

```bash
# Uses qwen3 by default
./nanocode-podman

# Specify model and work directory
OLLAMA_MODEL="llama3.1" ./nanocode-podman ~/dev/project

# Custom Ollama URL
OLLAMA_URL="http://remote-server:11434" ./nanocode-podman

# Configure git identity
GIT_USER_NAME="Your Name" GIT_USER_EMAIL="you@example.com" ./nanocode-podman
```

**How it works:**
- Creates a fresh container for each session
- Mounts your work directory into the container
- Accesses host's Ollama server via network
- Changes and commits persist to the mounted directory
- Container auto-removes after exit

**Requirements:**
- Podman or Docker installed (script auto-detects)
- Ollama running on host (default: `http://localhost:11434`)

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
