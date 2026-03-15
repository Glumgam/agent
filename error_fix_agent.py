import re

def analyze_error(output):

    if "ModuleNotFoundError" in output:
        module = re.findall(r"No module named '([^']+)'", output)
        if module:
            return {
                "tool": "run",
                "command": f"pip install {module[0]}"
            }

    if "SyntaxError" in output:
        return {
            "thought": "SyntaxError detected, need to inspect file",
            "tool": "read_file"
        }

    return None
