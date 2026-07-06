"""LLM providers: Ollama (local, default) + cloud APIs (Gemini / OpenAI / Anthropic) via user API keys.

All providers speak through two calls:
  chat_stream(messages, cfg)  -> yields content deltas (tutor chat)
  chat_json(prompt, cfg)      -> one-shot dict for analysis tasks (corrections, hints, ...)

cfg comes from main.llm_config(): {"provider": ..., "model": ..., "key": ...}.
Cloud providers use raw HTTP (requests) on purpose — no SDKs, zero extra dependencies.
"""
import json
import os

import requests

OLLAMA = os.environ.get("KAIWA_OLLAMA_URL", "http://localhost:11434")
PREFERRED = ["qwen3:4b-instruct-2507-q4_K_M", "qwen3:4b-instruct", "qwen3:4b",
             "qwen2.5:7b-instruct", "qwen2.5:7b"]

API_GEMINI = "https://generativelanguage.googleapis.com/v1beta"
API_OPENAI = "https://api.openai.com/v1"
API_ANTHROPIC = "https://api.anthropic.com/v1"

# Curated model lists for cloud providers (first entry = default: cheap + fast,
# which is what a conversation tutor wants).
PROVIDERS = {
    "ollama": {"label": "Local (Ollama)", "needs_key": False, "models": []},
    "gemini": {"label": "Google Gemini", "needs_key": True,
               "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]},
    "openai": {"label": "OpenAI", "needs_key": True,
               "models": ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o", "gpt-4.1"]},
    "anthropic": {"label": "Anthropic Claude", "needs_key": True,
                  "models": ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"]},
}

_model_cache = None


# ------------------------------------------------------------------- ollama

def list_models() -> list:
    try:
        r = requests.get(f"{OLLAMA}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def resolve_model(preferred: str | None = None) -> str | None:
    global _model_cache
    models = list_models()
    if preferred and preferred in models:
        return preferred
    if _model_cache in models:
        return _model_cache
    for p in PREFERRED:
        if p in models:
            _model_cache = p
            return p
    _model_cache = models[0] if models else None
    return _model_cache


def ollama_up() -> bool:
    try:
        requests.get(f"{OLLAMA}/api/version", timeout=3)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- readiness

def not_ready_reason(cfg: dict) -> str | None:
    """None if the active provider can serve requests, else a user-facing message."""
    if cfg["provider"] == "ollama":
        if not cfg["model"]:
            return "Ollama is not running or no model installed"
        return None
    if not cfg["key"]:
        label = PROVIDERS[cfg["provider"]]["label"]
        return f"No API key saved for {label} — add one in Settings"
    return None


def _raise_api_error(r: requests.Response, name: str):
    if r.ok:
        return
    try:
        body = r.json()
        msg = (body.get("error") or {}).get("message") or json.dumps(body)[:200]
    except Exception:
        msg = r.text[:200]
    if r.status_code in (401, 403):
        raise RuntimeError(f"{name}: API key rejected — check it in Settings")
    if r.status_code == 429:
        raise RuntimeError(f"{name}: rate limited — wait a moment and try again")
    raise RuntimeError(f"{name} error {r.status_code}: {msg}")


def _split_system(messages: list) -> tuple[str, list]:
    """Pull system messages out (Gemini/Anthropic take them as a separate field)."""
    system, rest = [], []
    for m in messages:
        (system if m["role"] == "system" else rest).append(m)
    return "\n\n".join(m["content"] for m in system), rest


def _parse_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # salvage first {...} block if the model added stray text
        start, end = content.find("{"), content.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}


def _cloud_max_tokens(num_predict: int) -> int:
    # Local num_predict is tuned for CPU latency; cloud is fast, so give headroom
    # (Gemini 2.5 also spends part of this budget on internal reasoning tokens).
    return max(1024, num_predict * 4)


# ------------------------------------------------------------------ routing

def chat_stream(messages: list, cfg: dict, temperature=0.7, num_predict=200):
    """Yield content deltas from a streaming chat call on the active provider."""
    p = cfg["provider"]
    if p == "ollama":
        yield from _ollama_stream(messages, cfg["model"], temperature, num_predict)
    elif p == "gemini":
        yield from _gemini_stream(messages, cfg["model"], cfg["key"], temperature,
                                  _cloud_max_tokens(num_predict))
    elif p == "openai":
        yield from _openai_stream(messages, cfg["model"], cfg["key"], temperature,
                                  _cloud_max_tokens(num_predict))
    elif p == "anthropic":
        yield from _anthropic_stream(messages, cfg["model"], cfg["key"],
                                     _cloud_max_tokens(num_predict))
    else:
        raise RuntimeError(f"unknown provider: {p}")


def chat_json(prompt: str, cfg: dict, temperature=0.2, num_predict=350) -> dict:
    """One-shot JSON call for analysis tasks (corrections, hints, ...)."""
    p = cfg["provider"]
    if p == "ollama":
        return _ollama_json(prompt, cfg["model"], temperature, num_predict)
    if p == "gemini":
        return _gemini_json(prompt, cfg["model"], cfg["key"], temperature,
                            _cloud_max_tokens(num_predict))
    if p == "openai":
        return _openai_json(prompt, cfg["model"], cfg["key"], temperature,
                            _cloud_max_tokens(num_predict))
    if p == "anthropic":
        return _anthropic_json(prompt, cfg["model"], cfg["key"],
                               _cloud_max_tokens(num_predict))
    raise RuntimeError(f"unknown provider: {p}")


# ---------------------------------------------------------- ollama backend

def _ollama_stream(messages, model, temperature, num_predict):
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": 4096,
            "repeat_penalty": 1.05,
        },
        "keep_alive": "30m",
    }
    with requests.post(f"{OLLAMA}/api/chat", json=payload, stream=True, timeout=300) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                yield delta
            if chunk.get("done"):
                break


def _ollama_json(prompt, model, temperature, num_predict) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": 4096,
        },
        "keep_alive": "30m",
    }
    r = requests.post(f"{OLLAMA}/api/chat", json=payload, timeout=300)
    r.raise_for_status()
    return _parse_json(r.json().get("message", {}).get("content", "{}"))


