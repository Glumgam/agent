import difflib

from project_map import safe_path


def apply_patch(file_path: str, new_content: str):
    if not file_path:
        return "Error: file_path is required"

    path = safe_path(file_path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()
    except FileNotFoundError:
        original = ""

    diff = difflib.unified_diff(
        original.splitlines(),
        new_content.splitlines(),
        fromfile=file_path,
        tofile=file_path,
        lineterm=""
    )

    diff_text = "\n".join(diff)
    if diff_text:
        print(diff_text)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return "Success: patch applied"
