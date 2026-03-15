"""
fallback/fallback_edit.py — テキスト編集系フォールバックハンドラー
文字列置換・時刻コード追加タスクを処理する
"""

from typing import Dict, List, Optional

from fallback.fallback_helpers import (
    _history_has_tool,
    _last_index,
    _last_read_content,
    _looks_like_success,
    _needs_time_code,
)


def _diff_edit_attempted(
    history: List[Dict], filename: str, old_text: Optional[str], new_text: Optional[str]
) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "diff_edit":
            continue
        if action.get("path") != filename:
            continue
        if action.get("old") == old_text and action.get("new") == new_text:
            return True
    return False


def _diff_edit_attempt_count(
    history: List[Dict], filename: str, old_text: Optional[str], new_text: Optional[str]
) -> int:
    count = 0
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "diff_edit":
            continue
        if action.get("path") != filename:
            continue
        if action.get("old") == old_text and action.get("new") == new_text:
            count += 1
    return count


def _last_diff_edit_index(
    history: List[Dict], filename: str, old_text: Optional[str], new_text: Optional[str]
) -> int:
    for i in range(len(history) - 1, -1, -1):
        action = history[i].get("action", {})
        if action.get("tool") != "diff_edit":
            continue
        if action.get("path") != filename:
            continue
        if action.get("old") == old_text and action.get("new") == new_text:
            return i
    return -1


def _last_diff_edit_result(
    history: List[Dict], filename: str, old_text: Optional[str], new_text: Optional[str]
) -> str:
    for i in range(len(history) - 1, -1, -1):
        action = history[i].get("action", {})
        if action.get("tool") != "diff_edit":
            continue
        if action.get("path") != filename:
            continue
        if action.get("old") == old_text and action.get("new") == new_text:
            return str(history[i].get("result", ""))
    return ""


def _diff_edit_succeeded(
    history: List[Dict], filename: str, old_text: Optional[str], new_text: Optional[str]
) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "diff_edit":
            continue
        if action.get("path") != filename:
            continue
        if action.get("old") != old_text or action.get("new") != new_text:
            continue
        result = str(h.get("result", ""))
        if _looks_like_success(result):
            return True
    return False


def _has_appended_time(history: List[Dict], filename: str) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "append_file":
            continue
        if action.get("path") != filename:
            continue
        content = str(action.get("content", ""))
        if "datetime" in content:
            return True
    last_content = _last_read_content(history, filename)
    return "datetime" in last_content


def handle_edit(
    task: str,
    history: List[Dict],
    filename: str,
    old_text: Optional[str],
    new_text: Optional[str],
    wants_replace: bool,
    wants_time: bool,
) -> Dict:
    task_lower = task.lower()

    last_content = _last_read_content(history, filename)
    has_read = _history_has_tool(history, "read_file", filename)

    if not has_read and ("read" in task_lower or "読み" in task_lower or "読み込み" in task_lower or "open" in task_lower):
        return {
            "thought": "編集前にファイル内容を読む",
            "tool": "read_file",
            "path": filename
        }

    if wants_replace and old_text and new_text:
        last_diff_result = _last_diff_edit_result(history, filename, old_text, new_text)
        last_diff_index = _last_diff_edit_index(history, filename, old_text, new_text)
        last_read_index = _last_index(history, "read_file", filename)

        if last_diff_result and "Error" in last_diff_result and last_read_index < last_diff_index:
            return {
                "thought": "置換に失敗したため再読して確認する",
                "tool": "read_file",
                "path": filename
            }

        if not _diff_edit_succeeded(history, filename, old_text, new_text):
            if _diff_edit_attempt_count(history, filename, old_text, new_text) < 2:
                return {
                    "thought": "指定文字列を置換する",
                    "tool": "diff_edit",
                    "path": filename,
                    "old": old_text,
                    "new": new_text
                }
            return {
                "thought": "置換に失敗したため終了する",
                "tool": "done"
            }

    if wants_time and not _has_appended_time(history, filename):
        has_datetime = "import datetime" in last_content or "from datetime" in last_content
        if has_datetime:
            snippet = "\nprint(datetime.datetime.now().isoformat())\n"
        else:
            snippet = "\nimport datetime\nprint(datetime.datetime.now().isoformat())\n"
        return {
            "thought": "現在時刻を表示するコードを追加する",
            "tool": "append_file",
            "path": filename,
            "content": snippet
        }

    return {
        "thought": "編集タスクが完了したため終了する",
        "tool": "done"
    }
