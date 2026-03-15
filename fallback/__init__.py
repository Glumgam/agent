"""
fallback/__init__.py — ディスパッチャー
タスク種別を検出してハンドラーに振り分ける
"""

from typing import Dict, List

from fallback.fallback_helpers import (
    _extract_all_paths,
    _extract_file_candidates,
    _extract_filename,
    _extract_pdf_paths,
    _extract_urls,
    _extract_all_quoted,
    _is_pdf_task,
    _is_test_task,
    _looks_like_success,
    _needs_time_code,
)
from fallback.fallback_file import handle_file
from fallback.fallback_shell import handle_pdf
from fallback.fallback_test import handle_test
from fallback.fallback_edit import handle_edit
from fallback.fallback_misc import handle_misc

# Re-export Ollama error utilities for backward compatibility
from fallback.fallback_misc import is_ollama_error_text, is_ollama_error_action  # noqa


def _detect_task_type(
    task: str,
    history: List[Dict],
) -> str:
    """タスク種別を文字列で返す。"""
    task_lower = task.lower()

    pdf_paths = _extract_pdf_paths(task)
    urls = _extract_urls(task)
    filename = _extract_filename(task)
    quoted = _extract_all_quoted(task)
    old_text = quoted[0] if len(quoted) >= 2 else None
    new_text = quoted[1] if len(quoted) >= 2 else None

    wants_replace = bool(old_text and new_text) and any(
        k in task_lower for k in ["変更", "change", "replace", "edit", "rewrite", "に変更", "置換"]
    )
    wants_time = _needs_time_code(task_lower)

    if bool(filename and (wants_replace or wants_time)):
        return "edit"
    if _is_test_task(task_lower):
        return "test"
    if _is_pdf_task(task_lower) or bool(pdf_paths) or bool(urls):
        return "pdf"
    if any(k in task_lower for k in ["move", "移動", "delete", "削除", "remove"]):
        return "file"
    return "misc"


def fallback_action(task: str, history: List[Dict]) -> Dict:
    """
    Offline policy for Stage 1〜6 tasks (simple read/replace/append/test/repair/pdf).
    タスク種別を検出し、対応するハンドラーに委譲する。
    """
    task_lower = task.lower()

    # 共通で必要な変数を事前に抽出
    pdf_paths = _extract_pdf_paths(task)
    urls = _extract_urls(task)
    filename = _extract_filename(task)
    quoted = _extract_all_quoted(task)
    old_text = quoted[0] if len(quoted) >= 2 else None
    new_text = quoted[1] if len(quoted) >= 2 else None

    wants_replace = bool(old_text and new_text) and any(
        k in task_lower for k in ["変更", "change", "replace", "edit", "rewrite", "に変更", "置換"]
    )
    wants_time = _needs_time_code(task_lower)

    is_edit = bool(filename and (wants_replace or wants_time))
    is_test = _is_test_task(task_lower)
    is_pdf = _is_pdf_task(task_lower) or bool(pdf_paths) or bool(urls)
    is_file_ops = any(k in task_lower for k in ["move", "移動", "delete", "削除", "remove"])

    # 早期終了: 特定タスク以外で最後の操作が成功済みなら done
    if history and not (is_edit or is_test or is_pdf or is_file_ops):
        last_result = str(history[-1].get("result", ""))
        if _looks_like_success(last_result):
            return {
                "thought": "前の操作が成功したため終了する",
                "tool": "done"
            }

    if is_file_ops:
        return handle_file(task, history)

    if is_pdf:
        return handle_pdf(task, history)

    if is_test:
        return handle_test(task, history)

    if is_edit and filename:
        return handle_edit(task, history, filename, old_text, new_text, wants_replace, wants_time)

    return handle_misc(task, history)
