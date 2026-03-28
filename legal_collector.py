"""
裁判・行政処分データ収集システム。

収集ソース:
- 金融庁（処分情報RSS）
- 公正取引委員会（プレスリリース）
- 消費者庁（プレスリリース）
- EDINET（有価証券報告書・訂正報告書）
- 官報（公告情報）
- 裁判所（判決情報）

分析内容:
- 企業への行政処分・課徴金
- 独占禁止法違反
- 有価証券報告書の訂正
- 民事・刑事訴訟の提起

※ 事実の記録のみ。投資助言は行わない。
"""

import re
import json
import requests
import feedparser
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent
LEGAL_DIR  = AGENT_ROOT / "knowledge" / "legal"
LEGAL_DB   = AGENT_ROOT / "memory" / "legal_events_db.json"
HEADERS    = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

# =====================================================
# ローカルニュース → 法務情報抽出用キーワード
# =====================================================
LEGAL_KEYWORDS = [
    "逮捕", "起訴", "書類送検", "摘発", "捜査",
    "詐欺", "横領", "背任", "インサイダー",
    "行政処分", "業務停止", "課徴金", "排除措置",
    "訴訟", "損害賠償", "和解", "判決",
    "倒産", "破産", "民事再生", "上場廃止",
]


def extract_legal_from_local_news(news_items: list) -> list:
    """
    ローカルニュース（地方紙等）から法務・犯罪関連情報を抽出する。
    LEGAL_KEYWORDS にマッチするタイトルのみを返す。

    Args:
        news_items: news_collector.collect_all_news() の "local" リスト
    Returns:
        法務関連ニュースのリスト（risk="medium" をデフォルト付与）
    """
    legal_items = []
    for item in news_items:
        title = item.get("title", "")
        if any(kw in title for kw in LEGAL_KEYWORDS):
            # 既存の _classify_legal_risk でリスクレベルを判定
            risk = _classify_legal_risk(title)
            legal_items.append({
                "title":  title,
                "source": item.get("source", "地方紙"),
                "url":    item.get("link", item.get("url", "")),
                "risk":   risk,
            })
    return legal_items


# =====================================================
# リスク分類定義
# =====================================================

LEGAL_RISK_MAP = {
    "高リスク": {
        "keywords": [
            "業務停止命令", "免許取消", "登録取消", "課徴金",
            "排除措置命令", "刑事告発", "逮捕", "起訴",
            "粉飾決算", "不正会計", "インサイダー",
        ],
        "level": "high",
        "tag":   "🔴 重大リスク",
    },
    "中リスク": {
        "keywords": [
            "業務改善命令", "警告", "勧告", "行政指導",
            "訴訟提起", "損害賠償請求", "仮処分",
            "有価証券報告書訂正", "開示訂正",
        ],
        "level": "medium",
        "tag":   "🟡 要注意",
    },
    "低リスク・情報開示": {
        "keywords": [
            "和解", "訴訟終結", "無罪", "勝訴",
            "課徴金減額", "処分取消",
        ],
        "level": "low",
        "tag":   "🟢 解消・好転",
    },
}


# =====================================================
# 金融庁
# =====================================================

def fetch_fsa_actions() -> list:
    """金融庁の行政処分情報を取得する"""
    results = []

    try:
        # Google News経由で金融庁ニュースを取得
        query = requests.utils.quote("金融庁 行政処分 業務停止")
        url   = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed  = feedparser.parse(url)

        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            pub   = entry.get("published", "")
            link  = entry.get("link", "")

            if "金融庁" in title or "FSA" in title:
                risk = _classify_legal_risk(title)
                results.append({
                    "source":    "金融庁関連",
                    "title":     title,
                    "published": pub,
                    "link":      link,
                    "risk":      risk,
                })

        print(f"  ✅ 金融庁関連: {len(results)}件")
    except Exception as e:
        print(f"  ⚠️ 金融庁: {e}")

    return results


# =====================================================
# 公正取引委員会
# =====================================================

