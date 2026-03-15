"""
過去の成功パターンを使った修復モジュール。
repair_patterns.json から同じエラータイプの成功戦略を取得し、
優先的に適用する。

修復優先順位:
  1. past_patterns（成功回数が多い順）
  2. rule_based（self_improver.py の既存ロジック）
  3. LLM auto repair（code_repair.py）
"""
import json
import math
from pathlib import Path
from dataclasses import dataclass
from self_evaluator import EvalResult, FailureType

AGENT_ROOT = Path(__file__).parent
PATTERN_DB = AGENT_ROOT / "memory" / "repair_patterns.json"


@dataclass
class PatternMatch:
    error_type:  str
    strategy:    str
    description: str
    count:       int
    confidence:  float


def get_best_patterns(error_type: str, top_n: int = 3) -> list:
    """
    指定エラータイプの成功パターンを成功回数順で返す。
    パターンがない場合は空リストを返す。
    """
    if not PATTERN_DB.exists():
        return []
    with open(PATTERN_DB, encoding="utf-8") as f:
        data = json.load(f)
    patterns = data.get("patterns", {}).get(error_type, [])
    if not patterns:
        return []
    sorted_patterns = sorted(patterns, key=lambda p: p.get("count", 0), reverse=True)
    total_count = sum(p.get("count", 1) for p in sorted_patterns)
    result = []
    for p in sorted_patterns[:top_n]:
        count = p.get("count", 1)
        result.append(PatternMatch(
            error_type=error_type,
            strategy=p["strategy"],
            description=p.get("description", ""),
            count=count,
            confidence=count / total_count if total_count > 0 else 0.0,
        ))
    return result


def apply_pattern(pattern: PatternMatch, eval_result: EvalResult) -> dict:
    """パターンに対応する修復を実行する"""
    strategy = pattern.strategy
    print(f"    🧠 パターン適用: {strategy} "
          f"(成功{pattern.count}回 / 信頼度{pattern.confidence:.0%})")

    rule_strategies = {
        "loop_threshold_relaxed":      _apply_loop_fix,
        "rule_loop_threshold":         _apply_loop_fix,
        "done_prompt_strengthened":    _apply_done_fix,
        "invalid_tool_prompt_updated": _apply_tool_fix,
        "run_injection_aggressive":    _apply_run_fix,
        "timeout_extended":            _apply_timeout_fix,
    }
    llm_strategies = {
        "auto_repair_patch":   _apply_llm_repair,
        "auto_repair_rewrite": _apply_llm_repair,
    }

    # rule_installed_<pkg> 系
    if strategy.startswith("rule_installed_") or strategy.startswith("installed_"):
        pkg = strategy.split("installed_", 1)[1] if "installed_" in strategy else ""
        return _apply_pip_install(pkg, eval_result)

    if strategy in rule_strategies:
        return rule_strategies[strategy](eval_result)
    elif strategy in llm_strategies:
        return llm_strategies[strategy](eval_result)
    else:
        return {
            "applied": False,
            "strategy": f"unknown_pattern_{strategy}",
            "files_modified": [],
            "description": f"未知の戦略: {strategy}",
        }


def apply_best_pattern(eval_result: EvalResult) -> dict:
    """
    signature → error_type の順でパターンを検索して適用する。
    パターンがない場合は applied=False を返す。
    """
    # --- SIGNATURE UPDATE START ---
    sig = getattr(eval_result, "signature", "") or eval_result.failure_type.value
    patterns = get_best_patterns_by_signature(sig, top_n=1)
    # --- SIGNATURE UPDATE END ---
    if not patterns:
        return {
            "applied": False,
            "strategy": "no_pattern",
            "files_modified": [],
            "description": "過去の成功パターンなし",
        }
    return apply_pattern(patterns[0], eval_result)


