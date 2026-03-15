import sys

from llm import ask_coder as ask
from llm import ask_planner
from executor import execute_tool, VALID_TOOLS, reset_session
from project_map import scan_project
from memory import load_memory, add_memory, format_memory, save_memory
from parser import extract_json
from offline_fallback import fallback_action, is_ollama_error_action
from reflection import reflect
from tool_learning import save_pattern
from planner_light import plan
from cognition.tree_of_thoughts import generate_candidates, select_best
from tools.code_search import search_code
from debug_loop import should_debug, analyze_error
from tools.diff_patch import apply_patch as apply_patch_file
from self_improve import analyze_failure, propose_fix


MAX_STEPS = 30
MAX_HISTORY = 6
MAX_PARSE_RETRIES = 2
CONTEXT_CHAR_BUDGET = 6000  # ≈ 9000〜12000トークン (num_ctx=16384, 日本語÷2想定)
MAX_DEBUG_STEPS = 5
MAX_SELF_IMPROVE = 1


EDIT_CONTEXT_TOOLS = {
    "edit_file",
    "diff_edit",
    "append_file",
    "add_function",
    "ast_replace_function",
    "apply_patch",
}

_code_context_cache = {}


# -------------------------
# TASK CLASSIFICATION
# -------------------------

def classify_task(task: str) -> str:
    t = (task or "").strip().lower()
    if not t:
        return "unknown"

    coding_kw = [
        "code", "python", "script", "bug", "error", "traceback", "stack trace",
        "repo", "repository", "function", "class", "module", "tests", "pytest",
        ".py", ".js", ".ts", "refactor", "lint", "build",
    ]
    automation_kw = [
        "move", "copy", "delete", "rename", "directory", "folder", "file",
        "archive", "backup", "zip", "unzip", "shell", "command", "system",
        "cron", "schedule", "pipeline", "batch",
    ]
    research_kw = [
        "research", "search", "survey", "compare", "sources", "latest",
        "news", "web", "url", "wikipedia", "find", "summary",
        "調べ", "検索", "比較", "最新", "ニュース", "出典",
    ]
    question_kw = [
        "what", "when", "where", "who", "why", "how",
        "what is", "define", "meaning", "explain",
        "教えて", "とは", "何", "どこ", "誰", "ベスト", "ランキング",
        "いつ", "なぜ", "どう",
    ]

    for kw in coding_kw:
        if kw in t:
            return "coding"
    for kw in automation_kw:
        if kw in t:
            return "automation"
    for kw in research_kw:
        if kw in t:
            return "research"
    if any(kw in t for kw in question_kw):
        return "question"
    if len(t) <= 120 and "?" in t:
        return "question"
    return "unknown"


def _strategy_hint(category: str) -> str:
    if category == "question":
        return "Answer directly using the LLM. Do NOT use web search unless explicitly required."
    if category == "research":
        return "Use the web research pipeline: search_web → fetch_page → extract_text → summarize_text → generate_report → answer."
    if category == "coding":
        return "Prefer code tools: read_file before edits, use ast_replace_function when possible, run tests after edits."
    if category == "automation":
        return "Prefer filesystem and run tools: read_directory, make_dir, move_file, delete_file, run."
    return "Use best judgment based on the task."


def reflect_answer(task: str, answer: str) -> str:
    prompt = (
        "You are reviewing an AI answer as a strict critic.\n"
        "If the answer contains errors, rewrite the answer completely.\n\n"
        f"Task:\n{task}\n\n"
        f"Answer:\n{answer}\n\n"
        "Check:\n"
        "1. Is the answer factually correct?\n"
        "2. Does it fully answer the question?\n"
        "3. Are there mistakes or hallucinations?\n"
        "4. Can the answer be improved?\n\n"
        "If the answer is correct, return the answer as-is.\n"
        "If errors are found, rewrite the answer completely and return only the improved answer.\n"
        "Do not repeat the same mistakes.\n"
    )
    try:
        reviewed = ask_planner(prompt)
        return reviewed.strip() or answer
    except Exception:
        return answer


# -------------------------
# HISTORY FORMAT
# -------------------------

