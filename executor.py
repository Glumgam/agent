"""
executor.py — ファサード

各サブモジュールから re-export し、後方互換を維持する。
ツール登録・ディスパッチのみここで行う。
"""

from security import *          # noqa: F401,F403  ALLOWED_COMMANDS, is_repeated_action, reset_session …
from command_runner import *    # noqa: F401,F403  run_command, _diagnose_python_error …
from tools_file import *        # noqa: F401,F403  tool_create_file … tool_delete_file
from tools_run import *         # noqa: F401,F403  tool_run … tool_ask_user
from tools_research import *    # noqa: F401,F403  tool_search_web … tool_self_improve_agent

from tool_registry import registry

def _lazy_ensure_code_index():
    """コードインデックスを遅延で構築（BERT起動コストを初回使用時まで延期）"""
    try:
        from code_indexer import ensure_index as ensure_code_index
        ensure_code_index()
    except Exception:
        pass


_LAST_SEARCH_URL = ""
_last_tool = ""   # create→done ガード用
_last_path = ""   # 最後に作成/編集したファイルパス


def _pick_first_url(result) -> str:
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                url = item.get("url")
                if url:
                    return url
    return ""


# -------------------------
# TOOL REGISTRATION
# -------------------------

def _register_tools():
    registry.register("create_file",          tool_create_file)
    registry.register("write_file",           tool_write_file)
    registry.register("edit_file",            tool_edit_file)
    registry.register("read_file",            tool_read_file)
    registry.register("append_file",          tool_append_file)
    registry.register("diff_edit",            tool_diff_edit)
    registry.register("make_dir",             tool_make_dir)
    registry.register("read_directory",       tool_read_directory)
    registry.register("run",                  tool_run)
    registry.register("search_web",           tool_search_web)
    registry.register("fetch_page",           tool_fetch_page)
    registry.register("extract_text",         tool_extract_text)
    registry.register("summarize_text",       tool_summarize_text)
    registry.register("create_research_plan", tool_create_research_plan)
    registry.register("search_knowledge",     tool_search_knowledge)
    registry.register("search_code",          tool_search_code)
    registry.register("run_task_loop",        tool_run_task_loop)
    registry.register("self_improve_agent",   tool_self_improve_agent)
    registry.register("generate_report",      tool_generate_report)
    registry.register("run_test",             tool_run_test)
    registry.register("move_file",            tool_move_file)
    registry.register("delete_file",          tool_delete_file)
    registry.register("add_function",         tool_add_function)
    registry.register("ast_replace_function", tool_ast_replace_function)
    registry.register("apply_patch",          tool_apply_patch)
    registry.register("run_tests",            tool_run_tests)
    registry.register("generate_test",        tool_generate_test)
    registry.register("ask_user",             tool_ask_user)
    registry.register("answer",               tool_answer)
    registry.register("done",                 tool_done)
    # --- WEB SEARCH START ---
    from tools.web_search import tool_web_search
    registry.register("web_search", tool_web_search)
    # --- WEB SEARCH END ---
    # --- NEWS/RANKING START ---
    from tools.web_search import tool_fetch_news, tool_fetch_ranking
    registry.register("fetch_news",    tool_fetch_news)
    registry.register("fetch_ranking", tool_fetch_ranking)
    # --- NEWS/RANKING END ---
    # --- SECRETARY TOOLS START ---
    from tools.web_search import tool_search_places, tool_fetch_tech_info
    registry.register("search_places",   lambda a: tool_search_places(
        a.get("query", ""), a.get("location", ""), int(a.get("limit", 5))))
    registry.register("fetch_tech_info", lambda a: tool_fetch_tech_info(
        a.get("query", a.get("topic", "")), a.get("source", "auto")))
    # --- SECRETARY TOOLS END ---


_register_tools()

# --- LOOP FIX START ---
# LLM が使うべき有効なツール名（これ以外はエラー扱い）
VALID_TOOLS = {
    "create_file", "edit_file", "read_file", "append_file",
    "delete_file", "make_dir", "read_directory", "diff_edit",
    "run", "run_test", "done", "ask_user", "answer",
    "web_search",   # --- WEB SEARCH START ---
    "fetch_news", "fetch_ranking",         # --- NEWS/RANKING START ---
    "search_places", "fetch_tech_info",   # --- SECRETARY TOOLS START ---
}
# --- LOOP FIX END ---


# -------------------------
# DISPATCH
# -------------------------

def _find_similar_tool(name: str) -> str:
    """編集距離で最も近いツール名を返す"""
    import difflib
    tools = registry.list_tools()
    matches = difflib.get_close_matches(name, tools, n=1, cutoff=0.4)
    return matches[0] if matches else sorted(tools)[0]


def execute_tool(action: dict):
    global _LAST_SEARCH_URL, _last_tool, _last_path
    tool = action.get("tool")

    if not tool:
        return "Error: no tool specified"

    # --- LOOP FIX START ---
    # 無効ツール名を即座にブロック（LLM が run_task_loop 等を生成した場合）
    if tool not in VALID_TOOLS:
        import difflib
        closest = difflib.get_close_matches(tool, sorted(VALID_TOOLS), n=1, cutoff=0.3)
        suggestion = closest[0] if closest else "run"
        return (
            f"ERROR: '{tool}' は無効なツール名。"
            f"最も近い有効ツール: '{suggestion}'。"
            f"有効: {sorted(VALID_TOOLS)}"
        )
    # --- LOOP FIX END ---

    # [Guard] create_file/edit_file → done without running = rejected
    if tool == "done" and _last_tool in ("create_file", "edit_file", "diff_edit"):
        blocked_path = _last_path or "the file"
        # reset so the user can retry done after running
        _last_tool = ""
        return (
            f"WARNING: done rejected. You created/edited '{blocked_path}' "
            f"but never ran it. "
            f'Run it first: {{"tool": "run", "command": "python {blocked_path}"}}. '
            f"Then declare done after confirming the output."
        )

    if is_repeated_action(action):
        return "Error: repeated action detected (loop guard)"

    if tool == "fetch_page" and not action.get("url") and _LAST_SEARCH_URL:
        action["url"] = _LAST_SEARCH_URL

    # code_search を初めて使う時だけインデックスを遅延構築
    if tool == "search_code":
        _lazy_ensure_code_index()

    try:
        handler = registry.get(tool)
    except KeyError:
        similar = _find_similar_tool(tool)
        valid = sorted(registry.list_tools())
        return (
            f"ERROR: Unknown tool '{tool}'. "
            f"Did you mean '{similar}'? "
            f"Valid tools: {valid}"
        )

    try:
        result = handler(action)
    except KeyError as e:
        return f"Error: missing argument '{e.args[0]}' for tool '{tool}'"
    except Exception as e:
        return f"Error: {e}"

    if tool == "search_web":
        selected = _pick_first_url(result)
        if selected:
            _LAST_SEARCH_URL = selected

    # run 後は create guard をリセット（実行確認済み）
    if tool == "run":
        _last_tool = ""
        _last_path = ""
    elif tool in ("create_file", "edit_file", "diff_edit"):
        _last_tool = tool
        _last_path = action.get("path", "")

    return str(result)