def fetch_jftc_actions() -> list:
    """公正取引委員会のプレスリリースを取得する"""
    results = []

    try:
        query = requests.utils.quote("公正取引委員会 排除措置命令 課徴金")
        url   = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed  = feedparser.parse(url)

        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            pub   = entry.get("published", "")
            link  = entry.get("link", "")

            if any(kw in title for kw in ["公取委", "公正取引", "独禁法", "カルテル"]):
                risk = _classify_legal_risk(title)
                results.append({
                    "source":    "公正取引委員会関連",
                    "title":     title,
                    "published": pub,
                    "link":      link,
                    "risk":      risk,
                })

        print(f"  ✅ 公正取引委員会関連: {len(results)}件")
    except Exception as e:
        print(f"  ⚠️ 公正取引委員会: {e}")

    return results


# =====================================================
# EDINET（有価証券報告書訂正）
# =====================================================

def fetch_edinet_corrections() -> list:
    """EDINETから訂正報告書を取得する"""
    results = []

    try:
        query = requests.utils.quote("有価証券報告書 訂正 訂正報告書")
        url   = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed  = feedparser.parse(url)

        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            pub   = entry.get("published", "")

            if "訂正" in title and any(
                kw in title for kw in ["有価証券", "報告書", "開示"]
            ):
                risk = _classify_legal_risk(title)
                results.append({
                    "source":    "EDINET関連",
                    "title":     title,
                    "published": pub,
                    "risk":      risk,
                })

        print(f"  ✅ EDINET関連: {len(results)}件")
    except Exception as e:
        print(f"  ⚠️ EDINET: {e}")

    return results


# =====================================================
# 企業訴訟情報
# =====================================================

def fetch_corporate_litigation(company: str = None) -> list:
    """企業の訴訟・法務リスク情報を取得する"""
    results = []

    try:
        if company:
            query = requests.utils.quote(f"{company} 訴訟 裁判 損害賠償")
        else:
            query = requests.utils.quote("上場企業 訴訟 提訴 損害賠償請求")

        url  = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(url)

        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            pub   = entry.get("published", "")
            link  = entry.get("link", "")

            if any(kw in title for kw in [
                "訴訟", "提訴", "損害賠償", "仮処分",
                "判決", "和解", "示談"
            ]):
                # 関連企業を抽出
                from stock_linker import extract_companies_from_text
                companies = extract_companies_from_text(title)
                risk      = _classify_legal_risk(title)

                results.append({
                    "source":    "訴訟関連",
                    "title":     title,
                    "published": pub,
                    "link":      link,
                    "companies": companies,
                    "risk":      risk,
                })

        label = company or "上場企業"
        print(f"  ✅ 訴訟情報({label}): {len(results)}件")
    except Exception as e:
        print(f"  ⚠️ 訴訟情報: {e}")

    return results


# =====================================================
# リスク分類
# =====================================================

def _classify_legal_risk(text: str) -> dict:
    """テキストからリスクレベルを判定する"""
    for category, config in LEGAL_RISK_MAP.items():
        if any(kw in text for kw in config["keywords"]):
            return {
                "category": category,
                "level":    config["level"],
                "tag":      config["tag"],
            }
    return {
        "category": "情報開示",
        "level":    "info",
        "tag":      "ℹ️ 情報",
    }


def _link_to_stocks(legal_items: list) -> list:
    """法務情報に関連銘柄を紐付ける"""
    # stock_linker の正しい関数名を使用
    from stock_linker import extract_companies_from_text, resolve_code_from_kabutan

    enriched = []
    for item in legal_items:
        title     = item.get("title", "")
        # fetch_corporate_litigation で既に取得済みの場合は再取得しない
        companies = item.get("companies") or extract_companies_from_text(title)

        stocks = []
        for company in companies[:2]:
            code = company.get("code") or resolve_code_from_kabutan(company["name"])
            if code:
                stocks.append({
                    "name": company["name"],
                    "code": code,
                })

        item = dict(item)
        item["related_stocks"] = stocks
        enriched.append(item)

    return enriched


# =====================================================
# メイン処理
# =====================================================

