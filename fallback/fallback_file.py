"""
fallback/fallback_file.py — ファイル操作系フォールバックハンドラー
move / delete / make_dir タスクを処理する
"""

import os
from typing import Dict, List

from fallback.fallback_helpers import (
    _extract_file_candidates,
    _extract_filename,
    _extract_output_dir,
    _history_has_delete,
    _history_has_move,
    _history_has_tool,
)


def handle_file(task: str, history: List[Dict]) -> Dict:
    task_lower = task.lower()

    file_candidates = _extract_file_candidates(task)
    filename = _extract_filename(task)

    move_task = any(k in task_lower for k in ["move", "移動"])
    delete_task = any(k in task_lower for k in ["delete", "削除", "remove"])
    list_task = any(k in task_lower for k in ["list", "一覧", "confirm", "確認"])

    src = file_candidates[0] if file_candidates else (filename or "")
    dest_dir = _extract_output_dir(task)
    if dest_dir.startswith("workspace/"):
        dest_dir = dest_dir[len("workspace/"):]
    if dest_dir and not dest_dir.endswith("/"):
        dest_dir = dest_dir + "/"

    dest = ""
    if dest_dir and src:
        dest = f"{dest_dir}{os.path.basename(src)}"
    elif len(file_candidates) > 1:
        dest = file_candidates[1]

    wants_create_file = any(
        k in task_lower
        for k in ["create", "make", "new file", "作成", "作る", "新規"]
    )

    if wants_create_file and src and not _history_has_tool(history, "create_file", src):
        return {
            "thought": "一時ファイルを作成する",
            "tool": "create_file",
            "path": src,
            "content": "temporary file\n"
        }

    if dest_dir and not _history_has_tool(history, "make_dir", dest_dir.rstrip("/")):
        return {
            "thought": "移動先ディレクトリを作成する",
            "tool": "make_dir",
            "path": dest_dir.rstrip("/")
        }

    if move_task and src and dest and not _history_has_move(history, src, dest):
        return {
            "thought": "ファイルを移動する",
            "tool": "move_file",
            "source": src,
            "destination": dest
        }

    list_path = dest_dir.rstrip("/") if dest_dir else (os.path.dirname(dest) or "")
    if list_task and list_path and not _history_has_tool(history, "read_directory", list_path):
        return {
            "thought": "ディレクトリ内容を確認する",
            "tool": "read_directory",
            "path": list_path
        }

    if delete_task:
        target = dest or src
        if target and not _history_has_delete(history, target):
            return {
                "thought": "ファイルを削除する",
                "tool": "delete_file",
                "path": target
            }

    return {
        "thought": "ファイル操作タスクが完了したため終了する",
        "tool": "done"
    }
