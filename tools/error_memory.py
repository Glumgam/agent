import json
import os
import time

from project_map import safe_path


ERROR_PATH = "memory/errors.json"


def _ensure_dir():
    base = os.path.dirname(ERROR_PATH) or "."
    os.makedirs(safe_path(base), exist_ok=True)


def _load_errors() -> list:
    _ensure_dir()
    path = safe_path(ERROR_PATH)
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


def _save_errors(errors: list):
    _ensure_dir()
    path = safe_path(ERROR_PATH)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def record_error(task: str, error_message: str) -> dict:
    if not task or not error_message:
        return {"status": "error", "message": "task and error_message are required"}
    errors = _load_errors()
    record = {
        "task": task,
        "error": error_message,
        "timestamp": int(time.time()),
    }
    errors.append(record)
    _save_errors(errors)
    return {"status": "ok", "record": record}


def get_recent_errors(limit: int = 10) -> list:
    errors = _load_errors()
    return errors[-limit:]
