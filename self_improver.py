"""
self_improver.py — 失敗原因に基づいてエージェント自身のコードを修正するモジュール。
ルールベース修正（高速・確実）→ LLM生成修正（複雑なケース）の2層構造。
"""

# --- SELF IMPROVE START ---
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from self_evaluator import FailureType, EvalResult

AGENT_ROOT = Path(__file__).parent


def improve(eval_result: EvalResult) -> dict:
    strategy_map = {
        FailureType.LOOP_DETECTED: _fix_loop,
        FailureType.MAX_STEPS:     _fix_done_declaration,
        FailureType.INVALID_TOOL:  _fix_invalid_tool,
        FailureType.IMPORT_ERROR:  _fix_missing_import,
        FailureType.SYNTAX_ERROR:  _fix_syntax_with_llm,
        FailureType.NO_RUN:        _fix_no_run,
        FailureType.WRONG_OUTPUT:  _fix_wrong_output_with_llm,
        FailureType.TIMEOUT:       _fix_timeout,
        FailureType.UNKNOWN:       _fix_unknown_with_llm,
    }
    fixer = strategy_map.get(eval_result.failure_type)
    if not fixer:
        return {"applied": False, "strategy": "no_strategy",
                "files_modified": [], "description": "修正戦略なし"}
    print(f"  🔧 修正戦略: {eval_result.failure_type.value}")
    return fixer(eval_result)


def _fix_loop(result: EvalResult) -> dict:
    main_py = AGENT_ROOT / "main.py"
    content = main_py.read_text(encoding="utf-8")
    modified = False
    applied_change = ""
    for old, new in [
        ("REPEAT_THRESHOLD = 3", "REPEAT_THRESHOLD = 4"),
        ("REPEAT_THRESHOLD = 4", "REPEAT_THRESHOLD = 5"),
        ("WINDOW = 6", "WINDOW = 8"),
        ("WINDOW = 8", "WINDOW = 10"),
    ]:
        if old in content:
            content = content.replace(old, new, 1)
            modified = True
            applied_change = f"{old} → {new}"
            break
    if modified:
        main_py.write_text(content, encoding="utf-8")
        # --- GIT EVOLUTION START ---
        from evolution_tracker import record_evolution
        record_evolution(
            error_type="loop_detected",
            file_repaired="main.py",
            strategy="rule_loop_threshold_relaxed",
            description=f"detect_loop 閾値を緩和: {applied_change}",
            files_to_commit=["main.py"],
        )
        # --- GIT EVOLUTION END ---
    return {"applied": modified, "strategy": "loop_threshold_relaxed",
            "files_modified": ["main.py"] if modified else [],
            "description": "detect_loop の閾値を緩和"}


def _fix_done_declaration(result: EvalResult) -> dict:
    llm_py = AGENT_ROOT / "llm.py"
    content = llm_py.read_text(encoding="utf-8")
    injection = (
        "\nRULE 4b: After EACH successful run (exit code 0), "
        "declare done IMMEDIATELY. No extra steps.\n"
    )
    if "RULE 4b" not in content:
        marker = "[RULE #4"
        if marker in content:
            idx = content.find(marker)
            next_rule = content.find("[RULE #", idx + 1)
            if next_rule == -1:
                next_rule = content.find("You are an autonomous", idx)
            if next_rule != -1:
                content = content[:next_rule] + injection + content[next_rule:]
                llm_py.write_text(content, encoding="utf-8")
                # --- GIT EVOLUTION START ---
                from evolution_tracker import record_evolution
                record_evolution(
                    error_type="max_steps",
                    file_repaired="llm.py",
                    strategy="rule_done_prompt_strengthened",
                    description="SYSTEM_PROMPTにRULE 4b（done宣言強化）を注入",
                    files_to_commit=["llm.py"],
                )
                # --- GIT EVOLUTION END ---
                return {"applied": True, "strategy": "done_prompt_strengthened",
                        "files_modified": ["llm.py"], "description": "done宣言ルール強化"}
    return {"applied": False, "strategy": "already_done",
            "files_modified": [], "description": "既に強化済み"}


def _fix_invalid_tool(result: EvalResult) -> dict:
    llm_py = AGENT_ROOT / "llm.py"
    content = llm_py.read_text(encoding="utf-8")
    if "RULE 3b" not in content:
        injection = (
            "\nRULE 3b: NEVER use run_task_loop, execute, bash, "
            "shell, run_tests. These cause immediate ERROR.\n"
        )
        marker = "[RULE #3"
        if marker in content:
            idx = content.find(marker)
            next_rule = content.find("[RULE #", idx + 1)
            if next_rule != -1:
                content = content[:next_rule] + injection + content[next_rule:]
                llm_py.write_text(content, encoding="utf-8")
                return {"applied": True, "strategy": "invalid_tool_prompt_updated",
                        "files_modified": ["llm.py"], "description": "無効ツール名ルール強化"}
    return {"applied": False, "strategy": "already_done",
            "files_modified": [], "description": "既に強化済み"}