def format_history(history, budget_chars: int = 8000):

    entries = history[-MAX_HISTORY:]
    lines = []

    for h in entries:

        action = h.get("action", {})
        tool = action.get("tool", "unknown")
        path = action.get("path", "")
        thought = action.get("thought", "")
        result = str(h.get("result", ""))

        if len(thought) > 200:
            thought = "...[truncated]...\n" + thought[-200:]

        if len(result) > 600:
            result = "...[truncated]...\n" + result[-600:]

        lines.append(
            f"STEP: {tool}({path})\n"
            f"THOUGHT: {thought}\n"
            f"RESULT: {result}"
        )

    while lines:
        joined = "\n".join(lines)
        if len(joined) <= budget_chars:
            break
        lines.pop(0)

    return "\n".join(lines)


# -------------------------
# LOOP DETECTION
# -------------------------

def _action_signature(entry: dict) -> str:
    a = entry.get("action", {})
    tool = a.get("tool", "")
    if tool == "run":
        return f"run::{a.get('command', '')}"
    return f"{tool}::{a.get('path', '')}"


def detect_loop(history: list) -> bool:
    WINDOW = 8
    REPEAT_THRESHOLD = 5

    real_steps = [h for h in history if not h.get("action", {}).get("_auto")]

    if len(real_steps) < REPEAT_THRESHOLD:
        return False

    # last action is done → never a loop
    last_action = real_steps[-1].get("action", {})
    if last_action.get("tool") == "done":
        return False

    recent = real_steps[-WINDOW:]
    sigs = [_action_signature(e) for e in recent]

    # Condition A: same signature repeated REPEAT_THRESHOLD times at end
    tail_sigs = sigs[-REPEAT_THRESHOLD:]
    if len(set(tail_sigs)) != 1:
        return False

    # --- LOOP FIX START ---
    # Layer-3: create_file/edit_file loop without run → let agent keep trying
    # create_file: _inject_run_if_needed handles forced-run
    # edit_file:   agent is refining code; do NOT false-positive loop-detect without run
    if all(s.startswith(("create_file::", "edit_file::")) for s in tail_sigs):
        path = tail_sigs[0].split("::", 1)[1] if "::" in tail_sigs[0] else ""
        has_run = any(
            e.get("action", {}).get("tool") == "run"
            and path in str(e.get("action", {}).get("command", ""))
            for e in recent
        )
        if not has_run:
            # No run found → inject (create) or LLM retry (edit) will handle it
            return False
    # --- LOOP FIX END ---

    # Condition B: observations unchanged OR all failing with no improvement
    recent_obs = [str(e.get("result", "")) for e in recent[-REPEAT_THRESHOLD:]]

    # If any step succeeded (exit code 0) → not a loop, it's making progress
    has_improvement = any("exit code 0" in obs for obs in recent_obs)
    if has_improvement:
        return False

    # All observations identical → stuck only if the obs is a failure
    if len(set(recent_obs)) == 1:
        single_obs = recent_obs[0]
        is_failure = (
            "exit code 1" in single_obs
            or "Error:" in single_obs
            or "error" in single_obs.lower()[:100]
        )
        if is_failure:
            print(f"[LOOP DETECTED] sigs={tail_sigs} obs_unique=1 (failure)")
            return True
        # Same success message × 5 = truly stuck
        tail_sigs5 = sigs[-5:] if len(sigs) >= 5 else sigs
        if len(tail_sigs5) >= 5 and len(set(tail_sigs5)) == 1:
            print(f"[LOOP DETECTED] sigs={tail_sigs5} obs_unique=1 (success×5)")
            return True
        return False

    # All failing (but varying error messages) → also a loop
    all_failing = all(
        "exit code 1" in obs or "Error" in obs or "error" in obs
        for obs in recent_obs
    )
    if all_failing:
        print(f"[LOOP DETECTED] sigs={tail_sigs} all_failing=True obs={[o[:80] for o in recent_obs]}")
        return True

    return False


# --- LOOP FIX START ---
def _inject_run_if_needed(action: dict, history: list) -> dict:
    """create_file が繰り返される場合（run を忘れた）、強制的に run を注入する。
    edit_file は正当な修正操作なので inject しない。"""
    if action.get("tool") != "create_file":
        return action
    path = action.get("path", "")
    if not path.endswith(".py"):
        return action
    recent = history[-5:] if len(history) >= 5 else history
    # 直近に同じファイルへの run が既にあるなら注入不要
    run_exists = any(
        e.get("action", {}).get("tool") == "run"
        and path in e.get("action", {}).get("command", "")
        for e in recent
    )
    # 直近に同じパスへの create/edit が既にあるなら 2 回目以降 → inject run
    create_count = sum(
        1 for e in recent
        if e.get("action", {}).get("tool") in ("create_file", "edit_file")
        and e.get("action", {}).get("path", "") == path
    )
    if create_count >= 0 and not run_exists:
        # --- LOOP FIX START ---
        # sys.argv を使うスクリプトには引数を渡す必要があるか確認
        content = action.get("content", "")
        uses_argv = "sys.argv" in content
        if uses_argv:
            # sys.argv[1] 等を使う場合はワークスペースのパスを引数に渡す
            from project_map import WORKSPACE
            run_cmd = f"python {path} {WORKSPACE}"
        else:
            run_cmd = f"python {path}"
        # --- LOOP FIX END ---
        print(f"[INJECT] {path} 未実行 → run を注入: {run_cmd}")
        return {
            "tool": "run",
            "command": run_cmd,
            "thought": f"（自動注入）{path} を実行して結果を確認する",
            "_auto": True,
        }
    return action
