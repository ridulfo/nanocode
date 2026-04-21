# nanocode

Minimal coding agent. Uses [llama.cpp](https://github.com/ggerganov/llama.cpp) for local LLM inference.

Built using Claude Code, then used to build itself.

## Features

- Full agentic loop with tool use
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output
- Sandboxed execution with bubblewrap

## Usage

Requires [llama.cpp](https://github.com/ggerganov/llama.cpp) server running locally.

### Sandbox Mode

Run nanocode in a sandboxed environment using bubblewrap:

```bash
# Uses default model
./run-nanocode.sh

# Specify work directory
./run-nanocode.sh ~/dev/project

# Specify model and custom URL
LLAMACPP_URL="http://remote-server:8079" ./run-nanocode.sh

# Configure git identity
GIT_USER_NAME="Your Name" GIT_USER_EMAIL="you@example.com" ./run-nanocode.sh
```

**How it works:**
- Creates a sandboxed environment using bubblewrap
- Mounts your work directory with read-write access
- Accesses host's llama.cpp server via network
- Changes and commits persist to the mounted directory
- Provides process isolation with PID and IPC namespaces

**Requirements:**
- bubblewrap installed
- llama.cpp server running on host (default: `http://localhost:8079`)

### Nix (Recommended)

Run directly from the flake:

```bash
nix run github:ridulfo/nanocode

# Specify a work directory
nix run github:ridulfo/nanocode -- ~/dev/project

# Specify a different model
nix run github:ridulfo/nanocode
```

#### Development

Use Nix for development:

```bash
# Enter development shell
nix develop

# Build package
nix build

# Run built package
nix run .
```

## Commands

- `/c` - Clear conversation
- `/q` or `exit` - Quit
- `/verbose` to see what the model is thinking

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
