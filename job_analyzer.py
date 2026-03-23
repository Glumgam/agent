"""
求人・採用動向収集システム。

収集ソース:
- Google News RSS（採用/求人/人員削減ニュース）
- 企業別採用動向（Google News 企業名+採用クエリ）

分析内容:
- 業界別採用トレンド（AI/DX/クラウド等）
- 企業別採用シグナル（積極採用 / 人員削減 / 海外展開）
- 注目技術キーワード（求人記事から集計）

※ 投資助言は行わない。データの収集・整理・紹介のみ。
"""
import re
import json
import requests
import feedparser
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent
JOB_DIR    = AGENT_ROOT / "knowledge" / "jobs"
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


# =====================================================
# 技術・戦略キーワード
# =====================================================
TECH_KEYWORDS = [
    "AI", "機械学習", "深層学習", "LLM", "生成AI",
    "DX", "デジタルトランスフォーメーション",
    "クラウド", "AWS", "Azure", "GCP",
    "データサイエンティスト", "データエンジニア",
    "セキュリティ", "サイバーセキュリティ",
    "IoT", "半導体", "EV", "自動運転",
    "ブロックチェーン", "Web3", "フィンテック",
    "Python", "Go", "Rust", "TypeScript",
    "MLOps", "DevOps", "SRE",
]

POSITIVE_SIGNALS = [
    "採用強化", "大規模採用", "採用拡大", "即戦力", "急募",
    "中途採用", "新卒採用", "エンジニア採用", "AI人材",
    "増員", "人材確保", "採用計画", "積極採用",
]

NEGATIVE_SIGNALS = [
    "希望退職", "早期退職", "リストラ", "人員削減", "組織再編",
    "黒字リストラ", "退職勧奨", "雇い止め",
]

GLOBAL_SIGNALS = [
    "グローバル採用", "海外採用", "外国人材", "インド", "ベトナム",
    "英語必須", "グローバル展開",
]

RESEARCH_SIGNALS = [
    "研究職", "R&D", "先行開発", "基礎研究", "博士", "ポスドク",
]


# =====================================================
# Google News RSS取得
# =====================================================
def _fetch_google_news(query: str, max_items: int = 15) -> list:
    """
    Google News RSS から求人・採用関連ニュースを取得する。
    Returns: [{title, link, summary, pub, source}]
    """
    try:
        q_enc = requests.utils.quote(query)
        url   = f"{GOOGLE_NEWS_RSS}?q={q_enc}&hl=ja&gl=JP&ceid=JP:ja"
        feed  = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            title   = entry.get("title", "").strip()
            link    = entry.get("link", "")
            summary = re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:300].strip()
            pub     = entry.get("published", "")
            # Google NewsのタイトルはNHK - サイト名の形式
            # 末尾の "- サイト名" を取り除く
            source = ""
            m = re.search(r' - ([^-]+)$', title)
            if m:
                source = m.group(1).strip()
                title  = title[:m.start()].strip()
            if title:
                items.append({
                    "title":   title,
                    "link":    link,
                    "summary": summary,
                    "pub":     pub,
                    "source":  source or "Google News",
                })
        return items
    except Exception as e:
        print(f"  ⚠️ Google News ({query[:20]}...): {e}")
        return []


# =====================================================
# 業界別採用トレンド
# =====================================================
INDUSTRY_QUERIES = {
    "AI・機械学習":     "AI人材 採用 拡大",
    "DX・データ":       "DX 採用強化 データサイエンティスト",
    "クラウド・インフラ": "クラウドエンジニア 採用 AWS Azure",
    "半導体・電子部品": "半導体 技術者 採用",
    "自動車・EV":       "EV 自動運転 エンジニア 採用",
    "金融・FinTech":    "フィンテック 採用 エンジニア",
    "人員削減動向":     "希望退職 上場企業",
}