# --- LOOP FIX END ---


def _consecutive_failures(history):
    count = 0
    for h in reversed(history):
        action = h.get("action", {})
        tool = action.get("tool", "")
        result = h.get("result", "")
        if _is_failure(result, tool):
            count += 1
        else:
            break
    return count


def _attempt_self_improve(task, history, reason):
    analysis = analyze_failure(task, history, reason)
    patch = propose_fix(analysis)
    if not isinstance(patch, dict) or patch.get("error"):
        return False
    path = patch.get("path", "")
    content = patch.get("content", "")
    if not path or content is None:
        return False
    try:
        result = apply_patch_file(path, content)
    except Exception as e:
        result = f"Error: {e}"
    history.append({
        "action": {"tool": "_self_improve", "path": path},
        "result": result
    })
    return isinstance(result, str) and result.startswith("Success")


# -------------------------
# TREE-OF-THOUGHTS GUARD
# -------------------------

def _should_use_tot(task: str, step: int, history: list) -> bool:
    # 短いタスクはスキップ (単純なファイル作成等)
    if len(task) < 100:
        return False
    # 初期ステップはスキップ (plan に従うだけなので)
    if step <= 2:
        return False
    # 直近3ステップでエラーが2件以上の場合のみ ToT を使う
    recent_errors = sum(
        1 for h in history[-3:]
        if "exit code 1" in str(h) or "Error" in str(h)
    )
    return recent_errors >= 2


# -------------------------
# SUCCESS DETECTION
# -------------------------

def detect_success(action, result):
    tool = action.get("tool", "")

    # 明示的 done
    if tool in ("done", "answer"):
        return True

    # 実行成功
    if tool in ("run", "run_test"):
        return "exit code 0" in str(result)

    return False


# -------------------------
# REPEATED RUN DETECTION (NEW)
# -------------------------

def repeated_run(history):

    runs = [
        h for h in history
        if h.get("action", {}).get("tool") in ("run", "run_test")
    ]

    if len(runs) < 2:
        return False

    last = runs[-1]["action"].get("command") or ""
    prev = runs[-2]["action"].get("command") or ""

    return last == prev


def _history_has_command(history, command: str) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "run":
            continue
        if action.get("command") == command:
            return True
    return False


def _history_has_tool(history, tool: str, path: str = "") -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != tool:
            continue
        if path and action.get("path") != path:
            continue
        return True
    return False


def _history_has_test_activity(history) -> bool:
    for h in history:
        action = h.get("action", {})
        tool = action.get("tool", "")
        path = action.get("path", "") or ""
        if tool == "run_test":
            return True
        if path.startswith("tests/") or path.startswith("test_"):
            return True
    return False


def _extract_pdf_path(task: str) -> str:
    if not task:
        return ""
    import re
    scrubbed = re.sub(r"https?://[^\s'\"）)]+", "", task)
    m = re.findall(r"[A-Za-z0-9_./-]+\.pdf", scrubbed)
    if m:
        path = m[0]
        if path.startswith("workspace/"):
            path = path[len("workspace/"):]
        if path.startswith("./"):
            path = path[2:]
        return path
    return ""


def _pdf_to_html(path: str) -> str:
    if not path:
        return "result.html"
    if path.endswith(".pdf"):
        return path[:-4] + ".html"
    return path + ".html"


