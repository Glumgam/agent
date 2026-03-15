import json
import os
import time

import requests

from project_map import safe_path


OLLAMA_BASE = "http://localhost:11434/api"

PLANNER_MODEL = "qwen3:14b"
CODER_MODEL = "qwen2.5-coder:7b"
EMBED_MODEL = "bge-m3"


def _ensure_log_dir():
    os.makedirs(safe_path("logs"), exist_ok=True)


def _log_call(model: str, prompt_size: int, response_tokens: int, status: str):
    _ensure_log_dir()
    path = safe_path("logs/llm_router.log")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(
            f"[{ts}] model={model} prompt_size={prompt_size} "
            f"response_tokens={response_tokens} status={status}\n"
        )


def _post_json(url: str, payload: dict) -> dict:
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return {"status": "ok", "data": resp.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def plan(prompt: str) -> str:
    payload = {
        "model": PLANNER_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    result = _post_json(f"{OLLAMA_BASE}/generate", payload)
    if result["status"] != "ok":
        _log_call(PLANNER_MODEL, len(prompt or ""), 0, "error")
        return ""
    data = result["data"]
    response = data.get("response", "") or ""
    tokens = data.get("eval_count", 0) or 0
    _log_call(PLANNER_MODEL, len(prompt or ""), tokens, "ok")
    return response.strip()


def code(prompt: str) -> str:
    payload = {
        "model": CODER_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    result = _post_json(f"{OLLAMA_BASE}/generate", payload)
    if result["status"] != "ok":
        _log_call(CODER_MODEL, len(prompt or ""), 0, "error")
        return ""
    data = result["data"]
    response = data.get("response", "") or ""
    tokens = data.get("eval_count", 0) or 0
    _log_call(CODER_MODEL, len(prompt or ""), tokens, "ok")
    return response.strip()


def embed(text: str) -> list:
    payload = {
        "model": EMBED_MODEL,
        "prompt": text,
    }
    result = _post_json(f"{OLLAMA_BASE}/embeddings", payload)
    if result["status"] != "ok":
        _log_call(EMBED_MODEL, len(text or ""), 0, "error")
        return []
    data = result["data"]
    vector = data.get("embedding", []) or []
    _log_call(EMBED_MODEL, len(text or ""), len(vector), "ok")
    return vector
