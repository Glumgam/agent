"""
投資記事ファクトチェックシステム。
チェック内容:
1. 数値の整合性（日経平均・為替・原油等）
2. コンテキスト外の架空情報検出
3. VIXと株価の方向性の矛盾
"""
import re
from pathlib import Path

AGENT_ROOT = Path(__file__).parent

# 架空情報でよく使われるパターン（コンテキスト外の場合のみ警告）
_HALLUCINATION_PATTERNS = [
    r'米中関係',
    r'地[缘緣]政治',
    r'アップルカー',
    r'Apple\s*Car',
    r'リーマン',
    r'コロナ',
    r'ウクライナ',
    r'台湾有事',
]


def check_numbers(content: str, finance_data: dict) -> list:
    """記事内の数値とコンテキストデータを照合する。"""
    issues = []
    market = finance_data.get("market_summary", {})
    macro  = finance_data.get("macro", {})
    forex  = macro.get("forex", {})
    us     = macro.get("us_stocks", {})
    comm   = macro.get("commodities", {})

    # 日経平均チェック（許容誤差: 500円）
    nikkei_actual_str = market.get("nikkei_price", "").replace(",", "")
    if nikkei_actual_str:
        try:
            nikkei_actual = float(nikkei_actual_str)
            nikkei_in_article = re.findall(r'[3-6][0-9],[0-9]{3}(?:\.[0-9]+)?(?=円)', content)
            for n in nikkei_in_article:
                n_val = float(n.replace(",", ""))
                if abs(n_val - nikkei_actual) > 500:
                    issues.append(
                        f"日経平均の数値が実際と大きく乖離: 記事={n} / 実際={market.get('nikkei_price')}"
                    )
        except (ValueError, TypeError):
            pass

    # USD/JPY チェック（許容誤差: 2円）
    usd_jpy_actual = forex.get("USD/JPY", {}).get("price")
    if isinstance(usd_jpy_actual, float):
        fx_in_article = re.findall(r'1[4-7][0-9]\.[0-9]+(?=円)', content)
        for fx in fx_in_article:
            try:
                fx_val = float(fx)
                if abs(fx_val - usd_jpy_actual) > 2.0:
                    issues.append(
                        f"USD/JPY数値の乖離: 記事={fx_val}円 / 実際={usd_jpy_actual}円"
                    )
            except (ValueError, TypeError):
                pass

    # VIX チェック（「VIX」直後の数値のみ対象、許容誤差: 1.0ポイント）
    vix_actual = us.get("VIX", {}).get("price")
    if isinstance(vix_actual, float):
        vix_in_article = re.findall(r'VIX[^0-9]{0,10}?(\d{1,3}(?:\.\d{1,2})?)', content)
        for v in vix_in_article:
            try:
                v_val = float(v)
                if 5 <= v_val <= 100 and abs(v_val - vix_actual) > 1.0:
                    issues.append(
                        f"VIX数値の乖離: 記事={v_val}pt / 実際={vix_actual:.2f}pt"
                    )
            except (ValueError, TypeError):
                pass

    # WTI原油 チェック（「WTI」「原油」直後の数値のみ対象、許容誤差: 2ドル）
    wti_actual = comm.get("WTI原油", {}).get("price")
    if isinstance(wti_actual, float):
        wti_in_article = re.findall(r'(?:WTI|原油)[^0-9]{0,10}?(\d{2,3}(?:\.\d{1,2})?)', content)
        for w in wti_in_article:
            try:
                w_val = float(w)
                if 20 <= w_val <= 300 and abs(w_val - wti_actual) > 2.0:
                    issues.append(
                        f"WTI原油数値の乖離: 記事={w_val}ドル / 実際={wti_actual:.2f}ドル"
                    )
            except (ValueError, TypeError):
                pass

    # S&P500 チェック（「S&P」直後の数値のみ対象、許容誤差: 50ポイント）
    sp500_actual = us.get("S&P500", {}).get("price")
    if isinstance(sp500_actual, float):
        sp_in_article = re.findall(r'S&P500?[^0-9]{0,10}?(\d{1,2},?\d{3}(?:\.\d{1,2})?)', content)
        for s in sp_in_article:
            try:
                s_val = float(s.replace(",", ""))
                if 1000 <= s_val <= 20000 and abs(s_val - sp500_actual) > 50:
                    issues.append(
                        f"S&P500数値の乖離: 記事={s_val}pt / 実際={sp500_actual:.2f}pt"
                    )
            except (ValueError, TypeError):
                pass

    return issues


