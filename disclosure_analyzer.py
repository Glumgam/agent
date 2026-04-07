"""
適時開示の自動分類・関連企業深掘りシステム。

処理フロー:
1. TDnetから適時開示を取得
2. ルール+LLMでポジティブ/ネガティブ/中立に分類
3. 関連企業を抽出して深掘り
4. 記事用のコンテキストを生成

※ 断定的な投資助言は行わない。
"""

import re
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent
HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}

# LLM分類フラグ: Falseにするとルールベースのみ（高速・タイムアウトなし）
# Trueにするとqwen2.5-coder:14bで分類（精度向上・低速）
# RAM不足時は自動でFalseに切り替え（Ollamaクラッシュ防止）
def _available_ram_mb() -> int:
    """利用可能RAM(MB)を取得する（vm_stat使用）"""
    try:
        out = subprocess.check_output(["vm_stat"], text=True, timeout=3)
        free = inactive = 0
        for line in out.splitlines():
            m = re.match(r'Pages (free|inactive):\s+(\d+)', line.strip())
            if m:
                pages = int(m.group(2))
                if m.group(1) == "free":
                    free = pages
                else:
                    inactive = pages
        return (free + inactive) * 4096 // 1024 // 1024
    except Exception:
        return 9999  # 取得失敗時は制限なし

_RAM_MB = _available_ram_mb()
USE_LLM_CLASSIFY = _RAM_MB >= 2000  # 2GB未満はルールベースのみ（qwen2.5-coder:14b読込に必要）
if not USE_LLM_CLASSIFY:
    print(f"  ℹ️ 適時開示: RAM不足({_RAM_MB}MB)のためルールベース分類のみ使用")


# =====================================================
# ルールベース分類
# =====================================================

POSITIVE_KEYWORDS = [
    "上方修正", "増配", "特別配当", "自社株買い", "自己株取得",
    "大型受注", "業績好調", "黒字転換", "最高益", "過去最高",
    "業務提携", "資本提携", "共同開発", "新規契約", "合意",
    "増収増益", "営業益増", "売上高増", "子会社化",
]

NEGATIVE_KEYWORDS = [
    "下方修正", "減配", "無配", "赤字転落", "最終赤字",
    "業績悪化", "損失計上", "特別損失", "訴訟", "不祥事",
    "リコール", "行政処分", "業務停止", "倒産", "民事再生",
    "減収減益", "営業損失", "売上高減",
]

NEUTRAL_KEYWORDS = [
    "人事", "役員", "組織変更", "定時株主総会", "招集通知",
    "社名変更", "本社移転", "株式併合", "単元株変更",
]


def classify_by_rules(text: str) -> str:
    """ルールベースで分類する"""
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    elif any(kw in text for kw in NEUTRAL_KEYWORDS):
        return "neutral"
    return "unknown"


def classify_by_llm(text: str) -> str:
    """LLMで分類する（ルールで判断できない場合）"""
    from llm import ask_plain

    prompt = f"""以下の適時開示を分類してください。

開示内容: {text[:500]}

以下の4つのうちどれか1つだけ回答してください:
- positive（良いニュース: 業績向上・増配・大型提携など）
- negative（悪いニュース: 業績悪化・減配・不祥事など）
- neutral（中立: 人事・組織変更・形式的開示など）
- unknown（判断不能）

回答（1単語のみ）:"""

    try:
        # qwen3:14b はthinking modeで遅いため120秒に延長
        result = ask_plain(prompt, retries=1, timeout=120).strip().lower()
    except Exception:
        return "unknown"

    if result in ("positive", "negative", "neutral", "unknown"):
        return result
    return "unknown"


def classify_disclosure(title: str, summary: str) -> str:
    """適時開示を分類する（ルール優先・LLM補助）"""
    text = title + " " + summary

    # まずルールで試みる
    rule_result = classify_by_rules(text)
    if rule_result != "unknown":
        return rule_result

    # USE_LLM_CLASSIFY=True の場合のみLLMで補助分類
    if USE_LLM_CLASSIFY:
        return classify_by_llm(text)

    # ルール未判定はneutralとして扱う（LLM呼び出しなし）
    return "neutral"


# =====================================================
# 関連企業の抽出・深掘り
# =====================================================

def extract_partner_companies(text: str) -> list:
    """
    適時開示から関連企業名を抽出する。
    「〇〇と提携」「〇〇社と共同」などのパターンから抽出。
    """
    patterns = [
        r'([^　\s、。]+(?:株式会社|㈱|Corp\.|Inc\.|Ltd\.)[^　\s、。]*)',
        r'([ァ-ヶー]{3,}(?:社|グループ|ホールディングス))',
    ]

    companies = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            if len(m) >= 4 and len(m) <= 30:
                companies.add(m.strip())

    return list(companies)[:5]  # 最大5社