# --- SIGNATURE UPDATE START ---
def decay_score(pattern: dict) -> float:
    """
    Confidence Decay スコア。
    score = count × exp(-age_days / 30)
    経過日数: 1日→97%  30日→37%  60日→13%  90日→5%
    """
    count = pattern.get("count", 1)
    last_success = pattern.get("last_success", "")
    if not last_success:
        return float(count)
    try:
        from datetime import datetime, timezone
        last = datetime.fromisoformat(last_success)
        now  = datetime.now(timezone.utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_days = (now - last).total_seconds() / 86400
        return count * math.exp(-age_days / 30.0)
    except Exception:
        return float(count)


# --- SIMILARITY START ---
def get_best_patterns_by_signature(signature: str, top_n: int = 3) -> list:
    """
    検索優先順位:
    1. 完全一致（signatures キー）
    2. 近似一致（Levenshtein距離 ≤ 閾値、combined_scoreでスコアリング）
    3. error_type フォールバック（patterns キー）
    """
    if not PATTERN_DB.exists():
        return []
    with open(PATTERN_DB, encoding="utf-8") as f:
        data = json.load(f)

    # 優先1: 完全一致
    patterns = data.get("signatures", {}).get(signature, [])
    source = "exact"

    # 優先2: 近似一致
    if not patterns:
        from signature_similarity import get_similar_patterns
        similar = get_similar_patterns(signature, top_n=top_n)
        if similar:
            patterns = similar
            source = "similar"
            print(f"    🔍 近似パターン使用: "
                  f"'{similar[0].get('source_sig', '?')}' "
                  f"(距離{similar[0].get('distance', '?')})")

    # 優先3: error_type フォールバック
    if not patterns and "::" in signature:
        error_type = signature.split("::")[0]
        patterns = data.get("patterns", {}).get(error_type, [])
        source = "fallback"

    if not patterns:
        patterns = data.get("patterns", {}).get(signature, [])

    if not patterns:
        return []

    # similar は combined_score、それ以外は decay_score で統一
    if source == "similar":
        scored = sorted(patterns, key=lambda p: -p.get("combined_score", 0.0))
        total = sum(p.get("combined_score", 0.0) for p in scored) or 1.0
        return [
            PatternMatch(
                error_type=signature,
                strategy=p["strategy"],
                description=p.get("description", ""),
                count=p.get("count", 1),
                confidence=p.get("combined_score", 0.0) / total,
            )
            for p in scored[:top_n]
        ]
    else:
        scored = sorted(
            [(decay_score(p), p) for p in patterns],
            key=lambda x: -x[0],
        )
        total = sum(s for s, _ in scored) or 1.0
        return [
            PatternMatch(
                error_type=signature,
                strategy=p["strategy"],
                description=p.get("description", ""),
                count=p.get("count", 1),
                confidence=s / total,
            )
            for s, p in scored[:top_n]
        ]
# --- SIMILARITY END ---
# --- SIGNATURE UPDATE END ---


def show_pattern_stats() -> str:
    """パターンDBの統計を返す"""
    if not PATTERN_DB.exists():
        return "## Pattern DB Stats\n\nパターンDB未作成"
    with open(PATTERN_DB, encoding="utf-8") as f:
        data = json.load(f)
    patterns = data.get("patterns", {})
    records  = data.get("records",  [])
    lines = [
        "## Pattern DB Stats",
        f"- 総修復記録: {len(records)}件",
        f"- 学習済みエラータイプ: {len(patterns)}種",
        "",
        "### 学習パターン一覧",
    ]
    for error_type, pats in sorted(patterns.items()):
        if not pats:
            continue
        lines.append(f"**{error_type}**:")
        for p in sorted(pats, key=lambda x: -x.get("count", 0)):
            lines.append(f"  - {p['strategy']} (成功{p.get('count', 0)}回)")
    if not patterns:
        lines.append("（まだ学習データなし）")
    return "\n".join(lines)


# =====================================================
# 内部: 各戦略の委譲
# =====================================================

def _apply_loop_fix(r: EvalResult) -> dict:
    from self_improver import _fix_loop
    return _fix_loop(r)


def _apply_done_fix(r: EvalResult) -> dict:
    from self_improver import _fix_done_declaration
    return _fix_done_declaration(r)


def _apply_tool_fix(r: EvalResult) -> dict:
    from self_improver import _fix_invalid_tool
    return _fix_invalid_tool(r)


def _apply_run_fix(r: EvalResult) -> dict:
    from self_improver import _fix_no_run
    return _fix_no_run(r)


def _apply_timeout_fix(r: EvalResult) -> dict:
    from self_improver import _fix_timeout
    return _fix_timeout(r)


def _apply_pip_install(pkg: str, r: EvalResult) -> dict:
    if not pkg:
        return {"applied": False, "strategy": "pip_no_pkg",
                "files_modified": [], "description": "パッケージ名不明"}
    import sys, subprocess
    print(f"    📦 学習パターン: pip install {pkg}")
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg],
        capture_output=True, text=True
    )
    applied = proc.returncode == 0
    return {
        "applied": applied,
        "strategy": f"installed_{pkg}",
        "files_modified": [],
        "description": f"pip install {pkg}: {'成功' if applied else '失敗'}",
    }


def _apply_llm_repair(r: EvalResult) -> dict:
    from self_improver import _auto_repair
    return _auto_repair(r)
