# nanocode

Minimal Claude Code alternative. Single Python file, zero dependencies, ~250 lines.

Built using Claude Code, then used to build itself.

![screenshot](screenshot.png)

## Features

- Full agentic loop with tool use
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output

## Usage

### Anthropic API

```bash
export ANTHROPIC_API_KEY="your-key"
python nanocode.py
```

### OpenRouter

Use [OpenRouter](https://openrouter.ai) to access any model:

```bash
export OPENROUTER_API_KEY="your-key"
python nanocode.py
```

To use a different model:

```bash
export OPENROUTER_API_KEY="your-key"
export MODEL="openai/gpt-5.2"
python nanocode.py
```

### llama.cpp Server

Use a local [llama.cpp](https://github.com/ggerganov/llama.cpp) server:

```bash
# Start llama.cpp server (in another terminal)
./llama-server -m model.gguf --port 8080

# Use with nanocode
export LLAMA_CPP_URL="http://localhost:8080"
python nanocode.py
```

### Container Mode (Podman/Docker)

Run nanocode in an isolated container (always uses current directory):

```bash
# Use llama.cpp (default)
./nanocode-podman

# Specify provider
./nanocode-podman llama            # llama.cpp at localhost:8080
./nanocode-podman ollama           # requires OLLAMA_MODEL
./nanocode-podman openrouter       # requires OPENROUTER_API_KEY
./nanocode-podman anthropic        # requires ANTHROPIC_API_KEY

# Configure Ollama
export OLLAMA_MODEL="gpt-oss"
./nanocode-podman ollama

# Configure git identity
export GIT_USER_NAME="Your Name"
export GIT_USER_EMAIL="you@example.com"
./nanocode-podman llama
```

**How it works:**
- Creates a fresh container for each session
- Mounts your work directory into the container
- Accesses host's llama.cpp server via network
- Changes and commits persist to the mounted directory
- Container auto-removes after exit

**Requirements:**
- Podman or Docker installed (script auto-detects)
- llama.cpp server running on host at `http://localhost:8080` (default, or set `LLAMA_CPP_URL` to override)
- Alternatively, configure `OLLAMA_MODEL` for Ollama, `OPENROUTER_API_KEY` for OpenRouter, or `ANTHROPIC_API_KEY` for Anthropic API

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
