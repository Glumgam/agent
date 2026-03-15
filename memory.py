import json
import os
import tempfile
from typing import List, Dict, Any

MEMORY_FILE = "agent_memory.json"

MAX_MEMORY_ENTRIES = 20
MAX_MEMORY_SHOWN = 5
MAX_SUMMARY_LENGTH = 500


def load_memory() -> List[Dict[str, Any]]:

    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        cleaned = []

        for item in data:
            if isinstance(item, dict):
                cleaned.append(item)

        return cleaned

    except Exception:
        return []


def _atomic_write(path: str, data: str) -> None:

    dir_name = os.path.dirname(path) or "."
    fd, temp_path = tempfile.mkstemp(dir=dir_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(data)

        os.replace(temp_path, path)

    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def save_memory(memory: List[Dict[str, Any]]) -> None:

    trimmed = memory[-MAX_MEMORY_ENTRIES:]

    data = json.dumps(
        trimmed,
        indent=2,
        ensure_ascii=False
    )

    _atomic_write(MEMORY_FILE, data)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated)"


def _summarize_history(history: List[Dict[str, Any]]) -> str:

    if not history:
        return "no steps taken"

    files_created = []
    files_edited = []
    last_run_result = ""
    final_tool = ""

    for h in history:

        action = h.get("action", {})
        tool = action.get("tool", "")
        path = action.get("path", "")

        result = str(h.get("result", ""))

        if tool == "create_file" and path:
            files_created.append(path)

        elif tool in ("edit_file", "diff_edit", "append_file") and path:
            files_edited.append(path)

        elif tool == "run":
            last_run_result = _truncate(result.strip(), 200)

        final_tool = tool

    parts = []

    if files_created:
        parts.append(f"created: {', '.join(set(files_created))}")

    if files_edited:
        parts.append(f"edited: {', '.join(set(files_edited))}")

    if last_run_result:
        parts.append(f"last_run_output: {last_run_result}")

    parts.append(f"ended_with: {final_tool}")

    summary = " | ".join(parts)

    return _truncate(summary, MAX_SUMMARY_LENGTH)


def add_memory(memory: List[Dict[str, Any]], task: str, history: List[Dict[str, Any]]) -> None:

    summary = _summarize_history(history)

    entry = {
        "task": str(task),
        "summary": summary
    }

    memory.append(entry)

    save_memory(memory)


def format_memory(memory: List[Dict[str, Any]]) -> str:

    if not memory:
        return "(no prior memory)"

    lines = []

    for m in memory[-MAX_MEMORY_SHOWN:]:

        task = m.get("task", "")
        summary = m.get("summary", "")

        lines.append(f"TASK: {task}")
        lines.append(f"SUMMARY: {summary}")

    return "\n".join(lines)
