"""
self_evaluator.py — エージェントの実行結果を評価し、失敗原因を分類するモジュール。
ルールベース評価（高速）→ LLM評価（複雑なケース）の2段構え。
"""

# --- SELF IMPROVE START ---
from dataclasses import dataclass, field
from enum import Enum
import re

# --- SIGNATURE UPDATE START ---
import hashlib
import math
# --- SIGNATURE UPDATE END ---


class FailureType(Enum):
    SUCCESS        = "success"
    LOOP_DETECTED  = "loop_detected"
    MAX_STEPS      = "max_steps"
    INVALID_TOOL   = "invalid_tool"
    IMPORT_ERROR   = "import_error"
    SYNTAX_ERROR   = "syntax_error"
    RUNTIME_ERROR  = "runtime_error"
    NO_RUN         = "no_run"
    WRONG_OUTPUT   = "wrong_output"
    TIMEOUT        = "timeout"
    UNKNOWN        = "unknown"


# --- SIGNATURE UPDATE START ---
@dataclass
class EvalResult:
    success:      bool
    failure_type: FailureType
    reason:       str
    last_log:     str = ""
    suggested_fix: str = ""
    signature:    str = ""   # 追加: error_type::feature


def _make_signature(failure_type: FailureType, log: str) -> str:
    """
    failure_type + エラーメッセージの特徴からシグネチャを生成。
    例: "syntax_error::unexpected_indent"
        "import_error::pandas"
        "loop_detected::fetch"
    """
    feature = _extract_feature(failure_type.value, log)
    if feature:
        return f"{failure_type.value}::{feature}"
    return failure_type.value


def _extract_feature(error_type: str, log: str) -> str:
    """エラータイプ別に特徴文字列を抽出する"""
    extractors = {
        # SyntaxError: 改行まで全部取得して先頭20文字を snake_case 化
        "syntax_error": lambda l: (
            m.group(1).strip()[:20].replace(" ", "_").lower()
            if (m := re.search(r"SyntaxError:\s*([^\n]+)", l)) else ""
        ),
        # ImportError: モジュール名（ドット区切りの末尾）
        "import_error": lambda l: (
            m.group(1).split(".")[-1]
            if (m := re.search(r"No module named '([^']+)'", l)) else ""
        ),
        # LoopDetected: sigs リストの最初のファイル名（拡張子なし）
        "loop_detected": lambda l: (
            m.group(1).split("::")[-1].split("/")[-1].replace(".py", "")[:15]
            if (m := re.search(r"sigs=\['(\S+)'", l)) else ""
        ),
        # RuntimeError: エラークラス名を小文字化
        "runtime_error": lambda l: (
            m.group(1).lower()[:20].replace(" ", "_")
            if (m := re.search(r"(\w+Error):", l)) else ""
        ),
    }
    extractor = extractors.get(error_type)
    if extractor:
        try:
            return extractor(log) or ""
        except Exception:
            return ""
    return ""
# --- SIGNATURE UPDATE END ---


def evaluate_run(task_def: dict, agent_log: str, agent_output: str) -> EvalResult:
    log = agent_log + "\n" + agent_output

    if "timeout" in log.lower() or "⏱" in log:
        return EvalResult(False, FailureType.TIMEOUT,
            "実行タイムアウト", _tail(log),
            "タイムアウト値を延長するか、タスクを分割する",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.TIMEOUT, log),
            # --- SIGNATURE UPDATE END ---
        )

    if "LOOP DETECTED" in log:
        sigs = re.findall(r"sigs=\[(.+?)\]", log)
        return EvalResult(False, FailureType.LOOP_DETECTED,
            f"ループ検出: {sigs[-1] if sigs else '不明'}", _tail(log),
            "同じアクションを繰り返している。runを挟む必要がある",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.LOOP_DETECTED, log),
            # --- SIGNATURE UPDATE END ---
        )

    if "無効なツール名" in log or "Unknown tool" in log or "は無効なツール名" in log:
        tool = re.search(r"'([^']+)' は無効", log)
        return EvalResult(False, FailureType.INVALID_TOOL,
            f"無効ツール: {tool.group(1) if tool else '不明'}", _tail(log),
            "SYSTEM_PROMPTのVALID_TOOLSルールを強化する",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.INVALID_TOOL, log),
            # --- SIGNATURE UPDATE END ---
        )

    if "ModuleNotFoundError" in log or "ImportError" in log:
        mod = re.search(r"No module named '([^']+)'", log)
        name = mod.group(1) if mod else "不明"
        return EvalResult(False, FailureType.IMPORT_ERROR,
            f"モジュール未インストール: {name}", _tail(log),
            f"pip install {name}",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.IMPORT_ERROR, log),
            # --- SIGNATURE UPDATE END ---
        )

    if "SyntaxError" in log:
        return EvalResult(False, FailureType.SYNTAX_ERROR,
            "Pythonの構文エラー", _tail(log),
            "生成したコードの構文を修正する",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.SYNTAX_ERROR, log),
            # --- SIGNATURE UPDATE END ---
        )

    if "STEP 30" in log and "done" not in log.lower().split("step 30")[-1]:
        return EvalResult(False, FailureType.MAX_STEPS,
            "MAX_STEPS(30)到達・done未宣言", _tail(log),
            "done宣言条件をSYSTEM_PROMPTで強化する",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.MAX_STEPS, log),
            # --- SIGNATURE UPDATE END ---
        )

    if "CREATED:" in log and "exit code" not in log:
        return EvalResult(False, FailureType.NO_RUN,
            "ファイルを作成したが実行していない", _tail(log),
            "run注入ロジックを確認する",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.NO_RUN, log),
            # --- SIGNATURE UPDATE END ---
        )

    expect = task_def.get("expect_contains", "")
    if expect and expect not in log:
        return EvalResult(False, FailureType.WRONG_OUTPUT,
            f"期待値 '{expect}' が出力に含まれない", _tail(log),
            "タスク文を明確化する",
            # --- SIGNATURE UPDATE START ---
            signature=_make_signature(FailureType.WRONG_OUTPUT, log),
            # --- SIGNATURE UPDATE END ---
        )

    if "exit code 0" in log or (expect and expect in log):
        return EvalResult(True, FailureType.SUCCESS, "成功")  # SUCCESS は signature 不要

    return _llm_evaluate(task_def, log)


def _llm_evaluate(task_def: dict, log: str) -> EvalResult:
    from llm import ask_plain
    prompt = f"""
以下はAIエージェントのタスク実行ログです。
成功か失敗かを判定し、失敗の場合は原因を教えてください。

タスク: {task_def.get('task', '')}
期待値: {task_def.get('expect_contains', '')}

ログ（末尾500文字）:
{log[-500:]}

以下の形式でのみ回答:
RESULT: SUCCESS または FAIL
REASON: （1行で）
"""
    response = ask_plain(prompt)
    success = "SUCCESS" in response.upper()
    m = re.search(r"REASON:\s*(.+)", response)
    reason = m.group(1).strip() if m else response[:100]
    ft = FailureType.SUCCESS if success else FailureType.UNKNOWN
    return EvalResult(
        success=success,
        failure_type=ft,
        reason=reason,
        last_log=log[-300:],
        # --- SIGNATURE UPDATE START ---
        signature=_make_signature(ft, log) if not success else "",
        # --- SIGNATURE UPDATE END ---
    )


def _tail(text: str, chars: int = 400) -> str:
    return text[-chars:] if len(text) > chars else text
# --- SELF IMPROVE END ---
