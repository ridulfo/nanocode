#!/usr/bin/env python3
"""nanocode - minimal claude code alternative"""

import glob as globlib, json, os, re, subprocess, urllib.request

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL")
OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434/v1/chat/completions")
LLAMA_CPP_URL = os.environ.get("LLAMA_CPP_URL")

# Provider detection: Ollama > llama.cpp > OpenRouter > Anthropic
if OLLAMA_MODEL:
    PROVIDER = "ollama"
    API_URL = OLLAMA_API_URL
    MODEL = OLLAMA_MODEL
elif LLAMA_CPP_URL:
    PROVIDER = "llama.cpp"
    API_URL = f"{LLAMA_CPP_URL.rstrip('/')}/v1/chat/completions"
    MODEL = os.environ.get("MODEL", "local-model")
elif OPENROUTER_KEY:
    PROVIDER = "openrouter"
    API_URL = "https://openrouter.ai/api/v1/messages"
    MODEL = os.environ.get("MODEL", "anthropic/claude-opus-4.5")
else:
    PROVIDER = "anthropic"
    API_URL = "https://api.anthropic.com/v1/messages"
    MODEL = os.environ.get("MODEL", "claude-opus-4-5")

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)


# --- Tool implementations ---


def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args):
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    proc = subprocess.Popen(
        args["cmd"], shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---

TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file. IMPORTANT: old must be unique - include surrounding lines as context if the target appears multiple times. Use all=true only to replace ALL occurrences.",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    """Anthropic format tool schema"""
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append(
            {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        )
    return result


def make_schema_openai():
    """OpenAI function calling format tool schema"""
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        })
    return result


def call_api_anthropic(messages, system_prompt):
    """Call Anthropic or OpenRouter API using Anthropic format"""
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
                "model": MODEL,
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": messages,
                "tools": make_schema(),
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            **({"Authorization": f"Bearer {OPENROUTER_KEY}"} if OPENROUTER_KEY else {"x-api-key": os.environ.get("ANTHROPIC_API_KEY", "")}),
        },
    )
    response = urllib.request.urlopen(request)
    return json.loads(response.read())


def call_api_openai_compatible(messages, system_prompt):
    """Call Ollama or llama.cpp API with OpenAI format conversion"""
    # Convert Anthropic messages to OpenAI format
    openai_messages = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        if msg["role"] == "user":
            content = msg["content"]
            if isinstance(content, str):
                openai_messages.append({"role": "user", "content": content})
            elif isinstance(content, list):
                # Handle tool_result blocks
                for block in content:
                    if block["type"] == "tool_result":
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"]
                        })
        elif msg["role"] == "assistant":
            content_blocks = msg["content"]
            text_parts = []
            tool_calls = []

            for block in content_blocks:
                if block["type"] == "text":
                    text_parts.append(block["text"])
                elif block["type"] == "tool_use":
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"])
                        }
                    })

            openai_msg = {"role": "assistant"}
            if text_parts:
                openai_msg["content"] = "\n".join(text_parts)
            if tool_calls:
                openai_msg["tool_calls"] = tool_calls
            openai_messages.append(openai_msg)

    # Make API call
    request = urllib.request.Request(
        API_URL,
        data=json.dumps({
            "model": MODEL,
            "messages": openai_messages,
            "tools": make_schema_openai(),
            "max_tokens": 8192,
        }).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        response = urllib.request.urlopen(request)
    except urllib.error.URLError as e:
        raise Exception(f"Cannot reach {PROVIDER} at {API_URL}. Is the server running? ({e})")

    openai_response = json.loads(response.read())

    # Convert OpenAI response back to Anthropic format
    choice = openai_response["choices"][0]
    message = choice["message"]

    content_blocks = []

    # Add text content if present
    if message.get("content"):
        content_blocks.append({"type": "text", "text": message["content"]})

    # Add tool calls if present
    if message.get("tool_calls"):
        for tool_call in message["tool_calls"]:
            content_blocks.append({
                "type": "tool_use",
                "id": tool_call["id"],
                "name": tool_call["function"]["name"],
                "input": json.loads(tool_call["function"]["arguments"])
            })

    return {"content": content_blocks}


def call_api(messages, system_prompt):
    """Route to appropriate API based on provider"""
    if PROVIDER in ("ollama", "llama.cpp"):
        return call_api_openai_compatible(messages, system_prompt)
    else:
        return call_api_anthropic(messages, system_prompt)
def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def main():
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} ({PROVIDER.capitalize()}) | {os.getcwd()}{RESET}\n")
    messages = []
    system_prompt = f"""You are a coding agent in a terminal-based assistant. cwd: {os.getcwd()}. Be concise, direct, and friendly. Keep working autonomously using the available tools until the task is fully resolved—do not guess or make up answers. Always read files before modifying them. When exploring the codebase, prefer grep and glob over bash. Briefly tell the user what you're about to do before each action.

Fix problems at root causes, not with surface patches. Keep changes minimal, focused, and consistent with existing code style. Do not add comments, type annotations, refactors, or improvements beyond what was asked. If an approach fails, try an alternative instead of repeating the same action. Do not commit or push to git unless explicitly asked. When tests or build commands exist, use them to verify your work."""

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                messages = []
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agentic loop: keep calling API until no more tool calls
            while True:
                response = call_api(messages, system_prompt)
                content_blocks = response.get("content", [])
                tool_results = []

                for block in content_blocks:
                    if block["type"] == "text":
                        print(f"\n{CYAN}⏺{RESET} {render_markdown(block['text'])}")

                    if block["type"] == "tool_use":
                        tool_name = block["name"]
                        tool_args = block["input"]
                        arg_preview = str(list(tool_args.values())[0])[:50]
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )

                        result = run_tool(tool_name, tool_args)
                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f"  {DIM}⎿  {preview}{RESET}")

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block["id"],
                                "content": result,
                            }
                        )

                messages.append({"role": "assistant", "content": content_blocks})

                if not tool_results:
                    break
                messages.append({"role": "user", "content": tool_results})

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