# ---------------------------------------------------------- gemini backend

def _gemini_payload(messages, temperature, max_tokens):
    system, msgs = _split_system(messages)
    contents = [{"role": "model" if m["role"] == "assistant" else "user",
                 "parts": [{"text": m["content"]}]} for m in msgs]
    payload = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    return payload


def _gemini_stream(messages, model, key, temperature, max_tokens):
    payload = _gemini_payload(messages, temperature, max_tokens)
    if "flash" in model:  # flash models allow disabling thinking → faster first token
        payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
    url = f"{API_GEMINI}/models/{model}:streamGenerateContent?alt=sse"
    with requests.post(url, headers={"x-goog-api-key": key}, json=payload,
                       stream=True, timeout=120) as r:
        _raise_api_error(r, "Gemini")
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            chunk = json.loads(line[6:])
            for cand in chunk.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    if part.get("text"):
                        yield part["text"]


def _gemini_json(messages_or_prompt, model, key, temperature, max_tokens) -> dict:
    payload = _gemini_payload([{"role": "user", "content": messages_or_prompt}],
                              temperature, max_tokens)
    payload["generationConfig"]["responseMimeType"] = "application/json"
    url = f"{API_GEMINI}/models/{model}:generateContent"
    r = requests.post(url, headers={"x-goog-api-key": key}, json=payload, timeout=120)
    _raise_api_error(r, "Gemini")
    cands = r.json().get("candidates", [])
    text = "".join(p.get("text", "") for c in cands
                   for p in c.get("content", {}).get("parts", []))
    return _parse_json(text)


# ---------------------------------------------------------- openai backend

def _openai_headers(key):
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _openai_stream(messages, model, key, temperature, max_tokens):
    payload = {"model": model, "messages": messages, "stream": True,
               "temperature": temperature, "max_completion_tokens": max_tokens}
    with requests.post(f"{API_OPENAI}/chat/completions", headers=_openai_headers(key),
                       json=payload, stream=True, timeout=120) as r:
        _raise_api_error(r, "OpenAI")
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            data = line[6:]
            if data == b"[DONE]":
                break
            chunk = json.loads(data)
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    yield delta


def _openai_json(prompt, model, key, temperature, max_tokens) -> dict:
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": temperature, "max_completion_tokens": max_tokens,
               "response_format": {"type": "json_object"}}
    r = requests.post(f"{API_OPENAI}/chat/completions", headers=_openai_headers(key),
                      json=payload, timeout=120)
    _raise_api_error(r, "OpenAI")
    choices = r.json().get("choices") or []
    content = choices[0]["message"]["content"] if choices else "{}"
    return _parse_json(content)


# ------------------------------------------------------- anthropic backend

def _anthropic_headers(key):
    return {"x-api-key": key, "anthropic-version": "2023-06-01",
            "content-type": "application/json"}


def _anthropic_stream(messages, model, key, max_tokens):
    # No sampling params: newest Claude models reject temperature; defaults are fine.
    system, msgs = _split_system(messages)
    payload = {"model": model, "max_tokens": max_tokens, "messages": msgs, "stream": True}
    if system:
        payload["system"] = system
    with requests.post(f"{API_ANTHROPIC}/messages", headers=_anthropic_headers(key),
                       json=payload, stream=True, timeout=120) as r:
        _raise_api_error(r, "Anthropic")
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            chunk = json.loads(line[6:])
            if chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                if delta.get("type") == "text_delta" and delta.get("text"):
                    yield delta["text"]


def _anthropic_json(prompt, model, key, max_tokens) -> dict:
    payload = {"model": model, "max_tokens": max_tokens,
               "messages": [{"role": "user", "content": prompt}]}
    r = requests.post(f"{API_ANTHROPIC}/messages", headers=_anthropic_headers(key),
                      json=payload, timeout=120)
    _raise_api_error(r, "Anthropic")
    content = "".join(b.get("text", "") for b in r.json().get("content", [])
                      if b.get("type") == "text")
    return _parse_json(content)