def collect_legal_data(companies: list = None) -> dict:
    """法務・行政処分データを収集する"""
    print("\n  ⚖️ 法務・行政処分データ収集中...")

    # 各ソースから収集
    fsa        = fetch_fsa_actions()
    jftc       = fetch_jftc_actions()
    edinet     = fetch_edinet_corrections()
    litigation = fetch_corporate_litigation()

    # 企業別訴訟情報
    company_litigation = []
    if companies:
        for company in companies[:2]:
            items = fetch_corporate_litigation(company)
            company_litigation.extend(items)

    # 全データを結合・重複除去（タイトル先頭40文字で判定）
    seen      = set()
    all_items = []
    for item in fsa + jftc + edinet + litigation + company_litigation:
        key = item.get("title", "")[:40]
        if key not in seen:
            seen.add(key)
            all_items.append(item)

    # 銘柄紐付け
    all_items = _link_to_stocks(all_items)

    # リスクレベル別に分類
    data = {
        "date":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "high":   [i for i in all_items if i.get("risk", {}).get("level") == "high"],
        "medium": [i for i in all_items if i.get("risk", {}).get("level") == "medium"],
        "low":    [i for i in all_items if i.get("risk", {}).get("level") == "low"],
        "info":   [i for i in all_items if i.get("risk", {}).get("level") == "info"],
        "total":  len(all_items),
    }

    print(f"  ✅ 収集完了: 高リスク{len(data['high'])}件 / "
          f"中リスク{len(data['medium'])}件 / "
          f"解消{len(data['low'])}件")

    # DBに保存
    _save_legal_db(data)

    # ファイル保存
    LEGAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LEGAL_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_legal.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  💾 保存: {out_path.name}")
    return data


def _save_legal_db(data: dict):
    """法務イベントDBに追記する"""
    db = []
    if LEGAL_DB.exists():
        try:
            db = json.loads(LEGAL_DB.read_text(encoding="utf-8"))
        except Exception:
            pass

    db.append(data)
    db = db[-180:]  # 最新180日分
    LEGAL_DB.parent.mkdir(exist_ok=True)
    LEGAL_DB.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def format_legal_for_article(data: dict) -> str:
    """法務データを記事用テキストに変換する"""
    lines = [
        "## ⚖️ 法務・規制動向\n",
        "> ⚠️ 以下は公開情報に基づく事実の整理です。",
        "> 投資判断の根拠にしないでください。\n",
    ]

    # 高リスク
    high = data.get("high", [])
    if high:
        lines.append("### 🔴 重大な法務リスク情報")
        for item in high[:3]:
            title     = item.get("title", "")
            stocks    = item.get("related_stocks", [])
            stock_str = "・".join(
                f"{s['name']}({s['code']})" for s in stocks[:2]
            ) if stocks else ""

            lines.append(f"- {title}")
            if stock_str:
                lines.append(f"  関連銘柄: {stock_str}")
        lines.append("")

    # 中リスク
    medium = data.get("medium", [])
    if medium:
        lines.append("### 🟡 注意が必要な情報")
        for item in medium[:3]:
            title     = item.get("title", "")
            stocks    = item.get("related_stocks", [])
            stock_str = "・".join(
                f"{s['name']}({s['code']})" for s in stocks[:2]
            ) if stocks else ""

            lines.append(f"- {title}")
            if stock_str:
                lines.append(f"  関連銘柄: {stock_str}")
        lines.append("")

    # 解消・好転
    low = data.get("low", [])
    if low:
        lines.append("### 🟢 リスク解消・好転情報")
        for item in low[:3]:
            title = item.get("title", "")
            lines.append(f"- {title}")
        lines.append("")

    if not (high or medium or low):
        lines.append("本日は特筆すべき法務・規制動向はありませんでした。\n")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="法務・行政処分データ収集")
    parser.add_argument(
        "--companies", nargs="*", default=None,
        help="対象企業名（スペース区切り）"
    )
    parser.add_argument(
        "--format-only", action="store_true",
        help="最新DBからフォーマットのみ出力"
    )
    args = parser.parse_args()

    if args.format_only and LEGAL_DB.exists():
        db   = json.loads(LEGAL_DB.read_text(encoding="utf-8"))
        data = db[-1] if db else {}
    else:
        data = collect_legal_data(companies=args.companies)

    print()
    print(format_legal_for_article(data))
    print(f"\n高リスク: {len(data.get('high', []))}件")
    print(f"中リスク: {len(data.get('medium', []))}件")
    print(f"解消:     {len(data.get('low', []))}件")
