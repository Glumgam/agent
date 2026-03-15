import os


def should_debug(result: str) -> bool:
    if not result:
        return False
    text = str(result)
    return "Traceback" in text or "Error" in text or "Exception" in text


def analyze_error(result: str, last_action: dict | None = None):
    text = str(result)

    if "ModuleNotFoundError" in text:
        module = ""
        if "No module named" in text and "'" in text:
            try:
                module = text.split("'")[1]
            except Exception:
                module = ""
        if module:
            return {"tool": "run", "command": f"pip install {module}"}
        return {"tool": "run", "command": "pip install <module>"}

    if "SyntaxError" in text:
        if last_action and "path" in last_action:
            path = last_action["path"]
            if path and os.path.exists(path):
                return {"tool": "read_file", "path": path}
        return None

    if "NameError" in text:
        return {"tool": "search_code"}

    return None
