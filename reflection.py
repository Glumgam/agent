def reflect(task, history):
    if not history:
        return None

    last = history[-1]
    result = str(last.get("result", ""))

    if "ModuleNotFoundError" in result:
        pkg = result.split("'")[1] if "'" in result else ""
        if pkg:
            return {
                "thought": "missing dependency detected",
                "tool": "run",
                "command": f"pip install {pkg}"
            }

    if "SyntaxError" in result:
        return {
            "thought": "syntax error detected, inspect file",
            "tool": "read_file",
            "path": last.get("action", {}).get("path", "")
        }

    return None