def reflect_action(action, result, history, task: str):

    tool = action.get("tool")

    if tool not in ("run", "run_test"):
        return None

    result_str = str(result)

    exit_ok = "[exit code 0]" in result_str

    needs_pytest = (
        "No module named pytest" in result_str
        or ("ModuleNotFoundError" in result_str and "pytest" in result_str)
        or ("command not found" in result_str and "pytest" in result_str)
    )

    if needs_pytest:
        cmd = "pip install pytest"
        if _history_has_command(history, cmd):
            return None
        return {
            "thought": "pytest が不足しているためインストールする",
            "tool": "run",
            "command": cmd,
            "_auto": True
        }

    needs_requests = (
        "No module named requests" in result_str
        or ("ModuleNotFoundError" in result_str and "requests" in result_str)
    )

    if needs_requests:
        cmd = "pip install requests"
        if _history_has_command(history, cmd):
            return None
        return {
            "thought": "requests が不足しているためインストールする",
            "tool": "run",
            "command": cmd,
            "_auto": True
        }

    needs_reportlab = (
        "No module named reportlab" in result_str
        or ("ModuleNotFoundError" in result_str and "reportlab" in result_str)
    )

    if needs_reportlab:
        cmd = "pip install reportlab"
        if _history_has_command(history, cmd):
            return None
        return {
            "thought": "reportlab が不足しているためインストールする",
            "tool": "run",
            "command": cmd,
            "_auto": True
        }

    task_lower = (task or "").lower()
    wants_test = any(k in task_lower for k in ["test", "pytest", "テスト"])

    if wants_test and not _history_has_test_activity(history):
        if not _history_has_tool(history, "read_directory", "tests"):
            return {
                "thought": "テストの有無を確認する",
                "tool": "read_directory",
                "path": "tests",
                "_auto": True
            }

    if "AssertionError" in result_str or "assert" in result_str:
        test_path = action.get("path") or ""
        if test_path and not _history_has_tool(history, "read_file", test_path):
            return {
                "thought": "テスト失敗の内容を確認する",
                "tool": "read_file",
                "path": test_path,
                "_auto": True
            }

    if tool == "run":
        cmd = action.get("command", "")
        if cmd.startswith("ls -l") and ("No such file" in result_str or "not found" in result_str):
            html_path = _pdf_to_html(_extract_pdf_path(task))
            ls_html = f"ls -l {html_path}"
            if not _history_has_command(history, ls_html):
                return {
                    "thought": "代替HTMLを確認する",
                    "tool": "run",
                    "command": ls_html,
                    "_auto": True
                }

    if tool == "run" and exit_ok:
        pdf_path = _extract_pdf_path(task)
        if pdf_path:
            ls_pdf = f"ls -l {pdf_path}"
            if not _history_has_command(history, ls_pdf):
                return {
                    "thought": "生成されたPDFを確認する",
                    "tool": "run",
                    "command": ls_pdf,
                    "_auto": True
                }

    if exit_ok:
        return None

    return None


# -------------------------
# PATH NORMALIZATION
# -------------------------

def normalize_path(path):

    if not path:
        return ""

    if path.startswith("workspace/"):
        return path[len("workspace/"):]

    return path


def normalize_command(command):

    if not command:
        return ""

    prefixes = ["python ", "python3 ", "pytest ", "pip "]

    for prefix in prefixes:
        if command.startswith(prefix + "workspace/"):
            command = command.replace("workspace/", "", 1)

    return command


def _is_failure(result, tool: str) -> bool:
    if isinstance(result, dict):
        if result.get("status") == "error":
            return True
    result_str = str(result)
    if tool in ("run", "run_test"):
        if "[exit code 0]" in result_str:
            return False
        if "[exit code" in result_str:
            return True
    lowered = result_str.lower()
    if lowered.startswith("error"):
        return True
    if "error:" in lowered or "tool error" in lowered:
        return True
    return False


# -------------------------
# CONTEXT PRELOAD
# -------------------------

def ensure_context_loaded(tool, path, file_cache):

    if tool not in EDIT_CONTEXT_TOOLS:
        return

    if not path:
        return

    if path in file_cache:
        return

    print(f"[auto-read] 編集前に読み込み: {path}")

    try:

        content = execute_tool({
            "tool": "read_file",
            "path": path
        })

        file_cache[path] = content

    except Exception as e:

        file_cache[path] = f"read failed: {e}"


# -------------------------
# PROMPT BUILDER
# -------------------------

def _trim(text: str, limit: int) -> str:
    """文字列を後ろから limit 文字に切り詰める。"""
    if len(text) <= limit:
        return text
    return "...(truncated)\n" + text[-limit:]


