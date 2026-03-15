import os
import json
import time
import hashlib
import re

from project_map import safe_path
from tools import research_cache
from tools import knowledge_base
from tools import vector_store


NOTES_DIR = "research/notes"


def _ensure_dirs():
    os.makedirs(safe_path(NOTES_DIR), exist_ok=True)


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _note_path(url: str) -> str:
    filename = _hash_url(url) + ".json"
    return safe_path(os.path.join(NOTES_DIR, filename))


def _is_expired(ts: float) -> bool:
    if not ts:
        return True
    return (time.time() - ts) > research_cache.CACHE_TTL


def load_note_cache(url: str) -> dict:
    _ensure_dirs()
    path = _note_path(url)
    if not os.path.exists(path):
        return {"status": "miss"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"status": "miss"}
    if _is_expired(data.get("timestamp", 0)):
        return {"status": "expired", "data": data}
    return {"status": "hit", "data": data}


def save_note(note: dict) -> dict:
    _ensure_dirs()
    url = note.get("url", "")
    if not url:
        return note
    path = _note_path(url)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(note, f, ensure_ascii=False, indent=2)
    return note


def _split_sentences(text: str) -> list:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    sentences = []
    for s in parts:
        s = s.strip()
        if len(s) < 20:
            continue
        sentences.append(s)
    return sentences


def _extract_key_points(text: str, min_points: int = 3, max_points: int = 5) -> list:
    if not text:
        return []
    points = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if line.startswith(("-", "*", "•", "・")):
            points.append(line.lstrip("-*•・ ").strip())
    if len(points) < min_points:
        sentences = _split_sentences(text)
        for s in sentences:
            if s not in points:
                points.append(s)
            if len(points) >= max_points:
                break
    return points[:max_points]


def extract_research_notes(page_data: dict) -> dict:
    url = page_data.get("url", "")
    title = page_data.get("title", "")
    content = page_data.get("content", "") or ""

    sentences = _split_sentences(content)
    summary = ""
    if sentences:
        summary = " ".join(sentences[:2]).strip()
    elif content:
        summary = content[:200].strip()

    key_points = _extract_key_points(content)
    if not key_points and summary:
        key_points = [summary]

    note = {
        "url": url,
        "title": title or "",
        "summary": summary,
        "key_points": key_points,
        "timestamp": int(time.time()),
    }
    knowledge_base.store_knowledge(note)
    note_id = _hash_url(url) if url else ""
    if note_id:
        note_text = " ".join(
            [
                note.get("title", ""),
                note.get("summary", ""),
                " ".join(note.get("key_points", []) or []),
            ]
        ).strip()
        if note_text:
            vector_store.add_document(note_id, note_text)
    return note
