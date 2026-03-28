"""
記事生成中の動的情報収集・検証システム。

記事内に「〇〇ぶり」「過去〇ヶ月の高水準」等の
時間表現が検出された場合、Yahoo Finance APIで
過去データを取得して数値の正確性を検証する。
"""

import re
import requests
from datetime import datetime, timedelta
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}


# -------------------------------------------------------
# 時間表現の抽出
# -------------------------------------------------------

def extract_time_expressions(content: str) -> list:
    """
    記事から時間表現を抽出する。
    数値を伴わない曖昧表現（「数週間ぶり」等）は抽出しない。

    Returns:
        [{"expression": "2週間ぶり", "context": "前後の文章", "days": 14}, ...]
    """
    PATTERNS = [
        (r'(\d+)週間ぶり',  lambda m: int(m.group(1)) * 7),
        (r'(\d+)ヶ月ぶり',  lambda m: int(m.group(1)) * 30),
        (r'(\d+)カ月ぶり',  lambda m: int(m.group(1)) * 30),
        (r'(\d+)か月ぶり',  lambda m: int(m.group(1)) * 30),
        (r'(\d+)年ぶり',    lambda m: int(m.group(1)) * 365),
        (r'(\d+)日ぶり',    lambda m: int(m.group(1))),
        (r'過去(\d+)週間',  lambda m: int(m.group(1)) * 7),
        (r'過去(\d+)ヶ月',  lambda m: int(m.group(1)) * 30),
        (r'過去(\d+)カ月',  lambda m: int(m.group(1)) * 30),
        (r'過去(\d+)年',    lambda m: int(m.group(1)) * 365),
    ]

    results = []
    for pattern, calc_days in PATTERNS:
        for m in re.finditer(pattern, content):
            # 前後50文字のコンテキストを取得
            start   = max(0, m.start() - 50)
            end     = min(len(content), m.end() + 50)
            context = content[start:end]
            days    = calc_days(m)

            results.append({
                "expression": m.group(0),
                "context":    context,
                "days":       days,
                "position":   m.start(),
            })

    return results


# -------------------------------------------------------
# Yahoo Finance APIで過去データを取得
# -------------------------------------------------------

def fetch_nikkei_history(days: int) -> list:
    """
    日経平均の過去データを取得する。

    Returns:
        [{"date": "2026-01-01", "close": 52000.0}, ...]
    """
    try:
        end_ts   = int(datetime.now().timestamp())
        start_ts = int((datetime.now() - timedelta(days=days + 10)).timestamp())

        url  = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/%5EN225"
            f"?period1={start_ts}&period2={end_ts}&interval=1d"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        result  = data["chart"]["result"][0]
        ts_list = result["timestamp"]
        closes  = result["indicators"]["quote"][0]["close"]

        history = []
        for ts, close in zip(ts_list, closes):
            if close is None:
                continue
            dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            history.append({"date": dt, "close": close})

        return history

    except Exception as e:
        print(f"  ⚠️ 日経平均過去データ取得失敗: {e}")
        return []


# -------------------------------------------------------
# 時間表現の検証
# -------------------------------------------------------

def verify_time_expression(
    expression: str,
    context: str,
    days: int,
    current_nikkei: float,
) -> dict:
    """
    時間表現をYahoo Finance APIで検証する。

    Returns:
        {
            "valid": bool,
            "expression": str,
            "suggestion": str,  # 修正案
            "evidence": str,    # 根拠
        }
    """
    history = fetch_nikkei_history(days)
    if not history:
        return {
            "valid":      False,
            "expression": expression,
            "suggestion": "（データ取得失敗のため表現を削除してください）",
            "evidence":   "過去データ取得失敗",
        }

    # 指定期間前の終値を取得
    target_idx = 0  # 最も古いデータ
    past_close = history[target_idx]["close"]
    past_date  = history[target_idx]["date"]

    # 現在値との比較
    # 「〇〇ぶりの高値」の場合: 期間内の最高値が現在値に近いか確認
    period_closes = [h["close"] for h in history]
    period_max    = max(period_closes)
    period_min    = min(period_closes)

    # 「〇〇ぶりの下落幅」を検証
    if "下落" in context or "安値" in context:
        is_valid = current_nikkei <= period_min * 1.02  # 2%の誤差許容
        suggestion = (
            f"（検証済み: {past_date}以来の安値水準）"
            if is_valid
            else f"（要確認: {past_date}時点={past_close:.0f}円、現在={current_nikkei:.0f}円）"
        )
    elif "上昇" in context or "高値" in context or "高水準" in context:
        is_valid = current_nikkei >= period_max * 0.98  # 2%の誤差許容
        suggestion = (
            f"（検証済み: {past_date}以来の高値水準）"
            if is_valid
            else f"（要確認: {past_date}時点={past_close:.0f}円、現在={current_nikkei:.0f}円）"
        )
    else:
        # 文脈不明の場合は許容
        is_valid   = True
        suggestion = f"（参考: {past_date}時点={past_close:.0f}円）"

    return {
        "valid":      is_valid,
        "expression": expression,
        "suggestion": suggestion,
        "evidence":   f"{past_date}時点: {past_close:.0f}円 / 期間最高: {period_max:.0f}円 / 期間最安: {period_min:.0f}円",
    }


# -------------------------------------------------------
# メイン検証関数
# -------------------------------------------------------

def verify_article_time_expressions(
    content: str,
    finance_data: dict,
) -> dict:
    """
    記事内の時間表現を検証する。

    Returns:
        {
            "has_issues": bool,
            "issues": [str],           # 再生成が必要な問題
            "warnings": [str],         # 警告のみ
            "verified": [str],         # 検証済み表現
            "correction_prompt": str,  # 再生成用の修正指示
        }
    """
    expressions = extract_time_expressions(content)

    if not expressions:
        return {
            "has_issues":        False,
            "issues":            [],
            "warnings":          [],
            "verified":          [],
            "correction_prompt": "",
        }

    print(f"  🔍 時間表現を検証中: {len(expressions)}件")

    # 現在の日経平均を取得
    market   = finance_data.get("market_summary", {})
    nikkei   = market.get("nikkei_price", "")
    try:
        current_nikkei = float(nikkei.replace(",", ""))
    except Exception:
        current_nikkei = 0.0

    issues   = []
    warnings = []
    verified = []

    for expr_info in expressions:
        expression = expr_info["expression"]
        context    = expr_info["context"]
        days       = expr_info["days"]

        print(f"  📅 検証: 「{expression}」（{days}日分のデータを取得）")
        result = verify_time_expression(
            expression, context, days, current_nikkei
        )

        if result["valid"]:
            verified.append(f"「{expression}」: {result['evidence']}")
            print(f"  ✅ 検証OK: {result['evidence']}")
        else:
            issues.append(
                f"「{expression}」の数値が不正確: {result['evidence']}"
            )
            print(f"  ❌ 検証NG: {result['evidence']}")

    # 修正指示を生成
    correction_prompt = ""
    if issues:
        issues_text = "\n".join(f"- {i}" for i in issues)
        correction_prompt = (
            f"\n\n【時間表現の検証結果 - 修正が必要】\n"
            f"{issues_text}\n\n"
            "以下のルールで修正してください:\n"
            "- 数値が不正確な時間表現は「数週間ぶり」「近年」等の曖昧表現に変更\n"
            "- または該当の表現を削除して事実のみを記載\n"
        )

    return {
        "has_issues":        bool(issues),
        "issues":            issues,
        "warnings":          warnings,
        "verified":          verified,
        "correction_prompt": correction_prompt,
    }