def check_hallucination(content: str, finance_data: dict) -> list:
    """コンテキストに含まれない可能性のある情報を警告する。"""
    warnings = []

    # コンテキストから許可されたキーワードを収集
    allowed_text = " ".join([
        " ".join(finance_data.get("up_ranking", []) + finance_data.get("down_ranking", [])),
        " ".join(n.get("title", "") for n in finance_data.get("news", [])),
        " ".join(
            i.get("title", "")
            for i in finance_data.get("legal", {}).get("high", [])
            + finance_data.get("legal", {}).get("medium", [])
        ),
    ])

    for pattern in _HALLUCINATION_PATTERNS:
        if re.search(pattern, content) and not re.search(pattern, allowed_text):
            warnings.append(f"コンテキスト外の情報の可能性: 「{re.findall(pattern, content)[0]}」")

    return warnings


def check_vix_consistency(content: str, finance_data: dict) -> list:
    """VIXと株価動向の記述が矛盾していないか確認する。"""
    warnings = []
    macro   = finance_data.get("macro", {})
    us      = macro.get("us_stocks", {})
    vix_chg = us.get("VIX", {}).get("change_pct")

    if not isinstance(vix_chg, float):
        return warnings

    # VIXが実際に下落しているのに記事で「VIX上昇」「不安感高まり」と書いている場合
    if vix_chg < -3:
        if re.search(r'VIX.{0,10}上昇|不安感.{0,5}高まり|恐怖感.{0,5}高まり', content):
            warnings.append(
                f"VIX説明の矛盾: 実際はVIX {vix_chg:+.1f}%（下落）なのに上昇と記述"
            )

    # VIXが実際に上昇しているのに「不安感低下」「VIX低下」と書いている場合
    # ※「リスクオン」はVIXの方向と無関係に使われる一般市場用語なので除外
    if vix_chg > 3:
        if re.search(r'不安感.{0,5}低下|恐怖感.{0,5}低下|VIX.{0,10}低下', content):
            warnings.append(
                f"VIX説明の矛盾: 実際はVIX {vix_chg:+.1f}%（上昇）なのに低下と記述"
            )

    return warnings


def check_unverifiable_time_expressions(content: str, finance_data: dict) -> list:
    """
    「〇〇ぶり」「過去〇ヶ月の高水準」等の時間表現が
    コンテキストで検証不可能な場合に警告する。
    ルール:
    - 表現自体は許容（削除不要）
    - ただし具体的な数値（「2週間ぶり」等）は警告
    - 「数カ月」「最近」等の曖昧表現は許容
    """
    issues = []
    # 具体的な数値を伴う時間表現（検証不可）
    SPECIFIC_TIME_PATTERNS = [
        r'\d+週間ぶり',          # 「2週間ぶり」
        r'\d+ヶ月ぶり',          # 「3ヶ月ぶり」
        r'\d+カ月ぶり',          # 「3カ月ぶり」
        r'\d+年ぶり',            # 「1年ぶり」
        r'\d+日ぶり',            # 「10日ぶり」
        r'過去\d+[週ヶカ年日]',  # 「過去3ヶ月」
        r'\d+ヶ月来',            # 「3ヶ月来」
        r'\d+カ月来',            # 「3カ月来」
        r'\d+[週年日]来',        # 「3週来」「1年来」「30日来」
    ]
    for pattern in SPECIFIC_TIME_PATTERNS:
        matches = re.findall(pattern, content)
        for match in matches:
            issues.append(
                f"時間表現の検証不可: 「{match}」"
                f"→ コンテキストに過去データがないため数値の正確性を確認できません。"
                f"「数週間ぶり」等の曖昧表現への変更を推奨します。"
            )
    return issues


_SPECULATION_PATTERNS = [
    r'業績改善の期待が背景',
    r'新規プロジェクトの発表',
    r'パートナー企業との提携が影響',
    r'技術革新や市場拡大の見込み',
    r'新規事業の発表が背景',
    r'投資家の関心が高まった.*可能性',
    r'市場シェアの低下が要因',
    r'収益モデルの見直しが背景',
    r'業績回復への期待が背景',
    r'新商品発表が材料',
]