def build_agent_prompt(task, project_map, history, memory, step, category=None, strategy_hint=None):

    tools_text = "\n".join(VALID_TOOLS)

    # --- SKILL HINT START ---
    skill_hint_text = ""
    try:
        from skill_extractor import get_skill_hint
        skill_hint_text = get_skill_hint(task)
    except Exception:
        pass
    # --- SKILL HINT END ---

    if task not in _code_context_cache:
        try:
            _code_context_cache[task] = search_code(task) or []
        except Exception:
            _code_context_cache[task] = []

    code_results = _code_context_cache[task]

    code_lines = []
    for item in code_results[:3]:
        path = item.get("path", "")
        score = item.get("score", 0.0)
        snippet = item.get("snippet", "")
        if len(snippet) > 400:
            snippet = snippet[:400]
        if path or snippet:
            code_lines.append(f"{path} score={score}\n{snippet}")

    code_context = "\n\n".join(code_lines) if code_lines else "(no code context)"
    history_str = format_history(history)
    memory_str = format_memory(memory)
    project_str = project_map

    prompt = f"""
You are an autonomous software engineering agent.

Respond ONLY with valid JSON.

AVAILABLE TOOLS
---------------
{tools_text}

JSON FORMAT EXAMPLE
-------------------
{{
 "thought": "I will create hello.py",
 "tool": "create_file",
 "path": "hello.py",
 "content": "print('hello')"
}}

PREFERENCE
----------
When editing an existing function, prefer ast_replace_function over edit_file.

TASK
----
{task}

TASK CATEGORY
-------------
{category or "unknown"}

STRATEGY
--------
{strategy_hint or ""}

{skill_hint_text}CODE CONTEXT
------------
{code_context}

PROJECT STRUCTURE
-----------------
{project_str}

MEMORY
------
{memory_str}
HISTORY
-------
{history_str}

STEP
----
{step+1} / {MAX_STEPS}

Return the NEXT action in JSON.
"""

    # -------------------------
    # コンテキスト削減 (優先順位付き)
    # -------------------------
    if len(prompt) > CONTEXT_CHAR_BUDGET:
        # 1. code_context を 2000文字に制限
        code_context = _trim(code_context, 2000)
        # 2. history は直近5件のみ (format_history の budget を下げる)
        history_str = format_history(history, budget_chars=3000)
        # 3. memory_str を 500文字に制限
        memory_str = _trim(memory_str, 500)
        # 4. project_map を末尾50行に制限
        project_str = "\n".join(project_map.splitlines()[-50:])

        prompt = f"""
TASK:
{task}

TASK CATEGORY:
{category or "unknown"}

STRATEGY:
{strategy_hint or ""}

{skill_hint_text}CODE CONTEXT:
{code_context}

PROJECT:
{project_str}

MEMORY:
{memory_str}

HISTORY:
{history_str}

Return next action JSON.
"""

    pct = int(len(prompt) / CONTEXT_CHAR_BUDGET * 100)
    print(f"[CONTEXT] prompt={len(prompt)}chars / budget={CONTEXT_CHAR_BUDGET}chars ({pct}%)")

    return prompt


# -------------------------
# JSON REPAIR
# -------------------------

def ask_with_json_repair(prompt, first_response):

    response = first_response
    action = extract_json(response)

    if action:
        return action

    for _ in range(MAX_PARSE_RETRIES):

        repair_prompt = f"""
The previous output was not valid JSON.

Output:
{response[:500]}

Return ONLY valid JSON.
"""

        response = ask(repair_prompt)
        action = extract_json(response)

        if action:
            return action

    return None


# -------------------------
# AGENT LOOP
# -------------------------

