"""
Zenn版・はてな版の整合性チェックシステム。

チェック項目:
1. 数値の一致（日経平均・VIX・為替・原油・S&P500）
2. はてな版のランキング銘柄件数
3. コンテキストの正値との照合
"""

import re


# -------------------------------------------------------
# 数値抽出
# -------------------------------------------------------

def extract_numbers_from_article(content: str) -> dict:
    """
    記事から主要数値を抽出する。
    変動率（%付き）はVIX値として誤検出しないよう除外する。
    """
    numbers = {}

    # 日経平均（5桁カンマ区切り+小数）
    m = re.search(r'(\d{2},\d{3}\.\d+)円', content)
    if m:
        numbers["nikkei"] = m.group(1).replace(",", "")

    # USD/JPY（「USD/JPY」直後 or 「円...ドル」）
    m = re.search(r'USD/JPY[^\d]*(\d{3}\.\d+)', content)
    if not m:
        m = re.search(r'(\d{3}\.\d+)円.*?ドル', content)
    if m:
        numbers["usd_jpy"] = m.group(1)

    # VIX（「VIX」直後の2桁+小数のみ・変動率%は除外）
    m = re.search(r'VIX[^%\d]*(\d{2}\.\d+)(?![\d%])', content)
    if m:
        numbers["vix"] = m.group(1)

    # S&P500（「S&P500」直後 例: 5,123.45 or 5123.45）
    m = re.search(r'S&P500[^\d]*([\d,]{4,}\.\d+)', content)
    if m:
        numbers["sp500"] = m.group(1).replace(",", "")

    # WTI原油（$マーク付き2〜3桁）
    m = re.search(r'WTI[^\d$]*\$(\d{2,3}\.\d+)', content)
    if not m:
        m = re.search(r'\$(\d{2,3}\.\d+).*?原油', content)
    if m:
        numbers["wti"] = m.group(1)

    return numbers


# -------------------------------------------------------
# 方向性矛盾検出
# -------------------------------------------------------

def check_directional_consistency(
    zenn_content: str,
    hatena_content: str,
    finance_data: dict,
) -> list:
    """
    「上昇/下落」「高い/低い」「円安/円高」等の
    方向性表現の矛盾を検出する。
    """
    issues = []
    seen   = set()  # 重複排除用

    market = finance_data.get("market_summary", {})
    macro  = finance_data.get("macro", {})
    us     = macro.get("us_stocks", {})
    forex  = macro.get("forex", {})
    comm   = macro.get("commodities", {})

    def get_direction(chg_pct):
        if not isinstance(chg_pct, (int, float)):
            return None
        return "上昇" if chg_pct > 0 else "下落"

    true_directions = {
        "日経平均": get_direction(market.get("nikkei_change_pct")),
        "VIX":      get_direction(us.get("VIX", {}).get("change_pct")),
        "S&P500":   get_direction(us.get("S&P500", {}).get("change_pct")),
        "USD/JPY":  get_direction(forex.get("USD/JPY", {}).get("change_pct")),
        "WTI原油":  get_direction(comm.get("WTI原油", {}).get("change_pct")),
    }

    usd_chg = forex.get("USD/JPY", {}).get("change_pct")
    if isinstance(usd_chg, (int, float)):
        true_directions["USD/JPY_ja"] = "円安" if usd_chg > 0 else "円高"

    DIRECTION_PATTERNS = {
        "日経平均": [
            (r'日経平均.*?(上昇|下落|上げ|下げ)', 1),
            (r'(上昇|下落|上げ|下げ).*?日経平均', 1),
        ],
        "VIX": [
            (r'VIX[^。\n]{0,30}(上昇|下落|低下|高まり|緩和)', 1),
            (r'(上昇|下落|低下|高まり|緩和)[^。\n]{0,20}VIX', 1),
        ],
        "USD/JPY_ja": [
            (r'(円安|円高)', 1),
        ],
    }

    OPPOSITE = {
        "上昇": ["下落", "下げ", "低下"],
        "下落": ["上昇", "上げ", "高まり"],
        "円安": ["円高"],
        "円高": ["円安"],
    }

    for key, patterns in DIRECTION_PATTERNS.items():
        true_dir = true_directions.get(key)
        if not true_dir:
            continue
        opposite_dirs = OPPOSITE.get(true_dir, [])
        for content, content_name in [
            (zenn_content, "Zenn版"),
            (hatena_content, "はてな版"),
        ]:
            for pattern, group in patterns:
                for match in re.findall(pattern, content):
                    if match in opposite_dirs:
                        issue_key = f"{content_name}:{key}:{match}"
                        if issue_key not in seen:
                            seen.add(issue_key)
                            issues.append(
                                f"方向性の矛盾({content_name}): "
                                f"{key}は実際に「{true_dir}」なのに「{match}」と記述"
                            )

    # Zenn版とはてな版間の相互矛盾チェック
    MUTUAL_PATTERNS = {
        "日経平均方向": (r'日経平均.*?(上昇|下落)', r'日経平均.*?(上昇|下落)'),
        "VIX方向":     (r'VIX[^。\n]{0,30}(上昇|下落|低下)', r'VIX[^。\n]{0,30}(上昇|下落|低下)'),
        "為替方向":    (r'(円安|円高)', r'(円安|円高)'),
    }
    CONFLICT_PAIRS = [
        {"上昇", "下落"}, {"上げ", "下げ"},
        {"円安", "円高"}, {"低下", "上昇"},
    ]

    for label, (pat_z, pat_h) in MUTUAL_PATTERNS.items():
        z_matches = re.findall(pat_z, zenn_content)
        h_matches = re.findall(pat_h, hatena_content)
        if not z_matches or not h_matches:
            continue
        z_dir = z_matches[0]
        h_dir = h_matches[0]
        for pair in CONFLICT_PAIRS:
            if z_dir in pair and h_dir in pair and z_dir != h_dir:
                issue_key = f"mutual:{label}:{z_dir}:{h_dir}"
                if issue_key not in seen:
                    seen.add(issue_key)
                    issues.append(
                        f"Zenn版とはてな版の方向性矛盾({label}): "
                        f"Zenn={z_dir} / はてな={h_dir}"
                    )
                break

    return issues


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

    # 数値の突合（両版に値が存在する場合のみ・±0.1%の誤差許容）
    for key in ["nikkei", "usd_jpy", "vix", "sp500", "wti"]:
        z_val = zenn_nums.get(key, "")
        h_val = hatena_nums.get(key, "")
        t_val = true_values.get(key, "")

        if not z_val or not h_val:
            continue  # 片方にない場合はスキップ

        # 浮動小数点の誤差を許容（±0.1%）
        try:
            z_f = float(z_val)
            h_f = float(h_val)
            if z_f > 0 and abs(z_f - h_f) / max(z_f, h_f) < 0.001:
                continue  # 誤差範囲内
        except (ValueError, TypeError):
            pass

        if z_val != h_val:
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

    # はてな版のランキング銘柄チェック（**銘柄名**（±%）パターン）
    # Zenn版は概要のため省略可 → はてな版のみ確認
    hatena_stocks = re.findall(
        r'\*\*[^*]+\*\*[（(][+-]?\d+\.\d+%?[）)]', hatena_content
    )
    if len(hatena_stocks) < 3:
        issues.append(
            f"はてな版のランキング銘柄が不足: {len(hatena_stocks)}件（最低3件必要）"
        )

    # 方向性矛盾チェック
    direction_issues = check_directional_consistency(
        zenn_content, hatena_content, finance_data
    )
    issues.extend(direction_issues)

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