def check_stock_explanations(content: str, finance_data: dict) -> list:
    """
    銘柄の説明に根拠のない推測が含まれていないか確認する。
    コンテキストのニュースに根拠がある場合は許容する。
    """
    warnings = []

    # コンテキストのニュースタイトルを結合（許容キーワード集合）
    allowed_text = " ".join(
        n.get("title", "") for n in finance_data.get("news", [])
    )

    for pattern in _SPECULATION_PATTERNS:
        if re.search(pattern, content):
            # コンテキストのニュースに関連語がある場合はスキップ
            keyword = re.findall(pattern, content)
            if keyword and keyword[0] not in allowed_text:
                warnings.append(
                    f"根拠なし推測の可能性: 「{keyword[0]}」"
                    f"→「背景は未公表」に変更してください"
                )

    # 曖昧な"逃げの推測"パターン
    VAGUE_PATTERNS = [
        r'とみられます',
        r'期待されています',
        r'見込まれています',
        r'と考えられます',
        r'影響していると見られる',
        r'要因と推測される',
        r'背景にあると見られる',
        r'影響を与えたと考えられる',
    ]
    for pattern in VAGUE_PATTERNS:
        if re.search(pattern, content):
            warnings.append(
                f"曖昧表現の検出: 「{pattern}」→ 根拠を明示するか「背景は未公表」に変更"
            )

    return warnings


def check_format_compliance(content: str, variant: str = "hatena") -> list:
    """
    銘柄説明が強制フォーマットに従っているか銘柄ブロック単位で確認する。
    ランキングセクションが存在する記事のみ対象。
    Zenn版（概要）はランキング詳細が不要のためスキップ。
    """
    if variant == "zenn":
        return []  # Zenn版はフォーマットチェック不要

    issues = []

    if "値上がり" not in content and "値下がり" not in content:
        return issues  # ランキング記事でなければスキップ

    # 銘柄ブロックを変動率行単位で分割（太字あり/なし両対応）
    blocks = re.split(r'\n(?=.*?\([+-]?\d+)', content)
    checked = 0
    for block in blocks:
        if not re.search(r'[（(][+-]?\d+(\.\d+)?%?[）)]', block):
            continue  # 括弧付き変動率を含まないブロックはスキップ（全角・半角両対応）
        checked += 1

        if "背景:" in block and "関連ニュース:" not in block:
            issues.append("フォーマット違反: 銘柄ブロックに「関連ニュース:」がない")
        if "関連ニュース:" in block and "背景:" not in block:
            issues.append("フォーマット違反: 銘柄ブロックに「背景:」がない")
        if re.search(r'背景:\s*$', block, re.MULTILINE):
            issues.append("フォーマット違反: 「背景:」の内容が空")
        if re.search(r'関連ニュース:\s*$', block, re.MULTILINE):
            issues.append("フォーマット違反: 「関連ニュース:」の内容が空")

    # 銘柄ブロックが検出されなかった場合は記事全体で簡易チェック
    if checked == 0:
        if "関連ニュース:" not in content:
            issues.append("フォーマット違反: 「関連ニュース:」が存在しない")
        if "背景:" not in content:
            issues.append("フォーマット違反: 「背景:」が存在しない")

    return issues


def fact_check(content: str, finance_data: dict, variant: str = "hatena") -> dict:
    """
    記事のファクトチェックを実行する。
    variant: "zenn" or "hatena"（フォーマットチェックの対象を制御）
    Returns:
        {
            "passed": bool,
            "issues": [str],
            "warnings": [str],
            "score_penalty": int,
        }
    """
    all_issues   = check_numbers(content, finance_data)
    all_warnings = (
        check_hallucination(content, finance_data)
        + check_vix_consistency(content, finance_data)
        + check_stock_explanations(content, finance_data)
        + check_format_compliance(content, variant=variant)
    )

    # 時間表現チェック
    time_issues = check_unverifiable_time_expressions(content, finance_data)
    all_warnings.extend(time_issues)

    score_penalty = len(all_issues) * 2 + len(all_warnings) * 1
    passed = len(all_issues) == 0

    if all_issues or all_warnings:
        print(f"  ⚠️ ファクトチェック:")
        for issue in all_issues:
            print(f"     ❌ {issue}")
        for warning in all_warnings:
            print(f"     ⚠️  {warning}")
    else:
        print(f"  ✅ ファクトチェック: 問題なし")

    return {
        "passed":        passed,
        "issues":        all_issues,
        "warnings":      all_warnings,
        "score_penalty": score_penalty,
    }
