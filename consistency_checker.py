"""
Zenn版・はてな版の整合性チェックシステム。

チェック項目:
1. 数値の一致（日経平均・VIX・為替・原油・S&P500）
2. 銘柄・変動率の一致
3. コンテキストの正値との照合
"""

import re


# -------------------------------------------------------
# 数値抽出
# -------------------------------------------------------

def extract_numbers_from_article(content: str) -> dict:
    """
    記事から主要数値を抽出する。
    """
    numbers = {}

    # 日経平均（例: 35,123.45円）
    m = re.search(r'(\d{2},\d{3}\.\d+)円', content)
    if m:
        numbers["nikkei"] = m.group(1).replace(",", "")

    # USD/JPY（例: USD/JPY 149.50円 or 149.50円/ドル）
    m = re.search(r'USD/JPY.*?(\d{3}\.\d+)', content)
    if not m:
        m = re.search(r'(\d{3}\.\d+)円.*?(?:ドル|USD)', content)
    if m:
        numbers["usd_jpy"] = m.group(1)

    # VIX（例: VIX 18.50）
    m = re.search(r'VIX.*?(\d+\.\d+)', content)
    if m:
        numbers["vix"] = m.group(1)

    # S&P500（例: S&P500 5,123.45）
    m = re.search(r'S&P500.*?(\d[\d,]+\.\d+)', content)
    if m:
        numbers["sp500"] = m.group(1).replace(",", "")

    # WTI原油（例: WTI $75.50）
    m = re.search(r'WTI.*?\$(\d+\.\d+)', content)
    if m:
        numbers["wti"] = m.group(1)

    # 前日比変動率（例: 前日比 +1.23%）
    m = re.search(r'前日比.*?([+-]?\d+\.\d+)%', content)
    if m:
        numbers["nikkei_change_pct"] = m.group(1)

    return numbers


# -------------------------------------------------------
# 整合性チェック
# -------------------------------------------------------

def check_consistency(zenn_content: str, hatena_content: str, finance_data: dict) -> dict:
    """
    Zenn版・はてな版の整合性を確認する。

    Returns:
        {
            "consistent": bool,
            "issues": [str],
            "corrections": [str],  # どちらを修正すべきか
        }
    """
    issues      = []
    corrections = []

    zenn_nums   = extract_numbers_from_article(zenn_content)
    hatena_nums = extract_numbers_from_article(hatena_content)

    # コンテキストの正値を取得
    market = finance_data.get("market_summary", {})
    macro  = finance_data.get("macro", {})
    us     = macro.get("us_stocks", {})
    forex  = macro.get("forex", {})
    comm   = macro.get("commodities", {})

    nikkei_raw = market.get("nikkei_price", "")
    true_values = {
        "nikkei":  nikkei_raw.replace(",", "") if nikkei_raw else "",
        "usd_jpy": str(forex.get("USD/JPY", {}).get("price", "")),
        "vix":     str(us.get("VIX", {}).get("price", "")),
        "sp500":   str(us.get("S&P500", {}).get("price", "")),
        "wti":     str(comm.get("WTI原油", {}).get("price", "")),
    }

    # 数値の突合（Zenn vs はてな vs 正値）
    for key in ["nikkei", "usd_jpy", "vix"]:
        z_val = zenn_nums.get(key, "")
        h_val = hatena_nums.get(key, "")
        t_val = true_values.get(key, "")

        if z_val and h_val and z_val != h_val:
            if t_val:
                if z_val == t_val:
                    correct = "zenn"
                elif h_val == t_val:
                    correct = "hatena"
                else:
                    correct = "both_wrong"
                issues.append(
                    f"{key}の不一致: Zenn={z_val} / はてな={h_val} / 正値={t_val}"
                )
                label_map = {
                    "zenn":       "Zenn版が正しい",
                    "hatena":     "はてな版が正しい",
                    "both_wrong": "両方修正が必要",
                }
                corrections.append(
                    f"{key}: {label_map[correct]}（正値: {t_val}）"
                )
            else:
                issues.append(f"{key}の不一致: Zenn={z_val} / はてな={h_val}")

    # 銘柄・変動率パターンの一致確認（括弧内の数値）
    zenn_vals   = set(re.findall(r'[（(][+-]?\d+\.\d+%?[）)]', zenn_content))
    hatena_vals = set(re.findall(r'[（(][+-]?\d+\.\d+%?[）)]', hatena_content))
    only_zenn   = zenn_vals - hatena_vals
    only_hatena = hatena_vals - zenn_vals

    if only_zenn or only_hatena:
        issues.append(
            f"銘柄・変動率の不一致: "
            f"Zennのみ={sorted(only_zenn)[:3]} / "
            f"はてなのみ={sorted(only_hatena)[:3]}"
        )

    consistent = len(issues) == 0

    if consistent:
        print(f"  ✅ 整合性チェック: 問題なし")
    else:
        print(f"  ❌ 整合性チェック: {len(issues)}件の不整合")
        for issue in issues:
            print(f"     ⚠️ {issue}")
        for correction in corrections:
            print(f"     🔧 {correction}")

    return {
        "consistent":  consistent,
        "issues":      issues,
        "corrections": corrections,
    }
