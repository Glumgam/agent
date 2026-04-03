"""
全国ローカルニュース収集システム。
収集ソース:
1. Google News RSS（地域×キーワード検索）
2. 号外NET（全国市区町村）
3. 登録済みローカルサイト（knowledge/local_sources.json で管理）

発見した新サイトは knowledge/local_sources.json に自動登録される。

Level 1（本実装）: Google News RSS + 号外NET
Level 2（後日）: X検索 + みんなの経済新聞
Level 3（後日）: 自動サイト発見・登録システム
"""
import json
import re
import time
import feedparser
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

AGENT_ROOT   = Path(__file__).parent
SOURCES_FILE = AGENT_ROOT / "knowledge" / "local_sources.json"
HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}

# -------------------------------------------------------
# Google News RSS（地域×キーワード）
# -------------------------------------------------------

# 経済・法務に影響しうるキーワード
SEARCH_KEYWORDS = [
    "逮捕", "起訴", "書類送検",
    "倒産", "破産", "民事再生",
    "行政処分", "業務停止", "課徴金",
    "工場 火災", "工場 爆発",
    "大規模 停電", "インフラ 障害",
    "ストライキ", "労働争議",
]

# 対象地域（主要都市・工業地帯を優先）
TARGET_REGIONS = [
    "北海道", "仙台", "新潟",
    "東京", "横浜", "川崎", "千葉", "埼玉",
    "名古屋", "浜松", "豊田",
    "大阪", "京都", "神戸",
    "広島", "福岡", "北九州", "熊本",
    "那覇",
]

# 全国地方紙RSSソース（地域バランスを考慮）
LOCAL_NEWS_SOURCES = [
    # 北海道・東北
    {"name": "北海道新聞",   "url": "https://www.hokkaido-np.co.jp/rss/index.html",     "region": "北海道"},
    {"name": "河北新報",     "url": "https://kahoku.news/feed/",                         "region": "東北"},
    # 関東
    {"name": "東京新聞",     "url": "https://www.tokyo-np.co.jp/rss/all.xml",            "region": "関東"},
    {"name": "神奈川新聞",   "url": "https://www.kanaloco.jp/feed/",                     "region": "関東"},
    # 中部
    {"name": "中日新聞",     "url": "https://www.chunichi.co.jp/rss/list/national.xml",  "region": "中部"},
    {"name": "信濃毎日新聞", "url": "https://www.shinmai.co.jp/rss/news.xml",            "region": "中部"},
    # 近畿
    {"name": "京都新聞",     "url": "https://www.kyoto-np.co.jp/rss/news.xml",           "region": "近畿"},
    {"name": "神戸新聞",     "url": "https://www.kobe-np.co.jp/rss/news.xml",            "region": "近畿"},
    # 中国・四国
    {"name": "中国新聞",     "url": "https://www.chugoku-np.co.jp/rss/",                 "region": "中国"},
    {"name": "愛媛新聞",     "url": "https://www.ehime-np.co.jp/rss/news.xml",           "region": "四国"},
    # 九州・沖縄
    {"name": "西日本新聞",   "url": "https://www.nishinippon.co.jp/rss/nnp/all.xml",     "region": "九州"},
    {"name": "沖縄タイムス", "url": "https://www.okinawatimes.co.jp/rss/articles.xml",   "region": "沖縄"},
]


