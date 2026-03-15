import os
import json
import time
import hashlib
import re
from project_map import safe_path
from tools import vector_store


KB_DIR = "knowledge"
ENTRY_DIR = "knowledge/entries"


def _ensure_dirs():
    os.makedirs(safe_path(KB_DIR), exist_ok=True)
    os.makedirs(safe_path(ENTRY_DIR), exist_ok=True)


def _hash_source(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _entry_path(source: str) -> str:
    filename = _hash_source(source) + ".json"
    return safe_path(os.path.join(ENTRY_DIR, filename))


def store_knowledge(note: dict) -> dict:
    _ensure_dirs()
    source = note.get("url") or note.get("source") or ""
    if not source:
        return {"status": "error", "message": "source url missing"}

    entry = {
        "title": note.get("title", ""),
        "summary": note.get("summary", ""),
        "key_points": note.get("key_points", []) or [],
        "source": source,
        "timestamp": int(time.time()),
    }

    path = _entry_path(source)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        return {"status": "saved", "path": os.path.join(ENTRY_DIR, os.path.basename(path))}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _score_entry(entry: dict, terms: list) -> int:
    hay = " ".join([
        entry.get("title", ""),
        entry.get("summary", ""),
        " ".join(entry.get("key_points", []) or []),
    ]).lower()
    score = 0
    for t in terms:
        if t and t in hay:
            score += 1
    return score


def knowledge_confidence(entries: list, query: str) -> float:
    if not entries or not query:
        return 0.0
    scores = [e.get("_score", 0.0) for e in entries]
    scores = [s for s in scores if isinstance(s, (int, float))]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def search_knowledge(query: str) -> list:
    _ensure_dirs()
    if not query:
        return []
    results = vector_store.search_similar(query, k=5)
    entries = []
    for item in results:
        doc_id = item.get("doc_id", "")
        score = item.get("_score", 0.0)
        if not doc_id:
            continue
        path = safe_path(os.path.join(ENTRY_DIR, f"{doc_id}.json"))
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["_score"] = score
                entries.append(data)
                continue
            except Exception:
                pass
        entries.append(
            {
                "title": "",
                "summary": "",
                "key_points": [],
                "source": "",
                "_score": score,
            }
        )
    return entries[:5]