def fetch_industry_job_trends() -> dict:
    """業界別の採用・求人トレンドをGoogle Newsから収集する"""
    print("  💼 業界別採用トレンド収集中...")
    results = {}
    ok = 0

    for industry, query in INDUSTRY_QUERIES.items():
        items = _fetch_google_news(query, max_items=10)
        if items:
            trends = _count_tech_keywords(items)
            results[industry] = {
                "job_count":     len(items),
                "top_keywords":  dict(list(trends.items())[:5]),
                "sample_titles": [it["title"] for it in items[:3]],
                "is_negative":   industry == "人員削減動向",
            }
            ok += 1
            top_kw = list(trends.keys())[:3]
            kw_str = ", ".join(top_kw) if top_kw else "（なし）"
            print(f"  ✅ {industry}: {len(items)}件  キーワード: {kw_str}")
        else:
            results[industry] = {
                "job_count": 0, "top_keywords": {}, "sample_titles": [],
                "is_negative": False,
            }
            print(f"  ⚠️ {industry}: 0件")

    print(f"  [採用] {ok}/{len(INDUSTRY_QUERIES)} カテゴリ取得")
    return results


# =====================================================
# 企業別採用シグナル
# =====================================================
COMPANY_JOB_QUERIES = {
    "トヨタ自動車":   "トヨタ 採用 エンジニア",
    "ソニーグループ": "ソニー 採用 AI",
    "日立製作所":     "日立 採用 DX",
    "富士通":         "富士通 採用",
    "NTT":            "NTT 採用 DX",
    "ソフトバンク":   "ソフトバンク 採用 AI",
    "楽天グループ":   "楽天 採用 エンジニア",
    "任天堂":         "任天堂 採用 ゲーム",
}


def _count_tech_keywords(items: list) -> dict:
    """記事リストから技術キーワード出現数を集計する"""
    counts = {}
    for item in items:
        text = item.get("title", "") + " " + item.get("summary", "")
        for kw in TECH_KEYWORDS:
            if kw in text:
                counts[kw] = counts.get(kw, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def _detect_strategy_signal(items: list) -> str:
    """採用ニュースから企業の戦略シグナルを推定する"""
    pos = neg = glob = res = 0
    for item in items:
        text = item.get("title", "") + " " + item.get("summary", "")
        pos  += sum(1 for kw in POSITIVE_SIGNALS  if kw in text)
        neg  += sum(1 for kw in NEGATIVE_SIGNALS  if kw in text)
        glob += sum(1 for kw in GLOBAL_SIGNALS    if kw in text)
        res  += sum(1 for kw in RESEARCH_SIGNALS  if kw in text)

    if neg > 0:
        return "⚠️ 人員削減・組織再編の報道あり"
    if pos >= 3:
        return "📈 積極採用・採用強化の報道あり"
    if glob >= 2:
        return "🌏 グローバル採用・海外展開の動き"
    if res >= 2:
        return "🔬 研究開発人材の採用強化"
    if pos >= 1:
        return "🔄 採用活動継続中"
    return "（報道なし）"


def fetch_company_job_data(companies: list = None) -> dict:
    """
    企業別採用動向をGoogle Newsから取得して分析する。
    companies: 調査対象企業名リスト（Noneの場合はデフォルト8社）
    """
    print("  🏢 企業別採用動向収集中...")
    query_map = {}
    if companies:
        for c in companies:
            query_map[c] = f"{c} 採用"
    else:
        query_map = COMPANY_JOB_QUERIES

    results = {}
    for company, query in list(query_map.items())[:8]:  # 最大8社
        items    = _fetch_google_news(query, max_items=10)
        signal   = _detect_strategy_signal(items)
        tech     = dict(list(_count_tech_keywords(items).items())[:5])
        results[company] = {
            "company":    company,
            "job_count":  len(items),
            "main_signal": signal,
            "tech_focus": tech,
            "headlines":  [it["title"] for it in items[:2]],
            "note":       "Google News 採用関連報道からの推定",
        }
        print(f"  ✅ {company}: {len(items)}件  → {signal}")

    return results


# =====================================================
# メイン収集
# =====================================================
def collect_job_data(target_companies: list = None) -> dict:
    """
    採用・求人データを収集して返す。
    target_companies: 優先調査企業リスト（株価ランキング上位など）
    """
    print("\n  💼 求人・採用データ収集中...")

    # 業界トレンド
    industry_trends = fetch_industry_job_trends()

    # 企業別採用動向
    company_data = fetch_company_job_data(target_companies)

    # 全体集計（AI人材・人員削減の総件数を概算）
    all_items_sample = _fetch_google_news("採用強化 上場企業 エンジニア", max_items=20)
    overall_trends = _count_tech_keywords(all_items_sample)

    data = {
        "date":               datetime.now().strftime("%Y-%m-%d %H:%M"),
        "industry_trends":    industry_trends,
        "company_data":       company_data,
        "overall_trends":     dict(list(overall_trends.items())[:10]),
        "total_articles_sampled": len(all_items_sample),
    }

    # 保存
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = JOB_DIR / f"{stamp}_jobs.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  💾 保存: {out_path.name}")
    return data


