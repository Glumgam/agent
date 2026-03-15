import os
import json
import time
import hashlib

from project_map import safe_path

CACHE_TTL = 86400

QUERY_DIR = "research/queries"
PAGE_DIR = "research/pages"


def _ensure_dirs():
    os.makedirs(safe_path(QUERY_DIR), exist_ok=True)
    os.makedirs(safe_path(PAGE_DIR), exist_ok=True)


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_expired(ts: float) -> bool:
    if not ts:
        return True
    return (time.time() - ts) > CACHE_TTL


def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _query_path(query: str) -> str:
    filename = _hash_key(query) + ".json"
    return safe_path(os.path.join(QUERY_DIR, filename))


def _page_path(url: str) -> str:
    filename = _hash_key(url) + ".json"
    return safe_path(os.path.join(PAGE_DIR, filename))


def load_query_cache(query: str) -> dict:
    _ensure_dirs()
    path = _query_path(query)
    if not os.path.exists(path):
        return {"status": "miss"}
    data = _load_json(path)
    if not data:
        return {"status": "miss"}
    if _is_expired(data.get("timestamp", 0)):
        return {"status": "expired", "data": data}
    return {"status": "hit", "data": data}


def save_query_cache(query: str, urls: list) -> dict:
    _ensure_dirs()
    payload = {
        "query": query,
        "urls": urls,
        "timestamp": int(time.time()),
    }
    _save_json(_query_path(query), payload)
    return payload


def load_page_cache(url: str) -> dict:
    _ensure_dirs()
    path = _page_path(url)
    if not os.path.exists(path):
        return {"status": "miss"}
    data = _load_json(path)
    if not data:
        return {"status": "miss"}
    if _is_expired(data.get("timestamp", 0)):
        return {"status": "expired", "data": data}
    return {"status": "hit", "data": data}


def save_page_cache(url: str, title: str, content: str, html: str = "") -> dict:
    _ensure_dirs()
    payload = {
        "url": url,
        "title": title or "",
        "timestamp": int(time.time()),
        "content": content or "",
    }
    if html:
        payload["html"] = html
    _save_json(_page_path(url), payload)
    return payload
