import json
import os

from project_map import safe_path


ERROR_PATH = "memory/errors.json"


def _load_errors() -> list:
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


def _classify_error(message: str) -> str:
    if not message:
        return "unknown_error"
    text = message.lower()
    if "urlopen error" in text or "nodename nor servname" in text:
        return "network_error"
    if "temporary failure" in text or "name resolution" in text:
        return "network_error"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "blocked by robots" in text or "robots.txt" in text:
        return "robots_blocked"
    if "permission" in text:
        return "permission_error"
    return "unknown_error"


def analyze_errors() -> list:
    errors = _load_errors()
    groups = {}
    for item in errors:
        message = item.get("error", "") if isinstance(item, dict) else ""
        err_type = _classify_error(message)
        if err_type not in groups:
            groups[err_type] = {
                "type": err_type,
                "count": 0,
                "example": message,
            }
        groups[err_type]["count"] += 1
        if not groups[err_type].get("example"):
            groups[err_type]["example"] = message
    summary = list(groups.values())
    summary.sort(key=lambda x: x.get("count", 0), reverse=True)
    return summary
