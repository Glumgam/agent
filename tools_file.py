"""
tools_file.py — カテゴリC: ファイル系ツール

- tool_create_file / tool_write_file / tool_edit_file / tool_read_file
- tool_append_file / tool_diff_edit / tool_make_dir / tool_read_directory
- tool_add_function / tool_ast_replace_function / tool_apply_patch
- tool_move_file / tool_delete_file
"""

from tools.filesystem import (
    write_file,
    create_file,
    read_file,
    append_file,
    make_dir,
    read_directory,
    diff_edit,
)
from tools.ast_editor import add_function
from tools.ast_editor_safe import replace_function
from tools.diff_patch import apply_patch
from tools.system_tools import move_file, delete_file
from tool_result import ToolResult

_DONE_HINT = 'File written. Run it to verify output, then use {"tool": "done"} only after confirming the output is correct.'


def _ok(raw) -> bool:
    return not (isinstance(raw, str) and raw.startswith("Error"))


def tool_create_file(action: dict):
    path = action["path"]
    raw = create_file(path, action.get("content", ""))
    ok = _ok(raw)
    # filesystem.create_file now returns the run hint directly (overwrite or create)
    output = str(raw)
    return ToolResult(ok=ok, output=output)


def tool_write_file(action: dict):
    path = action["path"]
    raw = write_file(path, action.get("content", ""))
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_edit_file(action: dict):
    path = action["path"]
    new_content = action.get("content", "")

    old = read_file(path)
    if isinstance(old, str) and not old.startswith("Error"):
        if old == new_content:
            return ToolResult(ok=True, output="No changes needed")

    raw = write_file(path, new_content)
    ok = _ok(raw)
    output = str(raw)
    if ok:
        output = f"Successfully written to {path}. {_DONE_HINT}"
    return ToolResult(ok=ok, output=output)


def tool_read_file(action: dict):
    content = read_file(action["path"])

    if isinstance(content, str) and content.startswith("Error"):
        return ToolResult(ok=False, output=content)

    MAX_READ = 10000
    if len(content) > MAX_READ:
        content = content[:MAX_READ] + "\n...[truncated]..."

    return ToolResult(ok=True, output=content)


def tool_append_file(action: dict):
    raw = append_file(action["path"], action.get("content", ""))
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_diff_edit(action: dict):
    path = action["path"]
    old_text = action.get("old", "")
    new_text = action.get("new", "")

    result = diff_edit(path, old_text, new_text)

    if isinstance(result, str) and result.startswith("Error"):
        if not old_text:
            return ToolResult(ok=False, output=result)

        content = read_file(path)
        if isinstance(content, str) and content.startswith("Error"):
            return ToolResult(ok=False, output=result)

        count = content.count(old_text)
        if count == 1:
            replaced = content.replace(old_text, new_text, 1)
            raw = write_file(path, replaced)
            ok = _ok(raw)
            return ToolResult(ok=ok, output=str(raw))
        if count > 1:
            msg = "Error: multiple matches for old snippet; aborting safe replace"
            return ToolResult(ok=False, output=msg)

    ok = _ok(result)
    return ToolResult(ok=ok, output=str(result))


def tool_make_dir(action: dict):
    raw = make_dir(action["path"])
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_read_directory(action: dict):
    path = action.get("path", ".")
    raw = read_directory(path)
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_add_function(action: dict):
    code = action.get("content") or action.get("code", "")
    raw = add_function(action["path"], code)
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_ast_replace_function(action: dict):
    function_name = action.get("function_name") or action.get("function")
    new_code = action.get("content") or action.get("code") or action.get("new_code", "")
    raw = replace_function(action["path"], function_name, new_code)
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_apply_patch(action: dict):
    new_content = action.get("content") or action.get("new_content", "")
    raw = apply_patch(action["path"], new_content)
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_move_file(action: dict):
    raw = move_file(action["source"], action["destination"])
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))


def tool_delete_file(action: dict):
    raw = delete_file(action["path"])
    ok = _ok(raw)
    return ToolResult(ok=ok, output=str(raw))
