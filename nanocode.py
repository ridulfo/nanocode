#!/usr/bin/env python3
"""nanocode - minimal coding agent using Ollama"""

import glob as globlib
import json
import os
import re
import subprocess
import urllib.request

MODEL = os.environ.get("OLLAMA_MODEL", "qwen3")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
API_URL = OLLAMA_URL.rstrip("/") + "/api/chat"

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

    # Detect common mistakes
    if not old or not isinstance(old, str):
        return f"error: 'old' must be a non-empty string, got: {type(old).__name__}"

    # Check if old contains line number formatting from read tool
    if re.match(r'^\s*\d+\|', old) or re.search(r'\n\s*\d+\|', old):
        return "error: 'old' contains line numbers (like '  123| '). Line numbers are only for display - copy the actual text content WITHOUT the line number prefix."

    if old not in text:
        # Show helpful context
        preview = old[:80] + "..." if len(old) > 80 else old
        return f"error: old_string not found in file. Searched for: {repr(preview)}\nTip: Copy the EXACT text from the file (read it first if needed). Don't include line numbers."

    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique. Add more surrounding lines to make it unique, or use all=true to replace all occurrences."

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
        args["cmd"],
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
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
        "Read file contents. Returns text with line numbers for reference (e.g., '  42| code'). File path required, not directory.",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file. CRITICAL: 'old' must be EXACT text from file (NOT the line-numbered output from read - strip '  42| ' prefixes). Must be unique unless using all=true. Include surrounding lines if needed for uniqueness.",
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
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return result


def call_api(messages, system_prompt):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
                "model": MODEL,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "tools": make_schema(),
                "stream": True,
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.URLError as e:
        raise Exception(
            f"Cannot reach Ollama at {OLLAMA_URL}. Is the server running? ({e})"
        )

    # Stream response
    content_chunks = []
    tool_calls = []
    usage = {}
    thinking_count = 0
    output_count = 0
    printed_header = False
    in_thinking = False

    for line in response:
        line = line.decode("utf-8").strip()
        if not line:
            continue

        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Check if we're in thinking mode
        msg = chunk.get("message", {})

        # Thinking tokens (before actual response)
        if msg.get("thinking"):
            thinking_count += 1
            in_thinking = True
            print(f"\r{DIM}Thinking... ({thinking_count} tokens){RESET}", end="", flush=True)

        # Accumulate and print content as it streams
        elif msg.get("content"):
            text = msg["content"]
            content_chunks.append(text)
            output_count += 1

            if not printed_header:
                # Clear "thinking" message
                if in_thinking:
                    print(f"\r{' ' * 40}\r", end="", flush=True)
                print(f"\n{CYAN}⏺{RESET} ", end="", flush=True)
                printed_header = True

            print(render_markdown(text), end="", flush=True)

        # Collect tool calls
        if chunk.get("message", {}).get("tool_calls"):
            tool_calls = chunk["message"]["tool_calls"]

        # Final chunk has usage info
        if chunk.get("done"):
            usage = {
                "prompt_tokens": chunk.get("prompt_eval_count", 0),
                "completion_tokens": chunk.get("eval_count", 0),
                "eval_duration": chunk.get("eval_duration", 0),
                "total_duration": chunk.get("total_duration", 0),
            }

    msg = {}
    if content_chunks:
        msg["content"] = "".join(content_chunks)
    if tool_calls:
        msg["tool_calls"] = tool_calls

    return {"message": msg, "usage": usage}


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def main():
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} (Ollama) | {os.getcwd()}{RESET}\n")
    messages = []
    system_prompt = f"""You are a coding agent in a terminal-based assistant. cwd: {os.getcwd()}. Be concise, direct, and friendly. Keep working autonomously using the available tools until the task is fully resolved—do not guess or make up answers. Always read files before modifying them. When exploring the codebase, prefer grep and glob over bash. Briefly tell the user what you're about to do before each action.

CRITICAL - Using the edit tool correctly:
1. The 'read' tool shows line numbers like "  42| content" - these are DISPLAY ONLY
2. When using 'edit', the 'old' parameter must contain ONLY the actual file text
3. NEVER include line number prefixes (like "  42| ") in the 'old' parameter
4. Copy the exact text after the line number prefix when preparing edit operations
5. If edit fails, read the file again and copy the exact text more carefully

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
                assistant_msg = response["message"]
                usage = response.get("usage")
                tool_results = []

                # Content already printed during streaming
                if usage:
                    total_tokens = usage['prompt_tokens'] + usage['completion_tokens']
                    print(f" {DIM}[{total_tokens} tokens]{RESET}", end="", flush=True)

                for tc in assistant_msg.get("tool_calls", []):
                    tool_name = tc["function"]["name"]
                    tool_args = tc["function"]["arguments"]
                    if isinstance(tool_args, str):
                        tool_args = json.loads(tool_args)
                    arg_preview = str(list(tool_args.values())[0])[:50] if tool_args else ""
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
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        }
                    )

                # Store assistant message
                assistant_msg_full = {"role": "assistant"}
                if assistant_msg.get("content"):
                    assistant_msg_full["content"] = assistant_msg["content"]
                if assistant_msg.get("tool_calls"):
                    assistant_msg_full["tool_calls"] = assistant_msg["tool_calls"]
                messages.append(assistant_msg_full)

                if not tool_results:
                    break
                messages.extend(tool_results)

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
