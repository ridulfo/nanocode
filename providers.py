import json
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


class Provider(ABC):
    @property
    @abstractmethod
    def label(self) -> str: ...

    @abstractmethod
    def call_api(self, messages, system_prompt, tools) -> dict: ...


class OllamaProvider(Provider):
    def __init__(self):
        self.model = os.environ.get("OLLAMA_MODEL", "qwen3")
        base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self._base_url = base_url
        self._api_url = base_url.rstrip("/") + "/api/chat"

    @property
    def label(self):
        return f"{self.model} (Ollama)"

    def call_api(self, messages, system_prompt, tools):
        request = urllib.request.Request(
            self._api_url,
            data=json.dumps({
                "model": self.model,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "tools": tools,
                "stream": True,
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.URLError as e:
            raise Exception(f"Cannot reach Ollama at {self._base_url}. Is the server running? ({e})")

        content_chunks = []
        tool_calls = []
        usage = {}
        thinking_count = 0
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

            msg = chunk.get("message", {})

            if msg.get("thinking"):
                thinking_count += 1
                in_thinking = True
                print(f"\r{DIM}Thinking... ({thinking_count} tokens){RESET}", end="", flush=True)
            elif msg.get("content"):
                text = msg["content"]
                content_chunks.append(text)
                if not printed_header:
                    if in_thinking:
                        print(f"\r{' ' * 40}\r", end="", flush=True)
                    print(f"\n{CYAN}⏺{RESET} ", end="", flush=True)
                    printed_header = True
                print(render_markdown(text), end="", flush=True)

            if msg.get("tool_calls"):
                tool_calls = msg["tool_calls"]

            if chunk.get("done"):
                usage = {
                    "prompt_tokens": chunk.get("prompt_eval_count", 0),
                    "completion_tokens": chunk.get("eval_count", 0),
                }

        msg = {}
        if content_chunks:
            msg["content"] = "".join(content_chunks)
        if tool_calls:
            msg["tool_calls"] = tool_calls
        return {"message": msg, "usage": usage}


class LlamaCppProvider(Provider):
    def __init__(self):
        self.model = os.environ.get("LLAMACPP_MODEL", "default")
        base_url = os.environ.get("LLAMACPP_URL", "http://localhost:8080")
        self._base_url = base_url
        self._api_url = base_url.rstrip("/") + "/v1/chat/completions"

    @property
    def label(self):
        return f"{self.model} (llama.cpp)"

    def call_api(self, messages, system_prompt, tools):
        request = urllib.request.Request(
            self._api_url,
            data=json.dumps({
                "model": self.model,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "tools": tools,
                "stream": True,
                "stream_options": {"include_usage": True},
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.URLError as e:
            raise Exception(f"Cannot reach llama.cpp at {self._base_url}. Is the server running? ({e})")

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

            if delta.get("reasoning_content"):
                thinking_count += len(delta["reasoning_content"].split())
                in_thinking = True
                print(f"\r{DIM}Thinking... ({thinking_count} tokens){RESET}", end="", flush=True)

            if delta.get("content"):
                text = delta["content"]
                content_chunks.append(text)
                if not printed_header:
                    if in_thinking:
                        print(f"\r{' ' * 40}\r", end="", flush=True)
                    print(f"\n{CYAN}⏺{RESET} ", end="", flush=True)
                    printed_header = True
                print(render_markdown(text), end="", flush=True)

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


_PROVIDERS = {
    "ollama": OllamaProvider,
    "llamacpp": LlamaCppProvider,
}


def get_provider() -> Provider:
    name = os.environ.get("PROVIDER", "ollama").lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown provider '{name}'. Choose from: {', '.join(_PROVIDERS)}")
    return _PROVIDERS[name]()
