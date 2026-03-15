"""
evaluator.py — テスト結果評価モジュール

LLMを使った意味的評価とルールベース評価の2段構え。
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# allow imports from agent root when run directly
sys.path.insert(0, str(Path(__file__).parent))


@dataclass
class EvalResult:
    success: bool
    reason: str
    score: float   # 0.0〜1.0


# -------------------------
# INTERNAL HELPERS
# -------------------------

_FAIL_SIGNALS = [
    "Traceback (most recent call last)",
    "exit code 1",
    "exit code 2",
    "SyntaxError",
    "ImportError",
    "ModuleNotFoundError",
    "Error: command",
    "tool error",
]


def _has_fail_signal(text: str) -> bool:
    return any(sig in text for sig in _FAIL_SIGNALS)


def _check_in_result_lines(output: str, expect: str) -> bool:
    """
    main.py は 'print("結果:", str(result)[:200])' で結果を出力する。
    その行か、[exit code 0] 直後の最大20行ブロックで期待値を探す。
    """
    lines = output.splitlines()

    # 1. '結果:' で始まる行
    for ln in lines:
        if ln.startswith("結果:") and expect in ln:
            return True

    # 2. '[exit code 0]' 直後のブロック
    for i, ln in enumerate(lines):
        if "[exit code 0]" in ln:
            block = "\n".join(lines[i: i + 20])
            if expect in block:
                return True

    return False


def _llm_evaluate(task_def: dict, agent_output: str) -> EvalResult:
    """
    LLMによる意味的評価（ルールベースで判定できない場合のみ呼ぶ）。
    """
    try:
        from llm import ask_planner
        snippet = agent_output[-3000:] if len(agent_output) > 3000 else agent_output
        prompt = (
            "あなたはソフトウェアエンジニアリングエージェントのテスト評価者です。\n\n"
            f"タスク: {task_def.get('task', '')}\n"
            f"期待する出力キーワード: {task_def.get('expect_contains', '')}\n\n"
            f"エージェントの実行ログ（末尾）:\n{snippet}\n\n"
            "このエージェントはタスクを成功させましたか？\n"
            "回答は必ず以下の形式で:\n"
            "SUCCESS: はい または いいえ\n"
            "REASON: 判断理由を一文で\n"
        )
        resp = ask_planner(prompt)
        success = "はい" in resp and "SUCCESS: はい" in resp
        # reason 抽出
        reason = ""
        for ln in resp.splitlines():
            if ln.startswith("REASON:"):
                reason = ln[len("REASON:"):].strip()
                break
        return EvalResult(
            success=success,
            reason=f"LLM判定: {reason or resp[:100]}",
            score=1.0 if success else 0.2,
        )
    except Exception as e:
        return EvalResult(success=False, reason=f"LLM評価エラー: {e}", score=0.0)


# -------------------------
# PUBLIC API
# -------------------------

def evaluate(task_def: dict, agent_output: str) -> EvalResult:
    """
    評価ロジック（優先順位順）:

    1. expect_contains が結果行 / exit code 0 ブロックに含まれるか（ルールベース・高速）
    2. "exit code 0" のみ期待する場合はシンプルチェック
    3. エラーシグナルが含まれているか
    4. LLMによる意味的評価（上記で判定できない場合のみ）
    """
    expect = task_def.get("expect_contains", "")

    # --- ルール1: expect_contains が実行結果行に含まれるか ---
    if expect and expect != "exit code 0":
        if _check_in_result_lines(agent_output, expect):
            return EvalResult(
                success=True,
                reason=f"'{expect}' が実行結果行に含まれる",
                score=1.0,
            )

    # --- ルール2: "exit code 0" 単体の期待値 ---
    if expect == "exit code 0" or not expect:
        if "[exit code 0]" in agent_output and not _has_fail_signal(agent_output):
            return EvalResult(
                success=True,
                reason="exit code 0 を確認、エラーなし",
                score=1.0,
            )
        if "[exit code 0]" in agent_output:
            # exit code 0 はあるがエラーシグナルも存在
            return EvalResult(
                success=True,
                reason="exit code 0 を確認（警告あり）",
                score=0.8,
            )

    # --- ルール3: 明確なエラーシグナル ---
    if _has_fail_signal(agent_output) and (not expect or expect not in agent_output):
        # フォールバックとしてテキスト全体でも探す（ログ汚染の可能性あり）
        if expect and expect in agent_output:
            return EvalResult(
                success=True,
                reason=f"'{expect}' をログ全体で検出（ノイズあり）",
                score=0.7,
            )
        return EvalResult(
            success=False,
            reason=f"エラーシグナル検出、期待値 '{expect}' 未確認",
            score=0.0,
        )

    # --- ルール4: done 宣言があり期待値もある程度ログにあれば成功とみなす ---
    if re.search(r"^完了$", agent_output, re.MULTILINE):
        if expect and expect in agent_output:
            return EvalResult(
                success=True,
                reason=f"done宣言あり、'{expect}' をログ内で検出",
                score=0.9,
            )

    # --- ルール5: LLM意味的評価（最終手段） ---
    return _llm_evaluate(task_def, agent_output)
