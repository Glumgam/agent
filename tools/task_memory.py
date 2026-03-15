import json
import os

from project_map import safe_path


TASK_QUEUE_PATH = "memory/task_queue.json"


def _ensure_dir():
    base = os.path.dirname(TASK_QUEUE_PATH) or "."
    os.makedirs(safe_path(base), exist_ok=True)


def load_tasks() -> list:
    _ensure_dir()
    path = safe_path(TASK_QUEUE_PATH)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def save_tasks(queue: list) -> dict:
    _ensure_dir()
    path = safe_path(TASK_QUEUE_PATH)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "count": len(queue)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