def fetch_google_news_rss(keyword: str, region: str = "", max_items: int = 5) -> list:
    """
    Google News RSSで地域×キーワード検索する。
    失敗時は空リストを返す（呼び出し元の処理を止めない）。
    """
    query = f"{region} {keyword}".strip() if region else keyword
    url   = (
        f"https://news.google.com/rss/search?"
        f"q={quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    )
    try:
        feed  = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            items.append({
                "title":     title,
                "url":       entry.get("link", ""),
                "source":    entry.get("source", {}).get("title", "Google News"),
                "published": entry.get("published", ""),
                "genre":     "local",
                "keyword":   keyword,
                "region":    region,
            })
        return items
    except Exception:
        return []


def collect_google_news_local(max_per_query: int = 3) -> list:
    """
    主要地域×キーワードでGoogle Newsを収集する。
    全国向け（地域なし）+ 優先地域×優先キーワードの2段階。
    """
    all_items = []
    seen_urls = set()

    # 全国向け（地域なし）
    for kw in SEARCH_KEYWORDS:
        for item in fetch_google_news_rss(kw, "", max_per_query):
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                all_items.append(item)
        time.sleep(0.3)

    # 地域×キーワード（重要な組み合わせのみ）
    priority_regions  = ["東京", "大阪", "名古屋", "福岡", "横浜"]
    priority_keywords = ["逮捕", "倒産", "行政処分", "工場 火災"]
    for region in priority_regions:
        for kw in priority_keywords:
            for item in fetch_google_news_rss(kw, region, 2):
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    all_items.append(item)
            time.sleep(0.3)

    print(f"  [Google News] {len(all_items)}件取得")
    return all_items


# -------------------------------------------------------
# 号外NET（全国市区町村）
# -------------------------------------------------------

GOGAI_PREFECTURES = {
    "北海道": "hokkaido",
    "宮城":   "miyagi",
    "東京":   "tokyo",
    "神奈川": "kanagawa",
    "愛知":   "aichi",
    "大阪":   "osaka",
    "兵庫":   "hyogo",
    "広島":   "hiroshima",
    "山口":   "yamaguchi",
    "福岡":   "fukuoka",
    "熊本":   "kumamoto",
    "沖縄":   "okinawa",
}


def fetch_gogai_net(pref_en: str, max_items: int = 10) -> list:
    """
    号外NETから都道府県のニュースを取得する。
    失敗時は空リストを返す（スキップ）。
    """
    url = f"https://{pref_en}.goguynet.jp/feed/"
    try:
        feed  = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            items.append({
                "title":     title,
                "url":       entry.get("link", ""),
                "source":    f"号外NET({pref_en})",
                "published": entry.get("published", ""),
                "genre":     "local",
            })
        return items
    except Exception:
        return []


def collect_gogai_net_all(max_per_pref: int = 5) -> list:
    """
    号外NETから全都道府県のニュースを収集する。
    各県は個別 try/except でスキップ可能。
    """
    all_items = []
    for pref_ja, pref_en in GOGAI_PREFECTURES.items():
        try:
            items = fetch_gogai_net(pref_en, max_per_pref)
            all_items.extend(items)
        except Exception:
            pass
        time.sleep(0.3)
    print(f"  [号外NET] {len(all_items)}件取得")
    return all_items


# -------------------------------------------------------
# 登録済みローカルサイト管理
# -------------------------------------------------------

def load_local_sources() -> list:
    """
    登録済みローカルサイト一覧を読み込む。
    ファイルが存在しない場合は初期データで作成する。
    """
    if not SOURCES_FILE.exists():
        default = [
            {
                "name":   "周南地域ニュース",
                "url":    "https://www.shinshunan.co.jp/news/shunan/rss.xml",
                "region": "山口",
                "genre":  "local",
                "active": True,
            },
            {
                "name":   "周南・下松・光ニュース",
                "url":    "https://shunan-kudamatsu-hikari.goguynet.jp/feed/",
                "region": "山口",
                "genre":  "local",
                "active": True,
            },
        ]
        SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
        SOURCES_FILE.write_text(
            json.dumps(default, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return default
    try:
        return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def register_local_source(name: str, url: str, region: str = "") -> bool:
    """
    新しいローカルサイトを登録する。
    既に登録済みの場合はスキップして False を返す。
    """
    sources = load_local_sources()
    urls    = [s["url"] for s in sources]
    if url in urls:
        return False  # 既に登録済み
    sources.append({
        "name":       name,
        "url":        url,
        "region":     region,
        "genre":      "local",
        "active":     True,
        "registered": datetime.now().strftime("%Y-%m-%d"),
    })
    SOURCES_FILE.write_text(
        json.dumps(sources, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  ✅ ローカルサイト登録: {name} ({url})")
    return True


def collect_registered_sources(max_per_source: int = 10) -> list:
    """
    登録済みローカルサイトからニュースを収集する。
    各ソースは個別 try/except でスキップ可能。
    """
    sources   = load_local_sources()
    all_items = []
    for source in sources:
        if not source.get("active", True):
            continue
        try:
            feed  = feedparser.parse(source["url"])
            items = []
            for entry in feed.entries[:max_per_source]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                items.append({
                    "title":     title,
                    "url":       entry.get("link", ""),
                    "source":    source["name"],
                    "region":    source.get("region", ""),
                    "published": entry.get("published", ""),
                    "genre":     "local",
                })
            all_items.extend(items)
            print(f"  ✅ {source['name']}: {len(items)}件")
        except Exception:
            print(f"  ⚠️ {source['name']}: 取得失敗（スキップ）")
        time.sleep(0.3)
    return all_items


# -------------------------------------------------------
# メイン収集関数
# -------------------------------------------------------

def collect_local_news(max_per_source: int = 5) -> list:
    """
    全国地方紙 + 号外NET + Google News からニュースを収集して返す。
    収集順:
      1. 全国地方紙RSS（LOCAL_NEWS_SOURCES）
      2. 号外NET（都道府県別）
      3. Google News（地域×キーワード）
    重複は URL 基準で除去する。
    """
    all_items = []
    success   = 0
    print("  🗾 ローカルニュース収集中...")

    # 1. 全国地方紙RSS
    for source in LOCAL_NEWS_SOURCES:
        try:
            feed  = feedparser.parse(source["url"])
            items = []
            for entry in feed.entries[:max_per_source]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                items.append({
                    "title":     title,
                    "url":       entry.get("link", ""),
                    "source":    source["name"],
                    "region":    source["region"],
                    "published": entry.get("published", ""),
                    "genre":     "local",
                })
            all_items.extend(items)
            if items:
                success += 1
                print(f"  ✅ {source['name']}（{source['region']}）: {len(items)}件")
            else:
                print(f"  ⚠️ {source['name']}: 0件")
        except Exception as e:
            print(f"  ⚠️ {source['name']} スキップ: {e}")
        time.sleep(0.3)

    # 2. 号外NET（全国）
    try:
        gogai = collect_gogai_net_all()
        all_items.extend(gogai)
    except Exception as e:
        print(f"  ⚠️ 号外NET収集失敗: {e}")

    # 3. Google News（地域×キーワード）
    try:
        google = collect_google_news_local()
        all_items.extend(google)
    except Exception as e:
        print(f"  ⚠️ Google News収集失敗: {e}")

    # 重複除去（URL基準）
    seen   = set()
    unique = []
    for item in all_items:
        key = item.get("url", "") or item.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    print(f"  🗾 ローカルニュース合計: {len(unique)}件"
          f"（地方紙{success}/{len(LOCAL_NEWS_SOURCES)}ソース成功）")
    return unique


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="全国ローカルニュース収集")
    parser.add_argument("--register", nargs=3, metavar=("NAME", "URL", "REGION"),
                        help="新サイトを登録: --register 名前 URL 地域")
    parser.add_argument("--list", action="store_true", help="登録済みサイト一覧")
    args = parser.parse_args()

    if args.register:
        register_local_source(*args.register)
    elif getattr(args, "list"):
        for s in load_local_sources():
            status = "✅" if s.get("active") else "⏸️"
            print(f"  {status} [{s.get('region','?')}] {s['name']} - {s['url']}")
    else:
        items = collect_local_news()
        print(f"\n合計: {len(items)}件")
        for item in items[:10]:
            print(f"  [{item['source']}] {item['title'][:50]}")