def analyze_partner_company(company_name: str) -> dict:
    """
    関連企業の情報をRAGとWebから収集して評価する。
    """
    from llm import ask_plain

    # RAGから情報を取得
    rag_context = ""
    try:
        from rag_retriever import search, format_context
        results     = search(company_name, top_k=3)
        rag_context = format_context(results, max_chars=1000)
    except Exception:
        pass

    # Web検索で補完
    web_context = ""
    try:
        resp = requests.get(
            f"https://finance.yahoo.co.jp/search/?query={requests.utils.quote(company_name)}",
            headers=HEADERS, timeout=10
        )
        text = re.sub(r'<[^>]+>', '', resp.text)
        web_context = text[:500]
    except Exception:
        pass

    context = (rag_context + "\n" + web_context).strip()
    if not context:
        context = f"{company_name}に関する情報を収集中"

    # LLMで評価コメント生成
    prompt = f"""以下の企業について、客観的な情報を200文字以内でまとめてください。

企業名: {company_name}
参考情報: {context[:1000]}

以下の観点で記述してください:
- 業種・事業内容
- 業界でのポジション
- 今回の提携・連携の意味（可能性・傾向として）

【重要】断定的な投資助言は書かないこと。
「〜の可能性がある」「〜と見られる傾向がある」などの表現を使うこと。
"""

    analysis = ask_plain(prompt)
    return {
        "company":  company_name,
        "analysis": analysis[:300] if analysis else "情報収集中",
    }


# =====================================================
# TDnet適時開示取得
# =====================================================

def fetch_disclosures() -> list:
    """
    TDnet（適時開示情報）を取得する。
    kabutanの開示情報ページから取得。
    """
    try:
        url  = "https://kabutan.jp/disclosures/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        # テーブルから開示情報を抽出
        rows = re.findall(
            r'<tr[^>]*>(.*?)</tr>',
            resp.text,
            re.DOTALL
        )

        disclosures = []
        for row in rows[:50]:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            cells = [c for c in cells if c]

            if len(cells) >= 2:
                disclosures.append({
                    "company": cells[0][:30] if cells else "",
                    "title":   cells[1][:80] if len(cells) > 1 else "",
                    "time":    cells[2][:10] if len(cells) > 2 else "",
                })

        return [d for d in disclosures if d["title"]][:20]

    except Exception as e:
        return [{"company": "取得エラー", "title": str(e), "time": ""}]


# =====================================================
# メイン処理
# =====================================================

def analyze_today_disclosures() -> dict:
    """
    本日の適時開示を取得・分類・深掘りして結果を返す。
    """
    print("  📋 適時開示を取得・分析中...")

    disclosures = fetch_disclosures()
    results = {
        "date":     datetime.now().strftime("%Y-%m-%d"),
        "positive": [],
        "negative": [],
        "neutral":  [],
        "notable":  [],  # 深掘りが必要な開示
    }

    for d in disclosures:
        text     = d["company"] + " " + d["title"]
        category = classify_disclosure(d["company"], d["title"])
        d["category"] = category

        results[category if category in ("positive", "negative", "neutral") else "neutral"].append(d)

        # 関連企業が含まれる場合は深掘り対象に追加（USE_LLM_CLASSIFY=Trueの場合のみLLM分析）
        if (any(kw in text for kw in ["提携", "共同", "合意", "契約"])
                and len(results["notable"]) < 3):
            partners = extract_partner_companies(text)
            if partners:
                d["partners"] = partners
                if USE_LLM_CLASSIFY:
                    d["partner_analysis"] = [
                        analyze_partner_company(p)
                        for p in partners[:1]  # 最大1社まで深掘り
                    ]
                results["notable"].append(d)

    # 保存
    out_dir  = AGENT_ROOT / "knowledge" / "finance"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{results['date']}_disclosures.json"
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"  ✅ 分析完了: "
          f"良いニュース{len(results['positive'])}件 / "
          f"悪いニュース{len(results['negative'])}件 / "
          f"中立{len(results['neutral'])}件 / "
          f"注目{len(results['notable'])}件")

    return results


def format_for_article(results: dict) -> str:
    """
    分析結果を記事用テキストに変換する。
    """
    lines = [f"## 本日（{results['date']}）の適時開示まとめ\n"]

    if results["positive"]:
        lines.append("### ✅ ポジティブな開示")
        for d in results["positive"][:5]:
            lines.append(f"- **{d['company']}**: {d['title']}")
        lines.append("")

    if results["negative"]:
        lines.append("### ⚠️ 注意が必要な開示")
        for d in results["negative"][:5]:
            lines.append(f"- **{d['company']}**: {d['title']}")
        lines.append("")

    if results["neutral"]:
        lines.append("### 📋 中立的な開示")
        for d in results["neutral"][:5]:
            lines.append(f"- **{d['company']}**: {d['title']}")
        lines.append("")

    if results["notable"]:
        lines.append("### 🔍 注目トピック（提携・共同開発）")
        for d in results["notable"][:3]:
            lines.append(f"\n#### {d['company']}: {d['title']}")
            for pa in d.get("partner_analysis", []):
                lines.append(f"\n**{pa['company']}について:**")
                lines.append(pa["analysis"])
        lines.append("")

    return "\n".join(lines)
