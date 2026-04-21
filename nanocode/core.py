#!/usr/bin/env python3
"""nanocode - minimal coding agent"""

import glob as globlib
import json
import os
import re
import signal
import subprocess
import urllib.error
import urllib.request

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)

BASH_TIMEOUT = int(os.environ.get("NANOCODE_BASH_TIMEOUT", "120"))
TOOL_OUTPUT_MAX = 10000
TOOL_OUTPUT_TRUNCATE = 8000


def render_markdown(text):
    text = re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)
    text = re.sub(r"`([^`]+)`", f"{DIM}\\1{RESET}", text)
    text = re.sub(
        r"```(\w*)\n?(.+?)```", f"\n{DIM}```\\1\n\\2```{RESET}\n", text, flags=re.DOTALL
    )
    text = re.sub(r"^- (.+)$", f"{DIM}• \\1{RESET}", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", f"\\1{DIM}(\\2){RESET}", text)
    text = re.sub(r"^#{1,6}\s+(.+)$", f"\n{BOLD}\\1{RESET}\n", text, flags=re.MULTILINE)
    return text


class Provider:
    def __init__(self):
        self.model = os.environ.get("LLAMACPP_MODEL")
        self.verbose = False
        base_url = os.environ.get("LLAMACPP_URL", "http://localhost:8079")
        self._base_url = base_url
        self._api_url = base_url.rstrip("/") + "/v1/chat/completions"

    @property
    def label(self):
        return self.model or "(server default)"

    def call_api(self, messages, system_prompt, tools):
        body = {
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "tools": tools,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if self.model:
            body["model"] = self.model

        request = urllib.request.Request(
            self._api_url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.URLError as e:
            raise Exception(
                f"Cannot reach llama.cpp at {self._base_url}. Is the server running? ({e})"
            )

        content_chunks = []
        tool_calls_map = {}  # index -> partial tool call
        usage = {}
        printed_header = False
        thinking_count = 0
        in_thinking = False

        for line in response:
            line = line.decode("utf-8").strip()
            if not line or not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue

            if chunk.get("usage"):
                u = chunk["usage"]
                usage = {
                    "prompt_tokens": u.get("prompt_tokens", 0),
                    "completion_tokens": u.get("completion_tokens", 0),
                }

            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})

            if self.verbose:
                if delta.get("reasoning_content"):
                    reasoning_text = delta["reasoning_content"]
                    thinking_count += len(reasoning_text.split())
                    in_thinking = True
                    print(f"{DIM}{reasoning_text}{RESET}", end="", flush=True)
                elif delta.get("content"):
                    text = delta["content"]
                    print(f"{text}", end="", flush=True)
            elif delta.get("reasoning_content"):
                reasoning_text = delta["reasoning_content"]
                thinking_count += len(reasoning_text.split())
                in_thinking = True
                print(
                    f"\r{DIM}Thinking... ({thinking_count} tokens){RESET}",
                    end="",
                    flush=True,
                )

            if delta.get("content") and not self.verbose:
                text = delta["content"]
                content_chunks.append(text)
                if not printed_header:
                    if in_thinking:
                        print(f"\r{' ' * 40}\r", end="", flush=True)
                    print(f"\n{CYAN}⏺{RESET} ", end="", flush=True)
                    printed_header = True
                print(render_markdown(text), end="", flush=True)
            elif delta.get("content"):
                text = delta["content"]
                content_chunks.append(text)

            for tc_delta in delta.get("tool_calls", []):
                idx = tc_delta.get("index", 0)
                if idx not in tool_calls_map:
                    tool_calls_map[idx] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                tc = tool_calls_map[idx]
                if tc_delta.get("id"):
                    tc["id"] = tc_delta["id"]
                fn = tc_delta.get("function", {})
                if fn.get("name"):
                    tc["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    tc["function"]["arguments"] += fn["arguments"]

        tool_calls = [tool_calls_map[i] for i in sorted(tool_calls_map)]
        msg = {}
        if content_chunks:
            msg["content"] = "".join(content_chunks)
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return {"message": msg, "usage": usage}


# --- Tool implementations ---


def read(args):
    try:
        with open(args["path"], "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"error: file not found: {args['path']}"
    except PermissionError:
        return f"error: permission denied: {args['path']}"
    except Exception as e:
        return f"error: {e}"
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    try:
        with open(args["path"], "w", encoding="utf-8") as f:
            f.write(args["content"])
    except PermissionError:
        return f"error: permission denied: {args['path']}"
    except Exception as e:
        return f"error: {e}"
    return "ok"


def edit(args):
    try:
        with open(args["path"], "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return f"error: file not found: {args['path']}"
    except PermissionError:
        return f"error: permission denied: {args['path']}"
    except Exception as e:
        return f"error: {e}"
    old, new = args["old"], args["new"]

    if not old or not isinstance(old, str):
        return f"error: 'old' must be a non-empty string, got: {type(old).__name__}"

    if re.match(r"^\s*\d+\|", old) or re.search(r"\n\s*\d+\|", old):
        return "error: 'old' contains line numbers (like '  123| '). Line numbers are only for display - copy the actual text content WITHOUT the line number prefix."

    if old not in text:
        preview = old[:80] + "..." if len(old) > 80 else old
        return f"error: old_string not found in file. Searched for: {repr(preview)}\nTip: Copy the EXACT text from the file (read it first if needed). Don't include line numbers."

    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique. Add more surrounding lines to make it unique, or use all=true to replace all occurrences."

    try:
        with open(args["path"], "w", encoding="utf-8") as f:
            f.write(
                text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
            )
    except PermissionError:
        return f"error: permission denied: {args['path']}"
    except Exception as e:
        return f"error: {e}"
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
            with open(filepath, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if pattern.search(line):
                        hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    cmd = args["cmd"]
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        preexec_fn=os.setsid,
    )
    output_lines = []
    timed_out = False
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=BASH_TIMEOUT)
    except KeyboardInterrupt:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
        except (ProcessLookupError, OSError):
            pass
        return "".join(output_lines).strip() or "(interrupted)"
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
        except (ProcessLookupError, OSError):
            pass
        timed_out = True
        output_lines.append(f"\n(timed out after {BASH_TIMEOUT}s)")
    output = "".join(output_lines).strip() or "(empty)"
    return output


# --- Todo system ---

TODO_FILE = os.path.expanduser("~/.nanocode-todos.json")


def _load_todos():
    try:
        with open(TODO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"todos": []}


def _save_todos(data):
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_todos(args):
    data = _load_todos()
    if not data["todos"]:
        return "No todos currently."
    lines = ["Todo list:"]
    for i, todo in enumerate(data["todos"], 1):
        status = (
            "✓"
            if todo["status"] == "completed"
            else "○"
            if todo["status"] == "pending"
            else "●"
        )
        lines.append(f"{i}. [{status}] {todo['description']}")
    return "\n".join(lines)


def write_todos(args):
    items = args.get("items", [])
    if not items:
        data = _load_todos()
        data["todos"] = []
        _save_todos(data)
        return "Cleared todo list."
    todos = [{"description": item, "status": "pending"} for item in items]
    data = {"todos": todos}
    _save_todos(data)
    lines = ["Todo list updated:"]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. ○ {item}")
    return "\n".join(lines)


def edit_todo(args):
    index = args.get("index", 1) - 1
    status = args.get("status")
    if status not in ("pending", "in_progress", "completed"):
        return f"error: status must be 'pending', 'in_progress', or 'completed', got: {status}"
    data = _load_todos()
    if not (0 <= index < len(data["todos"])):
        return f"error: invalid todo index {index + 1}"
    data["todos"][index]["status"] = status
    _save_todos(data)
    return f"Todo {index + 1} marked as {status}"


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
    "read_todos": (
        "Read the todo list. Returns all todos with their status (pending, in_progress, completed).",
        {},
        read_todos,
    ),
    "write_todos": (
        "Write/overwrite the entire todo list. Provide 'items' as a list of todo descriptions.",
        {"items": "string[]?"},
        write_todos,
    ),
    "edit_todo": (
        "Edit a todo item. Set status to 'pending', 'in_progress', or 'completed'. Use 'index' (1-based) and 'status'.",
        {"index": "integer", "status": "string"},
        edit_todo,
    ),
}


def run_tool(name, args):
    try:
        result = TOOLS[name][2](args)
        if len(result) > 10000:
            return f"warning: tool call '{name}' returned too much text ({len(result)} characters, max 10000). Aborting to prevent overwhelming the agent."
        return result
    except Exception as err:
        return f"error: {err}"


def make_schema():
    result = []
    for name, (desc, params, _) in TOOLS.items():
        props = {}
        for k, t in params.items():
            base = t.rstrip("?")
            if base == "string[]":
                props[k] = {"type": "array", "items": {"type": "string"}}
            elif base == "number":
                props[k] = {"type": "number"}
            elif base == "integer":
                props[k] = {"type": "integer"}
            elif base == "boolean":
                props[k] = {"type": "boolean"}
            else:
                props[k] = {"type": base}
        required = [k for k, t in params.items() if not t.endswith("?")]
        result.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            }
        )
    return result


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def main():
    provider = Provider()
    tools_schema = make_schema()
    print(f"{BOLD}nanocode{RESET} | {DIM}{provider.label} | {os.getcwd()}{RESET}\n")
    messages = []
    verbose = False

    prompt_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "system-prompt.md"
    )
    with open(prompt_path) as f:
        system_prompt = f.read().format(os.getcwd())

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
            if user_input == "/verbose":
                verbose = not verbose
                provider.verbose = verbose  # Also set provider's verbose flag
                status = "ON" if verbose else "OFF"
                print(f"{GREEN}⏺ Verbose mode {status}{RESET}")
                continue

            messages.append({"role": "user", "content": user_input})

            # agentic loop: keep calling API until no more tool calls
            while True:
                try:
                    response = provider.call_api(messages, system_prompt, tools_schema)
                except KeyboardInterrupt:
                    print(f"\n{YELLOW}⏺ Interrupted{RESET}")
                    break
                assistant_msg = response["message"]
                usage = response.get("usage")
                tool_results = []

                # Content already printed during streaming
                if usage:
                    total_tokens = usage["prompt_tokens"] + usage["completion_tokens"]
                    print(f" {DIM}[{total_tokens} tokens]{RESET}", end="", flush=True)

                for tc in assistant_msg.get("tool_calls", []):
                    tool_name = tc["function"]["name"]
                    tool_args = tc["function"]["arguments"]
                    if isinstance(tool_args, str):
                        tool_args = json.loads(tool_args)
                    arg_preview = (
                        str(list(tool_args.values())[0])[:50] if tool_args else ""
                    )
                    print(
                        f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                    )

                    result = run_tool(tool_name, tool_args)
                    lines = result.split("\n")
                    extra = (
                        f" ... +{len(lines) - 1} lines"
                        if len(lines) > 1
                        else "..."
                        if len(lines[0]) > 60
                        else ""
                    )
                    preview = lines[0][:60] + extra
                    print(f"  {DIM}⎿  {preview}{RESET}")

                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        }
                    )

                # Store assistant message (content must always be present for llama.cpp)
                msg = {
                    "role": "assistant",
                    "content": assistant_msg.get("content") or "",
                }
                if assistant_msg.get("tool_calls"):
                    msg["tool_calls"] = assistant_msg["tool_calls"]
                messages.append(msg)

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
