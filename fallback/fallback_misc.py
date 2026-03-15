"""
fallback/fallback_misc.py — 汎用フォールバック + Ollama エラー検出
リスト・追記・作成・読み込みの汎用処理と is_ollama_error_* ユーティリティ
"""

from typing import Dict, List, Optional

from fallback.fallback_helpers import (
    _extract_filename,
    _extract_quoted_text,
    _line_with_newline,
)


# -------------------------
# OLLAMA ERROR DETECTION
# -------------------------

_OLLAMA_ERROR_MARKERS = [
    "Ollama接続エラー",
    "Max retries exceeded",
    "Failed to establish a new connection",
    "Connection refused",
    "Operation not permitted",
]


def is_ollama_error_text(text: str) -> bool:
    if not text:
        return False
    return any(m in text for m in _OLLAMA_ERROR_MARKERS)


def is_ollama_error_action(action: Optional[Dict]) -> bool:
    if not action:
        return False
    thought = str(action.get("thought", ""))
    return is_ollama_error_text(thought)


# -------------------------
# GENERIC / MISC HANDLER
# -------------------------

def handle_misc(task: str, history: List[Dict]) -> Dict:
    task_lower = task.lower()
    filename = _extract_filename(task)

    if any(k in task_lower for k in [
        "list files", "show files", "files in", "list the files",
        "ディレクトリ", "一覧", "ファイル一覧", "list directory"
    ]):
        return {
            "thought": "ワークスペースの内容を確認する",
            "tool": "read_directory",
            "path": ""
        }

    quoted = _extract_quoted_text(task)

    if any(k in task_lower for k in ["append", "add line", "追記", "追加"]):
        content = quoted or "# appended line"
        return {
            "thought": "指定ファイルに追記する",
            "tool": "append_file",
            "path": filename or "",
            "content": _line_with_newline(content)
        }

    if any(k in task_lower for k in ["create", "make", "new file", "作成", "作る", "新規"]):
        if filename:
            content = ""
            if "print" in task_lower or "prints" in task_lower:
                message = quoted or "Hello World"
                content = f"print(\"{message}\")\n"
            return {
                "thought": "新規ファイルを作成する",
                "tool": "create_file",
                "path": filename,
                "content": content
            }

    if any(k in task_lower for k in ["read", "open", "show", "表示", "見る"]):
        if filename:
            return {
                "thought": "指定ファイルを読む",
                "tool": "read_file",
                "path": filename
            }

    return {
        "thought": "オフラインで判断できないため終了する",
        "tool": "done"
    }
