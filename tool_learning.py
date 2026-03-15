import json
import os

PATH = "memory/tool_patterns.json"


def load_patterns():
    if not os.path.exists(PATH):
        return []
    with open(PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_pattern(task, history):
    steps = [h["action"]["tool"] for h in history if "action" in h and h["action"].get("tool")]

    data = load_patterns()
    data.append({
        "task": task,
        "steps": steps
    })

    os.makedirs("memory", exist_ok=True)

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
