"""
security.py — カテゴリA: コマンドセキュリティ・ループガード

- ALLOWED_COMMANDS / pip ホワイトリスト
- is_repeated_action() / reset_session()
"""

import json
import os
import sys
from typing import Optional


# -------------------------
# COMMAND SECURITY
# -------------------------

ALLOWED_COMMANDS = {
    "python",
    "python3",
    "pytest",
    "pip",
    "curl",
    "ls",
    "grep",
    "cat",
    "mkdir",
    "echo",
    "pwd",
    "which",
}

VENV_PYTHON = sys.executable
DEFAULT_PIP_PACKAGES = {"pytest", "requests", "reportlab"}


def _load_pip_whitelist() -> set:
    path = os.path.join(os.path.dirname(__file__), "pip_whitelist.json")
    if not os.path.exists(path):
        return set(DEFAULT_PIP_PACKAGES)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            cleaned = {x.strip() for x in data if x.strip()}
            return cleaned or set(DEFAULT_PIP_PACKAGES)
    except Exception:
        pass
    return set(DEFAULT_PIP_PACKAGES)


ALLOWED_PIP_PACKAGES = _load_pip_whitelist()


def _normalize_pkg_name(pkg: str) -> str:
    for sep in ("==", ">=", "<=", ">", "<"):
        if sep in pkg:
            return pkg.split(sep, 1)[0]
    return pkg


def _extract_pip_install_targets(parts: list) -> Optional[list]:
    if not parts:
        return None

    if parts[0] == "pip":
        if "install" not in parts:
            return None
        idx = parts.index("install")
        targets = [p for p in parts[idx + 1:] if not p.startswith("-")]
        return targets

    if parts[0] in ("python", "python3"):
        if "-m" in parts:
            for i in range(len(parts) - 1):
                if parts[i] == "-m" and parts[i + 1] == "pip":
                    if "install" not in parts[i + 2:]:
                        return None
                    idx = parts.index("install", i + 2)
                    targets = [p for p in parts[idx + 1:] if not p.startswith("-")]
                    return targets
        return None

    return None


def _validate_pip_install(parts: list) -> Optional[str]:
    targets = _extract_pip_install_targets(parts)
    if targets is None:
        return None
    if not targets:
        return "Error: pip install requires at least one package"

    normalized = [_normalize_pkg_name(t) for t in targets]
    disallowed = [t for t in normalized if t not in ALLOWED_PIP_PACKAGES]

    if disallowed:
        return (
            "Error: pip install not allowed for "
            f"{disallowed}. Allowed: {sorted(ALLOWED_PIP_PACKAGES)}"
        )

    return None


# -------------------------
# LOOP GUARD
# -------------------------

ACTION_HISTORY = []
MAX_REPEAT = 4


def is_repeated_action(action: dict) -> bool:
    tool = action.get("tool", "")

    # done and read_file are never considered repeated (always safe)
    if tool in ("done", "read_file"):
        return False

    # --- LOOP FIX START ---
    # create_file は上書き対応済みなので繰り返しを許容
    # _inject_run_if_needed() が run を注入して収束させる
    if tool == "create_file":
        ACTION_HISTORY.append(action)
        if len(ACTION_HISTORY) > 50:
            ACTION_HISTORY.pop(0)
        return False
    # --- LOOP FIX END ---

    # run immediately after an edit is a legitimate test-fix-retest cycle
    if tool == "run" and ACTION_HISTORY:
        prev_tool = ACTION_HISTORY[-1].get("tool", "")
        if prev_tool in ("edit_file", "diff_edit", "append_file",
                         "add_function", "ast_replace_function", "apply_patch"):
            ACTION_HISTORY.append(action)
            if len(ACTION_HISTORY) > 50:
                ACTION_HISTORY.pop(0)
            return False

    ACTION_HISTORY.append(action)

    if ACTION_HISTORY.count(action) >= MAX_REPEAT:
        return True

    if len(ACTION_HISTORY) > 50:
        ACTION_HISTORY.pop(0)

    return False


def reset_session() -> None:
    """新しいエージェントセッション開始時に呼ぶ。ACTION_HISTORY をクリアする。"""
    global ACTION_HISTORY
    ACTION_HISTORY.clear()
