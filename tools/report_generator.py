import os
import json
import time
import hashlib
import re

from project_map import safe_path
from tools import research_cache


REPORTS_DIR = "reports"
NOTES_DIR = "research/notes"


def _ensure_dirs():
    os.makedirs(safe_path(REPORTS_DIR), exist_ok=True)


def _hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _load_notes() -> list:
    notes_path = safe_path(NOTES_DIR)
    if not os.path.exists(notes_path):
        return []
    notes = []
    for name in os.listdir(notes_path):
        if not name.endswith(".json"):
            continue
        path = os.path.join(notes_path, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = data.get("timestamp", 0)
            if ts and (time.time() - ts) > research_cache.CACHE_TTL:
                continue
            notes.append(data)
        except Exception:
            continue
    return notes


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _is_relevant(note: dict, query: str) -> bool:
    q = _normalize(query)
    if not q:
        return True
    hay = " ".join([
        note.get("title", ""),
        note.get("summary", ""),
        " ".join(note.get("key_points", []) or []),
        note.get("url", ""),
        note.get("source", ""),
    ])
    return _normalize(hay).find(q) != -1


def _unique(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _build_summary(relevant_notes: list) -> str:
    summaries = [n.get("summary", "") for n in relevant_notes if n.get("summary")]
    summaries = _unique(summaries)
    if not summaries:
        return "(no summary)"
    paragraphs = []
    idx = 0
    while idx < len(summaries) and len(paragraphs) < 3:
        paragraphs.append(summaries[idx])
        idx += 1
    return "\n\n".join(paragraphs)


def _aggregate_key_points(relevant_notes: list, limit: int = 8) -> list:
    points = []
    for n in relevant_notes:
        points.extend(n.get("key_points", []) or [])
    points = _unique(points)
    return points[:limit]


def _aggregate_sources(relevant_notes: list) -> list:
    sources = []
    for n in relevant_notes:
        title = n.get("title", "").strip()
        url = n.get("url", "").strip() or n.get("source", "").strip()
        if not url:
            continue
        sources.append(f"{title} - {url}" if title else url)
    return _unique(sources)


def generate_report(query: str, entries: list = None) -> dict:
    _ensure_dirs()
    if entries is None:
        notes = _load_notes()
        relevant = [n for n in notes if _is_relevant(n, query)]
        if not relevant:
            relevant = notes
    else:
        relevant = entries

    summary = _build_summary(relevant)
    key_points = _aggregate_key_points(relevant)
    sources = _aggregate_sources(relevant)

    report_lines = []
    report_lines.append("Title")
    report_lines.append(query)
    report_lines.append("")
    report_lines.append("Summary")
    report_lines.append(summary)
    report_lines.append("")
    report_lines.append("Key Findings")
    if key_points:
        for p in key_points:
            report_lines.append(f"* {p}")
    else:
        report_lines.append("* (no key points)")
    report_lines.append("")
    report_lines.append("Sources")
    if sources:
        for s in sources:
            report_lines.append(f"* {s}")
    else:
        report_lines.append("* (no sources)")
    report_lines.append("")
    report_lines.append("Timestamp")
    report_lines.append(str(int(time.time())))

    filename = _hash_query(query) + ".txt"
    path = safe_path(os.path.join(REPORTS_DIR, filename))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    return {
        "status": "ok",
        "path": os.path.join(REPORTS_DIR, filename),
        "note_count": len(relevant),
    }
