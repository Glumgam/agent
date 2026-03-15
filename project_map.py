import os
import ast

# -------------------------
# WORKSPACE
# -------------------------

WORKSPACE = os.path.abspath("workspace")

# -------------------------
# SETTINGS
# -------------------------

IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    "dist",
    "build",
}

IGNORE_FILES = {
    ".DS_Store",
}

MAX_FILE_SIZE = 50_000
MAX_OUTPUT_LINES = 2000


# -------------------------
# SAFE PATH
# -------------------------


def safe_path(path: str) -> str:
    """
    ワークスペース外へのアクセスを防ぐサンドボックスパス解決。

    - None/空文字列を拒否
    - workspace/ / ./ プレフィックスを正規化
    - ../ を明示的に拒否
    - os.path.realpath() でシンボリックリンクを解決
    - os.path.commonpath() でワークスペース境界を検証
    - 違反時は ValueError を raise
    """
    if not path:
        raise ValueError("safe_path: path must not be empty")

    # LLMがよく付けるプレフィックスを除去
    if path.startswith("workspace/"):
        path = path[len("workspace/"):]
    if path.startswith("./"):
        path = path[2:]

    # ../ トラバーサルを明示的に拒否
    parts = path.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError(f"safe_path: path traversal not allowed: {path!r}")

    # シンボリックリンク解決 + ワークスペース境界チェック
    workspace_real = os.path.realpath(WORKSPACE)
    full = os.path.realpath(os.path.join(WORKSPACE, path))

    if os.path.commonpath([workspace_real, full]) != workspace_real:
        raise ValueError(f"Access denied: path outside workspace: {path!r}")

    return full


# -------------------------
# PYTHON SYMBOLS
# -------------------------


def list_python_symbols(file_path):

    try:

        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        symbols = []

        for node in tree.body:

            if isinstance(node, ast.FunctionDef):
                symbols.append(f"func {node.name}()")

            elif isinstance(node, ast.AsyncFunctionDef):
                symbols.append(f"async func {node.name}()")

            elif isinstance(node, ast.ClassDef):
                symbols.append(f"class {node.name}")

        return symbols

    except Exception:
        return []


# -------------------------
# PROJECT SCAN
# -------------------------


def scan_project():

    if not os.path.exists(WORKSPACE):
        return "Workspace directory not found."

    lines = []

    for root, dirs, files in os.walk(WORKSPACE):

        # skip ignored directories
        dirs[:] = sorted([d for d in dirs if d not in IGNORE_DIRS])

        files = sorted(files)

        rel_path = os.path.relpath(root, WORKSPACE)

        if rel_path == ".":

            name = "workspace/"
            level = 0

        else:

            name = os.path.basename(root) + "/"
            level = rel_path.count(os.sep) + 1

        indent = "  " * level

        lines.append(f"{indent}{name}")

        file_indent = "  " * (level + 1)

        for file in files:

            if file in IGNORE_FILES:
                continue

            path = os.path.join(root, file)

            try:

                size = os.path.getsize(path)

                if size > MAX_FILE_SIZE:

                    lines.append(
                        f"{file_indent}{file} (large file {size} bytes)"
                    )

                    continue

                lines.append(f"{file_indent}{file}")

                if file.endswith(".py"):

                    symbols = list_python_symbols(path)

                    for s in symbols:

                        lines.append(f"{file_indent}  - {s}")

            except OSError:

                lines.append(f"{file_indent}{file} (access error)")

        if len(lines) > MAX_OUTPUT_LINES:

            lines.append("... project map truncated ...")
            break

    return "\n".join(lines)