def _fix_missing_import(result: EvalResult) -> dict:
    mod_match = re.search(r"No module named '([^']+)'", result.last_log)
    if not mod_match:
        return {"applied": False, "strategy": "no_module_found",
                "files_modified": [], "description": "モジュール名不明"}
    module = mod_match.group(1).split(".")[0]
    pip_map = {"bs4": "beautifulsoup4", "cv2": "opencv-python",
               "PIL": "Pillow", "sklearn": "scikit-learn"}
    pip_name = pip_map.get(module, module)
    print(f"    📦 インストール: {pip_name}")
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", pip_name],
        capture_output=True, text=True
    )
    applied = proc.returncode == 0
    description = f"pip install {pip_name}: {'成功' if applied else '失敗'}"
    if applied:
        # --- GIT EVOLUTION START ---
        from evolution_tracker import record_evolution
        record_evolution(
            error_type="import_error",
            file_repaired="(venv)",
            strategy=f"rule_installed_{pip_name}",
            description=description,
            files_to_commit=[],
        )
        # --- GIT EVOLUTION END ---
    return {"applied": applied,
            "strategy": f"installed_{pip_name}", "files_modified": [],
            "description": description}


def _fix_no_run(result: EvalResult) -> dict:
    main_py = AGENT_ROOT / "main.py"
    content = main_py.read_text(encoding="utf-8")
    if "create_count >= 1" in content:
        content = content.replace("create_count >= 1", "create_count >= 0", 1)
        main_py.write_text(content, encoding="utf-8")
        return {"applied": True, "strategy": "run_injection_aggressive",
                "files_modified": ["main.py"], "description": "run注入を初回から実行"}
    return {"applied": False, "strategy": "no_change",
            "files_modified": [], "description": "run注入は設定済み"}


def _fix_timeout(result: EvalResult) -> dict:
    tester_py = AGENT_ROOT / "tester.py"
    content = tester_py.read_text(encoding="utf-8")
    modified = False
    for old, new in [("TIMEOUT = 60", "TIMEOUT = 120"),
                     ("TIMEOUT = 120", "TIMEOUT = 180"),
                     ("TIMEOUT = 180", "TIMEOUT = 300")]:
        if old in content:
            content = content.replace(old, new, 1)
            modified = True
            break
    if modified:
        tester_py.write_text(content, encoding="utf-8")
    return {"applied": modified, "strategy": "timeout_extended",
            "files_modified": ["tester.py"] if modified else [],
            "description": "タイムアウト値を延長"}


# --- AUTO REPAIR START ---
def _fix_syntax_with_llm(result: EvalResult) -> dict:
    return _auto_repair(result)


def _fix_wrong_output_with_llm(result: EvalResult) -> dict:
    return _auto_repair(result)


def _fix_unknown_with_llm(result: EvalResult) -> dict:
    return _auto_repair(result)


def _auto_repair(result: EvalResult) -> dict:
    """
    code_repair.py を使って失敗ファイルを自動修復する。
    対象ファイルをエラーログから特定する。
    """
    from code_repair import repair_file

    # エラーログからファイル名を特定
    file_match = re.search(
        r'(?:File ["\']|python\s+|running\s+)([\w/]+\.py)',
        result.last_log
    )
    if not file_match:
        return _llm_based_fix(result, "unknown")

    target_file = file_match.group(1)
    print(f"    🎯 修復対象: {target_file}")

    # --- GIT EVOLUTION START ---
    repair_result = repair_file(
        file_path=target_file,
        error_log=result.last_log,
        task_description=result.reason,
        error_type=result.failure_type.value,  # 追加
    )
    # --- GIT EVOLUTION END ---

    return {
        "applied": repair_result.success,
        "strategy": f"auto_repair_{repair_result.strategy}",
        "files_modified": [repair_result.file_repaired] if repair_result.success else [],
        "description": repair_result.description,
    }
# --- AUTO REPAIR END ---


def _llm_based_fix(result: EvalResult, fix_type: str) -> dict:
    from llm import ask_plain
    prompt = f"""
AIエージェントのテストが失敗しました。修正方針を1〜3行で提案してください。

失敗種別: {fix_type}
失敗理由: {result.reason}
ログ:
{result.last_log}

どのファイルの何を変えるか、具体的に答えてください。
"""
    suggestion = ask_plain(prompt)
    print(f"    🤖 LLM提案:\n{suggestion[:300]}")
    log_path = AGENT_ROOT / "self_improve_log.md"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — {fix_type}\n")
        f.write(f"**理由:** {result.reason}\n**提案:**\n{suggestion}\n")
    return {"applied": False, "strategy": f"llm_suggestion_{fix_type}",
            "files_modified": [],
            "description": "LLM提案をself_improve_log.mdに記録"}
# --- SELF IMPROVE END ---
