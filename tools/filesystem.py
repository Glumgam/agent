import os
import re

from project_map import safe_path, WORKSPACE


# -------------------------
# FILE WRITE
# -------------------------

def write_file(path, content):

    full = safe_path(path)

    os.makedirs(os.path.dirname(full), exist_ok=True)

    with open(full, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Successfully written to {os.path.relpath(full, WORKSPACE)}"


# -------------------------
# CREATE FILE (NEW)
# -------------------------

def create_file(path, content):

    full = safe_path(path)
    existed = os.path.exists(full)

    os.makedirs(os.path.dirname(full), exist_ok=True)

    with open(full, "w", encoding="utf-8") as f:
        f.write(content)

    rel = os.path.relpath(full, WORKSPACE)
    # --- LOOP FIX START ---
    action_msg = '{"tool": "run", "command": "python ' + rel + '"}'
    if existed:
        return (
            f"OVERWRITTEN: {rel}. "
            f"Stop creating. NEXT ACTION MUST BE: {action_msg}"
        )
    return (
        f"CREATED: {rel}. "
        f"NEXT ACTION MUST BE: {action_msg}"
    )
    # --- LOOP FIX END ---


# -------------------------
# FILE READ
# -------------------------

def read_file(path):

    full = safe_path(path)

    if not os.path.exists(full):
        return f"Error: File does not exist: {path}"

    with open(full, "r", encoding="utf-8") as f:
        content = f.read()

    MAX_READ = 10000

    if len(content) > MAX_READ:
        return content[:MAX_READ] + "\n...[truncated]..."

    return content


# -------------------------
# APPEND FILE
# -------------------------

def append_file(path, content):

    full = safe_path(path)

    if not os.path.exists(full):
        return f"Error: File does not exist for append: {path}"

    with open(full, "a", encoding="utf-8") as f:
        f.write(content)

    return f"Successfully appended to {os.path.relpath(full, WORKSPACE)}"


# -------------------------
# MAKE DIR
# -------------------------

def make_dir(path):

    full = safe_path(path)

    if os.path.exists(full):
        return f"Directory already exists: {path}"

    os.makedirs(full, exist_ok=True)

    return f"Directory created: {os.path.relpath(full, WORKSPACE)}"


# -------------------------
# READ DIRECTORY
# -------------------------

def read_directory(path="."):

    full = safe_path(path)

    if not os.path.isdir(full):
        return f"Error: {path} is not a directory."

    items = sorted(os.listdir(full))

    lines = []

    for item in items:

        if item == ".DS_Store":
            continue

        p = os.path.join(full, item)

        if os.path.isdir(p):
            lines.append(f"{item}/")
        else:
            size = os.path.getsize(p)
            lines.append(f"{item} ({size} bytes)")

    if not lines:
        return "(empty directory)"

    return "\n".join(lines)


# -------------------------
# DIFF EDIT
# -------------------------

def diff_edit(path, old, new):

    full = safe_path(path)

    if not os.path.exists(full):
        return f"Error: File {path} not found."

    with open(full, "r", encoding="utf-8") as f:
        content = f.read()

    if old in content:

        new_content = content.replace(old, new, 1)

        with open(full, "w", encoding="utf-8") as f:
            f.write(new_content)

        return "Success: Diff applied (exact match)."

    def normalize(text):

        lines = text.strip().splitlines()

        return [l.strip() for l in lines if l.strip()]

    old_lines = normalize(old)

    file_lines = content.splitlines()

    for i in range(len(file_lines)):

        segment = file_lines[i:i + len(old_lines)]

        if normalize("\n".join(segment)) == old_lines:

            start = sum(len(l) + 1 for l in file_lines[:i])
            end = start + sum(len(l) + 1 for l in segment)

            new_content = content[:start] + new + content[end:]

            with open(full, "w", encoding="utf-8") as f:
                f.write(new_content)

            return "Success: Diff applied (whitespace tolerant)."

    def make_pattern(text):

        escaped = re.escape(text.strip())

        return re.sub(r"\\\s+", r"\\s+", escaped)

    pattern = make_pattern(old)

    matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))

    if len(matches) == 1:

        start, end = matches[0].span()

        new_content = content[:start] + new + content[end:]

        with open(full, "w", encoding="utf-8") as f:
            f.write(new_content)

        return "Success: Diff applied (regex fuzzy match)."

    if len(matches) > 1:

        return (
            "Error: Multiple matches found for 'old' snippet.\n"
            "Please provide a more unique snippet."
        )

    return (
        "Error: 'old' snippet not found in file.\n"
        "Ensure indentation and code match the file."
    )
