"""
Signature類似度モジュール。
外部ライブラリ不要のLevenshtein距離で近似signatureを検索する。
"""
import json
import math
from pathlib import Path

AGENT_ROOT = Path(__file__).parent
PATTERN_DB = AGENT_ROOT / "memory" / "repair_patterns.json"

SIMILARITY_THRESHOLD = 4  # この距離以下を「類似」とみなす


def levenshtein(s1: str, s2: str) -> int:
    """
    2つの文字列間のLevenshtein距離を計算する。
    標準ライブラリのみ使用。
    """
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i]
        for j, c2 in enumerate(s2, 1):
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (c1 != c2),
            ))
        prev = curr
    return prev[-1]


def similarity_weight(distance: int, threshold: int = SIMILARITY_THRESHOLD) -> float:
    """
    距離からsimilarity weightを計算する。
    distance=0 → 1.0
    distance=threshold → 0.0に近い値
    """
    if distance == 0:
        return 1.0
    return max(0.0, 1.0 - distance / (threshold + 1))


def find_similar_signatures(
    target: str,
    threshold: int = SIMILARITY_THRESHOLD,
    top_n: int = 3,
) -> list:
    """
    repair_patterns.json から target に近い signature を返す。
    同じ error_type のものだけを比較対象にする。

    Returns: [(distance, signature, patterns)] の距離昇順リスト
    """
    if not PATTERN_DB.exists():
        return []
    with open(PATTERN_DB, encoding="utf-8") as f:
        data = json.load(f)
    signatures_db = data.get("signatures", {})
    if not signatures_db:
        return []

    target_type    = target.split("::")[0] if "::" in target else target
    target_feature = target.split("::")[-1] if "::" in target else ""

    candidates = []
    for sig, patterns in signatures_db.items():
        if sig == target or not patterns:
            continue
        sig_type    = sig.split("::")[0] if "::" in sig else sig
        sig_feature = sig.split("::")[-1] if "::" in sig else ""
        if sig_type != target_type:
            continue
        dist = levenshtein(target_feature, sig_feature)
        if dist <= threshold:
            candidates.append((dist, sig, patterns))

    candidates.sort(key=lambda x: x[0])
    return candidates[:top_n]


def get_similar_patterns(target_signature: str, top_n: int = 3) -> list:
    """
    類似signatureのパターンをフラットなリストで返す。
    decay_score × similarity_weight の複合スコアで並び替える。
    """
    similar = find_similar_signatures(target_signature, top_n=top_n)
    if not similar:
        return []

    results = []
    for distance, sig, patterns in similar:
        weight = similarity_weight(distance)
        for p in patterns:
            base_count = p.get("count", 1)
            decay      = _decay_score(p)
            combined   = decay * weight   # 時間減衰 × 距離ペナルティ
            results.append({
                "strategy":      p["strategy"],
                "description":   p.get("description", ""),
                "count":         base_count,
                "last_success":  p.get("last_success", ""),
                "distance":      distance,
                "source_sig":    sig,
                "combined_score": combined,
            })

    results.sort(key=lambda x: -x["combined_score"])
    return results[:top_n]


def _decay_score(pattern: dict) -> float:
    """score = count × exp(-age_days / 30)"""
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