# =====================================================
# 記事用フォーマット
# =====================================================
def format_jobs_for_article(data: dict) -> str:
    """採用・求人データを記事挿入用 Markdown に変換する"""
    if not data:
        return ""

    lines = ["## 💼 企業採用動向から読む経営戦略\n"]
    lines.append(
        "> ⚠️ 以下は報道・求人情報の集計です。確定的な情報ではありません。\n"
    )

    # 業界別トレンド
    industry_trends = data.get("industry_trends", {})
    positive_industries = {
        k: v for k, v in industry_trends.items()
        if v.get("job_count", 0) > 0 and not v.get("is_negative")
    }
    negative_industries = {
        k: v for k, v in industry_trends.items()
        if v.get("job_count", 0) > 0 and v.get("is_negative")
    }

    if positive_industries:
        lines.append("### 📊 業界別採用トレンド")
        for industry, info in positive_industries.items():
            count   = info.get("job_count", 0)
            top_kws = list(info.get("top_keywords", {}).keys())[:3]
            kw_str  = "、".join(top_kws) if top_kws else "（関連報道あり）"
            lines.append(f"- **{industry}**: {count}件  注目: {kw_str}")
        lines.append("")

    if negative_industries:
        lines.append("### ⚠️ 人員削減・組織再編の動向")
        for industry, info in negative_industries.items():
            count   = info.get("job_count", 0)
            samples = info.get("sample_titles", [])
            lines.append(f"- **{industry}**: {count}件の報道")
            for t in samples[:2]:
                lines.append(f"  - {t[:60]}")
        lines.append("")

    # 企業別採用シグナル
    company_data = data.get("company_data", {})
    if company_data:
        lines.append("### 🏢 主要企業の採用シグナル")
        for company, info in company_data.items():
            count  = info.get("job_count", 0)
            signal = info.get("main_signal", "（報道なし）")
            tech   = list(info.get("tech_focus", {}).keys())[:2]
            if count > 0 and signal != "（報道なし）":
                tech_str = f"（{', '.join(tech)}）" if tech else ""
                lines.append(f"- **{company}**: {signal} {tech_str}")
        lines.append("")

    # 全体技術トレンド
    overall = data.get("overall_trends", {})
    if overall:
        lines.append("### 🔧 注目される採用スキル")
        top = list(overall.items())[:8]
        kw_list = "  ".join([f"`{k}` ×{v}" for k, v in top])
        lines.append(kw_list)
        lines.append("")

    lines.append(
        "> 📎 データソース: Google News 採用関連記事（集計日: "
        + data.get("date", "")[:10]
        + "）"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="求人・採用動向収集システム")
    parser.add_argument(
        "--companies", nargs="*", default=None,
        help="調査対象企業名（スペース区切り）"
    )
    parser.add_argument(
        "--industry-only", action="store_true",
        help="業界トレンドのみ取得"
    )
    args = parser.parse_args()

    if args.industry_only:
        trends = fetch_industry_job_trends()
        print()
        for k, v in trends.items():
            print(f"{k}: {v['job_count']}件")
            for kw, cnt in v["top_keywords"].items():
                print(f"  {kw}: {cnt}")
    else:
        data = collect_job_data(target_companies=args.companies)
        print()
        print(format_jobs_for_article(data))
