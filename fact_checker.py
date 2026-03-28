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

    # 日経平均チェック
    nikkei_actual_str = market.get("nikkei_price", "").replace(",", "")
    if nikkei_actual_str:
        try:
            nikkei_actual = float(nikkei_actual_str)
            # 記事内の日経平均数値（4〜5万円台）を抽出
            nikkei_in_article = re.findall(r'[3-6][0-9],[0-9]{3}(?:\.[0-9]+)?(?=円)', content)
            for n in nikkei_in_article:
                n_val = float(n.replace(",", ""))
                if abs(n_val - nikkei_actual) > 500:
                    issues.append(
                        f"日経平均の数値が実際と大きく乖離: 記事={n} / 実際={market.get('nikkei_price')}"
                    )
        except (ValueError, TypeError):
            pass

    # USD/JPY チェック
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

    # VIXが実際に上昇しているのに「不安感低下」と書いている場合
    if vix_chg > 3:
        if re.search(r'不安感.{0,5}低下|恐怖感.{0,5}低下|リスクオン', content):
            warnings.append(
                f"VIX説明の矛盾: 実際はVIX {vix_chg:+.1f}%（上昇）なのに低下と記述"
            )

    return warnings


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


def check_format_compliance(content: str) -> list:
    """
    銘柄説明が強制フォーマットに従っているか銘柄ブロック単位で確認する。
    ランキングセクションが存在する記事のみ対象。
    """
    issues = []

    if "値上がり" not in content and "値下がり" not in content:
        return issues  # ランキング記事でなければスキップ

    # 銘柄ブロックを変動率行単位で分割（太字あり/なし両対応）
    blocks = re.split(r'\n(?=.*?\([+-]?\d+)', content)
    checked = 0
    for block in blocks:
        if not re.search(r'[+-]?\d+(\.\d+)?%?', block):
            continue  # 変動率を含まないブロックはスキップ
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


def fact_check(content: str, finance_data: dict) -> dict:
    """
    記事のファクトチェックを実行する。
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
        + check_format_compliance(content)
    )

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