def run_agent():

    reset_session()  # ACTION_HISTORYをセッション開始時にクリア

    print("=== ローカルAIエージェント起動 ===")

    print("タスク: ", end="", flush=True)

    if sys.stdin.isatty():
        task = sys.stdin.readline().strip()
    else:
        task = sys.stdin.read().strip()

    if not task:
        print("タスクが空です")
        return

    history = []
    file_cache = {}

    memory = load_memory()
    pending_action = None
    debug_steps = 0
    self_improve_attempts = 0

    print("\n[1/2] プロジェクトスキャン")
    project_map = scan_project()

    print("\n[2/2] 実行開始")

    task_category = classify_task(task)
    strategy = _strategy_hint(task_category)
    print(f"\n分類: {task_category}")
    print(f"戦略: {strategy}")

    plan_result = ""
    if task_category != "question":
        plan_result = plan(task)
        print("PLAN:")
        print(plan_result)
    else:
        print("PLAN: (skipped for question)")

    for step in range(MAX_STEPS):

        print(f"\n===== STEP {step+1} =====")

        if detect_loop(history):

            if self_improve_attempts < MAX_SELF_IMPROVE:
                print("⚠️ ループ検出 → 自己改善を試行")
                ok = _attempt_self_improve(task, history, "loop detected")
                self_improve_attempts += 1
                if ok:
                    continue
            print("⚠️ ループ検出 → 強制終了")
            break

        if pending_action:
            action = pending_action
            pending_action = None
        else:
            prompt = build_agent_prompt(
                task,
                project_map,
                history,
                memory,
                step,
                category=task_category,
                strategy_hint=strategy
            )

            if _should_use_tot(task, step, history):
                candidates = generate_candidates(prompt)
                action = select_best(candidates, task)
                print(f"[ToT] step={step+1} — 候補{len(candidates)}件生成、'{action.get('tool')}' を選択")
            else:
                print(f"[ToT] step={step+1} — スキップ (simple task)")
                response = ask(prompt)
                action = extract_json(response)

        if not action or is_ollama_error_action(action):

            if not action:
                history.append({
                    "action": {"tool": "_error"},
                    "result": "JSON parse failed"
                })

            action = fallback_action(task, history)

        thought = action.get("thought")
        tool = action.get("tool")

        print("THOUGHT:", thought)
        print("ACTION:", action)

        if tool == "answer":
            content = action.get("content", "").strip()
            if len(content) < 10:
                print("ANSWERガード: 内容が短すぎるため再推論")
                history.append({
                    "action": action,
                    "result": "answer content too short"
                })
                continue
            refined = reflect_answer(task, content)
            if refined.strip() and refined.strip() != content.strip():
                action = {
                    "tool": "answer",
                    "content": refined.strip(),
                    "thought": "回答を見直して改善した"
                }
                content = refined.strip()

        if tool in ("done", "answer"):
            print("完了")
            save_pattern(task, history)
            # --- SKILL LEARNING START ---
            try:
                from skill_extractor import extract_skill, save_skill
                _skill = extract_skill(task, history)
                if _skill:
                    save_skill(_skill)
            except Exception as _sk_err:
                print(f"  ⚠️ スキル抽出スキップ: {_sk_err}")
            # --- SKILL LEARNING END ---
            break

        if tool not in VALID_TOOLS:

            print("無効ツール:", tool)

            history.append({
                "action": action,
                "result": "invalid tool"
            })

            continue

        path = normalize_path(action.get("path"))

        if path:
            action["path"] = path

        command = normalize_command(action.get("command"))

        if command:
            action["command"] = command

        ensure_context_loaded(tool, path, file_cache)

        # --- LOOP FIX START ---
        action = _inject_run_if_needed(action, history)
        tool = action.get("tool")
        if action.get("_auto"):
            path = None
        # --- LOOP FIX END ---

        print("実行:", tool)

        try:

            result = execute_tool(action)

        except Exception as e:

            result = f"tool error: {e}"

        history.append({
            "action": action,
            "result": result
        })

        print("結果:", str(result)[:200])

        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]

        if should_debug(str(result)):
            fix_action = analyze_error(str(result), action)
            if fix_action and debug_steps < MAX_DEBUG_STEPS:
                debug_steps += 1
                print("AUTO DEBUG:", fix_action)
                pending_action = fix_action
                continue
        else:
            debug_steps = 0

        if _is_failure(result, tool) and _consecutive_failures(history) >= 3:
            if self_improve_attempts < MAX_SELF_IMPROVE:
                print("⚠️ 失敗が続いたため自己改善を試行")
                ok = _attempt_self_improve(task, history, result)
                self_improve_attempts += 1
                if ok:
                    continue

        # EDIT_CONTEXT_TOOLS auto-run removed (was using invalid tool "run_tests")
        # The inject + SYSTEM_PROMPT rules handle run-after-edit

        reflection = reflect(task, history)
        if reflection:
            print("REFLECT:", reflection.get("thought"))
            action = reflection
            continue

        # -------------------------
        # AUTO SUCCESS STOP (NEW)
        # -------------------------

        last_h = history[-1] if history else {}
        if detect_success(last_h.get("action", {}), last_h.get("result", "")) and repeated_run(history):

            print("\n✅ タスク成功と判断 → 自動終了")
            save_pattern(task, history)
            break

    print("\n終了処理")

    add_memory(memory, task, history)

    print("完了")


if __name__ == "__main__":

    try:
        run_agent()

    except KeyboardInterrupt:

        print("停止")

        sys.exit(0)
