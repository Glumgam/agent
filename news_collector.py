"""
汎用ニュース収集システム。
複数のRSS・ニュースサイトからジャンル別に情報を収集する。
research_agent.py の情報収集を補強する。

使い方:
  python news_collector.py               # 全ジャンル収集
  python news_collector.py --genre tech  # 特定ジャンルのみ
  python news_collector.py --stats       # 統計表示
"""
import re
import json
import hashlib
import requests
import feedparser
from pathlib import Path
from datetime import datetime, timedelta

AGENT_ROOT = Path(__file__).parent
NEWS_DIR   = AGENT_ROOT / "knowledge" / "news_cache"
SEEN_FILE  = AGENT_ROOT / "memory" / "seen_news.json"
HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}

# =====================================================
# 信頼度レベル定義
# =====================================================
CREDIBILITY_LEVELS = {
    "high":   {"label": "高信頼",  "score": 0.9, "tag": "✅ 公式"},
    "medium": {"label": "中信頼",  "score": 0.6, "tag": "📝 ブログ"},
    "low":    {"label": "要確認",  "score": 0.3, "tag": "💬 掲示板"},
}

# =====================================================
# RSSフィード定義（ジャンル別）
# credibility: "high"=公式メディア / "medium"=ブログ / "low"=掲示板・まとめ
# =====================================================
RSS_SOURCES = {
    "tech": [
        {"name": "Gihyo",           "url": "https://gihyo.jp/feed/rss2",                                      "credibility": "high"},
        {"name": "ITmedia",         "url": "https://rss.itmedia.co.jp/rss/2.0/itmediatechnews.xml",           "credibility": "high"},
        {"name": "ZDNet Japan",     "url": "https://japan.zdnet.com/rss/news/",                               "credibility": "high"},
        {"name": "Qiita",           "url": "https://qiita.com/popular-items/feed",                            "credibility": "medium"},
        {"name": "Zenn",            "url": "https://zenn.dev/feed",                                           "credibility": "medium"},
        {"name": "ASCII",           "url": "https://ascii.jp/rss.xml",                                        "credibility": "high"},
        {"name": "マイナビ Tech",   "url": "https://news.mynavi.jp/techplus/rss/index",                       "credibility": "high"},
    ],
    "ai": [
        {"name": "arXiv AI",        "url": "https://export.arxiv.org/rss/cs.AI",                              "credibility": "high"},
        {"name": "Ledge.ai",        "url": "https://ledge.ai/feed/",                                          "credibility": "medium"},
        {"name": "ITmedia AI",      "url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",                   "credibility": "high"},
        {"name": "東洋経済テック",  "url": "https://toyokeizai.net/list/feed/rss",                            "credibility": "high"},
    ],
    "finance": [
        # 既存ソース
        {"name": "NHK経済",         "url": "https://www3.nhk.or.jp/rss/news/cat4.xml",                       "credibility": "high"},
        {"name": "東洋経済",        "url": "https://toyokeizai.net/list/feed/rss",                            "credibility": "high"},
        {"name": "Yahoo金融",       "url": "https://news.yahoo.co.jp/rss/topics/business.xml",               "credibility": "high"},
        # 政府・公的機関
        {"name": "金融庁",          "url": "https://www.fsa.go.jp/news/rss.xml",                             "credibility": "high"},
        {"name": "日本銀行",        "url": "https://www.boj.or.jp/rss/boj_news.xml",                         "credibility": "high"},
        {"name": "財務省",          "url": "https://www.mof.go.jp/rss/topics.xml",                           "credibility": "high"},
        {"name": "経済産業省",      "url": "https://www.meti.go.jp/rss/topics.xml",                          "credibility": "high"},
        # 海外・マクロ
        {"name": "ロイター日本語",  "url": "https://feeds.reuters.com/reuters/JPBusinessNews",               "credibility": "high"},
        {"name": "NHK国際",         "url": "https://www3.nhk.or.jp/rss/news/cat6.xml",                       "credibility": "high"},
    ],
    # 法務・行政処分・裁判系
    "legal": [
        {"name": "公正取引委員会",  "url": "https://www.jftc.go.jp/rss/index.xml",                          "credibility": "high"},
        {"name": "消費者庁",        "url": "https://www.caa.go.jp/rss/topics.xml",                           "credibility": "high"},
        {"name": "警察庁",          "url": "https://www.npa.go.jp/rss/index.xml",                            "credibility": "high"},
        {"name": "検察庁",          "url": "https://www.kensatsu.go.jp/rss/index.xml",                       "credibility": "high"},
        {"name": "法務省",          "url": "https://www.moj.go.jp/rss/topics.xml",                           "credibility": "high"},
        {"name": "裁判所",          "url": "https://www.courts.go.jp/rss/index.xml",                         "credibility": "high"},
    ],
    # 地方紙・地域ニュース（法務・行政処分の補完）
    "local": [
        # 山口県
        {"name": "周南地域ニュース",       "url": "https://www.shinshunan.co.jp/news/shunan/rss.xml",        "credibility": "medium"},
        {"name": "周南・下松・光ニュース", "url": "https://shunan-kudamatsu-hikari.goguynet.jp/feed/",       "credibility": "medium"},
        # 全国地方紙
        {"name": "北海道新聞",      "url": "https://www.hokkaido-np.co.jp/rss/news.xml",                    "credibility": "high"},
        {"name": "河北新報",        "url": "https://kahoku.news/feed/",                                      "credibility": "high"},
        {"name": "中日新聞",        "url": "https://www.chunichi.co.jp/rss/list/economics.xml",              "credibility": "high"},
        {"name": "西日本新聞",      "url": "https://www.nishinippon.co.jp/rss/economy.xml",                  "credibility": "high"},
        {"name": "南日本新聞",      "url": "https://373news.com/feed/",                                      "credibility": "medium"},
        {"name": "琉球新報",        "url": "https://ryukyushimpo.jp/rss/index.xml",                          "credibility": "high"},
        {"name": "NHK社会",         "url": "https://www3.nhk.or.jp/rss/news/cat5.xml",                      "credibility": "high"},
    ],
    "general": [
        {"name": "NHK総合",         "url": "https://www3.nhk.or.jp/rss/news/cat0.xml",                       "credibility": "high"},
        {"name": "Yahoo News",      "url": "https://news.yahoo.co.jp/rss/topics/top-picks.xml",              "credibility": "high"},
        {"name": "朝日新聞",        "url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf",              "credibility": "high"},
        {"name": "産経ニュース",    "url": "https://www.sankei.com/rss/news/flash.xml",                      "credibility": "high"},
    ],
    "science": [
        {"name": "Science Daily",   "url": "https://www.sciencedaily.com/rss/top/science.xml",               "credibility": "high"},
        {"name": "NASA",            "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",                  "credibility": "high"},
        {"name": "Nature News",     "url": "https://www.nature.com/news.rss",                                 "credibility": "high"},
    ],
    "security": [
        {"name": "IPA",             "url": "https://www.ipa.go.jp/security/rss/vuln.rdf",                    "credibility": "high"},
        {"name": "JPCERT",          "url": "https://www.jpcert.or.jp/rss/jpcert.rdf",                        "credibility": "high"},
        {"name": "Bleeping Computer", "url": "https://www.bleepingcomputer.com/feed/",                        "credibility": "high"},
    ],
    "gadget": [
        {"name": "Gizmodo JP",      "url": "https://www.gizmodo.jp/index.xml",                               "credibility": "high"},
        {"name": "Impress Watch",   "url": "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf",      "credibility": "high"},
        {"name": "マイナビニュース","url": "https://news.mynavi.jp/rss/index",                                "credibility": "high"},
        {"name": "Engadget JP",     "url": "https://japanese.engadget.com/rss.xml",                          "credibility": "high"},
    ],
    # 特許庁（各国公式）
    "patent": [
        {"name": "JPO（日本）",       "url": "https://www.jpo.go.jp/rss/index.xml",                              "credibility": "high"},
        {"name": "USPTO（米国）",     "url": "https://www.uspto.gov/rss/pressrelease.xml",                       "credibility": "high"},
        {"name": "EPO（欧州）",       "url": "https://www.epo.org/news-events/news/rss.xml",                     "credibility": "high"},
        {"name": "WIPO（国際）",      "url": "https://www.wipo.int/pressroom/en/rss.xml",                        "credibility": "high"},
        {"name": "CNIPA（中国）",     "url": "https://www.cnipa.gov.cn/rss/index.xml",                           "credibility": "high"},
        # 日本語・国内知財情報
        {"name": "J-PlatPat新着",     "url": "https://www.j-platpat.inpit.go.jp/rss/news.rss",                  "credibility": "high"},
        {"name": "WIPO日本語",        "url": "https://www.wipo.int/pressroom/ja/rss/news.rss",                   "credibility": "high"},
        {"name": "知財情報センター",  "url": "https://www.jiii.or.jp/rss/index.xml",                             "credibility": "high"},
    ],
    # 技術ブログ・コミュニティ（信頼度: medium）
    "tech_blog": [
        {"name": "はてなブックマーク技術", "url": "https://b.hatena.ne.jp/hotentry/it.rss",                  "credibility": "medium"},
        {"name": "Qiitaトレンド",   "url": "https://qiita.com/popular-items/feed",                           "credibility": "medium"},
        {"name": "Zennトレンド",    "url": "https://zenn.dev/feed",                                           "credibility": "medium"},
        {"name": "note技術",        "url": "https://note.com/hashtag/python?rss",                            "credibility": "medium"},
    ],
    # 掲示板・まとめ（信頼度: low・クロスチェック必須）
    "bbs": [
        {"name": "ハム速",          "url": "https://hamusoku.com/index.rdf",                                  "credibility": "low"},
        {"name": "ガールズちゃんねる", "url": "https://girlschannel.net/feeds/rss/",                          "credibility": "low"},
        {"name": "爆サイ",          "url": "https://bakusai.com/rss/",                                        "credibility": "low"},
        {"name": "2chニュース速報",  "url": "https://rsso.2nn.jp/rss/2ch",                                    "credibility": "low"},
    ],
}

# トピックID → RSSジャンルのマッピング
TOPIC_TO_GENRE = {
    "python_tech":  "tech",
    "ai_news":      "ai",
    "arxiv_ai":     "ai",
    "finance":      "finance",
    "security":     "security",
    "gadget":       "gadget",
    "science":      "science",
    "food":         "general",
    "local_food":   "general",
    "general":      "general",
}


# =====================================================
# 既読管理（7日間TTL）
# =====================================================
def _load_seen() -> dict:
    """既読ハッシュ → 最終確認時刻 の辞書を返す"""
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_seen(seen: dict):
    SEEN_FILE.parent.mkdir(exist_ok=True)
    # 7日以上古いエントリを削除
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    seen   = {k: v for k, v in seen.items() if v >= cutoff}
    SEEN_FILE.write_text(
        json.dumps(seen, ensure_ascii=False),
        encoding="utf-8",
    )


def _news_hash(title: str) -> str:
    """タイトル先頭50文字の MD5 先頭8桁をハッシュキーにする"""
    return hashlib.md5(title[:50].encode("utf-8", errors="ignore")).hexdigest()[:8]


# =====================================================
# RSS収集
# =====================================================
def fetch_rss(source: dict, max_items: int = 5) -> list:
    """単一RSSフィードを取得する。失敗時は空リストを返す。"""
    credibility = source.get("credibility", "medium")
    cred_score  = CREDIBILITY_LEVELS[credibility]["score"]
    try:
        feed  = feedparser.parse(source["url"])
        items = []
        for entry in feed.entries[:max_items]:
            title   = entry.get("title", "").strip()
            summary = re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:300].strip()
            link    = entry.get("link", "")
            pub     = entry.get("published", entry.get("updated", ""))
            if title and len(title) > 3:
                items.append({
                    "source":           source["name"],
                    "title":            title,
                    "summary":          summary,
                    "link":             link,
                    "pub":              pub,
                    "hash":             _news_hash(title),
                    "credibility":      credibility,
                    "credibility_score": cred_score,
                    "credibility_label": CREDIBILITY_LEVELS[credibility]["tag"],
                    "cross_checked":    False,
                    "matched_sources":  [],
                })
        return items
    except Exception:
        return []


def cross_check_credibility(item: dict, high_cred_news: list) -> dict:
    """
    低信頼ソースの情報を高信頼ソースと照合して信頼度スコアを更新する。
    日本語2文字以上の単語を2語以上共有していれば「裏付けあり」と判定。
    """
    title    = item.get("title", "")
    keywords = set(re.findall(r'[ぁ-んァ-ヶー一-龥]{2,}', title))
    if not keywords:
        # 英語キーワードで照合
        keywords = set(re.findall(r'[A-Za-z]{4,}', title))

    match_count     = 0
    matched_sources = []
    for news in high_cred_news:
        news_kw = set(re.findall(r'[ぁ-んァ-ヶー一-龥]{2,}', news.get("title", "")))
        if not news_kw:
            news_kw = set(re.findall(r'[A-Za-z]{4,}', news.get("title", "")))
        overlap = keywords & news_kw
        if len(overlap) >= 2:
            match_count += 1
            matched_sources.append(news.get("source", ""))

    base_score = item.get("credibility_score", 0.3)
    if match_count > 0:
        boosted = min(0.85, base_score + match_count * 0.2)
        src_str = "、".join(matched_sources[:2])
        item.update({
            "cross_checked":     True,
            "matched_sources":   matched_sources[:3],
            "credibility_score": boosted,
            "credibility_label": f"✅ 裏付けあり（{src_str}）",
        })
    else:
        item.update({
            "cross_checked":     False,
            "matched_sources":   [],
            "credibility_label": "💬 噂レベル（裏付けなし）",
        })
    return item


def collect_news(
    genres: list = None,
    max_per_source: int = 5,
    skip_seen: bool = True,
    cross_check: bool = True,
) -> dict:
    """
    複数ジャンルのニュースを収集する。

    Args:
        genres:         収集するジャンルリスト（Noneで全ジャンル）
        max_per_source: ソースごとの最大記事数
        skip_seen:      既読をスキップするか
        cross_check:    低信頼ソースを高信頼ソースで照合するか

    Returns:
        {ジャンル: [ニュースリスト]}
    """
    if genres is None:
        genres = list(RSS_SOURCES.keys())

    seen_db    = _load_seen() if skip_seen else {}
    seen_keys  = set(seen_db.keys())
    results    = {}
    new_hashes: dict = {}

    for genre in genres:
        sources = RSS_SOURCES.get(genre, [])
        items   = []
        ok_src  = 0

        for source in sources:
            fetched = fetch_rss(source, max_per_source)
            added   = 0
            for item in fetched:
                h = item["hash"]
                if h not in seen_keys:
                    items.append(item)
                    new_hashes[h] = datetime.now().isoformat()
                    added += 1
            if fetched:
                ok_src += 1

        results[genre] = items
        print(f"  [{genre:10s}] {len(items):3d}件  ({ok_src}/{len(sources)} ソース)")

    # クロスチェック: 低信頼ソースを高信頼ソースと照合
    if cross_check:
        high_cred_news = [
            item
            for genre_items in results.values()
            for item in genre_items
            if item.get("credibility") == "high"
        ]
        for genre in results:
            checked = []
            for item in results[genre]:
                if item.get("credibility") == "low":
                    item = cross_check_credibility(item, high_cred_news)
                checked.append(item)
            results[genre] = checked

    # 既読を更新して保存
    seen_db.update(new_hashes)
    _save_seen(seen_db)

    # キャッシュ保存
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = NEWS_DIR / f"{stamp}_news.json"
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total = sum(len(v) for v in results.values())
    print(f"  💾 保存: {out_path.name}  (合計 {total}件)")
    return results


def collect_all_news(max_per_source: int = 10) -> dict:
    """
    全ジャンル（legal・local 含む）のニュースを収集する。
    local は RSS_SOURCES["local"] に加えて local_news_collector
    （Google News RSS + 号外NET + 登録済みサイト）も統合する。
    genre="local" の記事は extract_legal_from_local_news() にも転送して
    地域の犯罪・行政処分情報を法務データに補完する。

    Returns:
        {ジャンル: [ニュースリスト]}
    """
    results = collect_news(
        genres=list(RSS_SOURCES.keys()),
        max_per_source=max_per_source,
        skip_seen=True,
        cross_check=True,
    )

    # ローカルニュース拡張（Google News + 号外NET + 登録済みサイト）
    try:
        from local_news_collector import collect_local_news
        extended_local = collect_local_news()
        if extended_local:
            existing_urls = {
                item.get("url", "") or item.get("title", "")
                for item in results.get("local", [])
            }
            added = 0
            for item in extended_local:
                key = item.get("url", "") or item.get("title", "")
                if key and key not in existing_urls:
                    results.setdefault("local", []).append(item)
                    existing_urls.add(key)
                    added += 1
            if added:
                print(f"  🗾 ローカルニュース追補: +{added}件")
    except Exception as e:
        print(f"  ⚠️ ローカルニュース拡張スキップ: {e}")

    # ローカルニュースから法務情報を抽出して "legal" に追記
    all_local = results.get("local", [])
    if all_local:
        try:
            from legal_collector import extract_legal_from_local_news
            legal_from_local = extract_legal_from_local_news(all_local)
            if legal_from_local:
                results.setdefault("legal", [])
                existing_titles = {
                    item.get("title", "")[:40] for item in results["legal"]
                }
                added_legal = 0
                for item in legal_from_local:
                    if item.get("title", "")[:40] not in existing_titles:
                        results["legal"].append(item)
                        added_legal += 1
                if added_legal:
                    print(f"  ⚖️ 地方紙から法務情報を追補: {added_legal}件")
        except Exception as e:
            print(f"  ⚠️ 地方紙→法務転送スキップ: {e}")

    return results


def get_latest_news(genre: str, max_items: int = 10) -> list:
    """
    最新キャッシュ（1時間以内）からジャンル別ニュースを返す。
    キャッシュがない・古い場合はリアルタイム収集する。
    """
    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    cached = sorted(NEWS_DIR.glob("*_news.json"), reverse=True)
    if cached:
        age_secs = (datetime.now() - datetime.fromtimestamp(
            cached[0].stat().st_mtime
        )).total_seconds()
        if age_secs < 3600:  # 1時間以内
            try:
                data = json.loads(cached[0].read_text(encoding="utf-8"))
                items = data.get(genre, [])
                if items:
                    return items[:max_items]
            except Exception:
                pass

    # キャッシュなし or 古い → リアルタイム収集
    results = collect_news(genres=[genre], skip_seen=False)
    return results.get(genre, [])[:max_items]


def format_news_for_article(
    news_items: list,
    max_items: int = 10,
    include_low_credibility: bool = True,
) -> str:
    """ニュースを信頼度別に整理して記事挿入用 Markdown テキストに変換する"""
    if not news_items:
        return ""

    high   = [n for n in news_items if n.get("credibility_score", 0.6) >= 0.7]
    medium = [n for n in news_items if 0.4 <= n.get("credibility_score", 0.6) < 0.7]
    low    = [n for n in news_items if n.get("credibility_score", 0.3) < 0.4]
    lines  = []

    if high:
        lines.append("### 📰 確認済みニュース")
        for item in high[:max_items]:
            lines.append(f"- **[{item['source']}]** {item['title']}")
            if item.get("summary"):
                lines.append(f"  {item['summary'][:100]}")
        lines.append("")

    if medium:
        lines.append("### 📝 ブログ・コミュニティ情報")
        for item in medium[:3]:
            lines.append(f"- [{item['source']}] {item['title']}")
        lines.append("")

    if low and include_low_credibility:
        backed = [n for n in low if n.get("cross_checked")]
        rumors = [n for n in low if not n.get("cross_checked")]

        if backed:
            lines.append("### 💬 話題になっている情報（要確認）")
            lines.append("> ⚠️ 以下は掲示板・まとめサイト由来の情報です。")
            lines.append("> 信頼できるニュースソースと照合済みのもののみ掲載しています。")
            lines.append("")
            for item in backed[:3]:
                lines.append(
                    f"- {item['title']} "
                    f"（{item.get('credibility_label', '')}）"
                )
            lines.append("")

        if rumors:
            lines.append("### 🔍 噂・未確認情報（参考程度）")
            lines.append("> ⚠️ 以下は裏付けが取れていない情報です。参考程度にご覧ください。")
            lines.append("")
            for item in rumors[:2]:
                lines.append(f"- {item['title']} （出典: {item['source']}）")
            lines.append("")

    return "\n".join(lines)


def show_stats():
    """収集統計を表示する"""
    seen_db = _load_seen()
    cached  = sorted(NEWS_DIR.glob("*_news.json"), reverse=True) if NEWS_DIR.exists() else []
    print(f"\n## ニュース収集統計")
    print(f"既読管理エントリ数: {len(seen_db)}件")
    print(f"キャッシュファイル数: {len(cached)}件")
    if cached:
        latest  = cached[0]
        age_min = int((datetime.now() - datetime.fromtimestamp(
            latest.stat().st_mtime
        )).total_seconds() // 60)
        print(f"最新キャッシュ: {latest.name} ({age_min}分前)")
        data = json.loads(latest.read_text(encoding="utf-8"))
        print("ジャンル別件数:")
        for genre, items in data.items():
            print(f"  {genre:10s}: {len(items)}件")


def filter_new_patent_items(patent_items: list) -> list:
    """
    前日までの特許ニュースと比較して新規情報のみ返す。
    legal_collector の filter_new_legal_items と同じ設計。
    本日分は knowledge/patent/ に保存して次回の重複排除に使用する。
    """
    PATENT_DIR = AGENT_ROOT / "knowledge" / "patent"
    PATENT_DIR.mkdir(parents=True, exist_ok=True)

    PROGRESS_KEYWORDS = ["登録", "査定", "審決", "判決", "異議", "無効", "侵害", "和解"]

    # 直近5件の特許キャッシュからタイトルを収集
    prev_titles = set()
    for f in sorted(PATENT_DIR.glob("*_patent.json"), reverse=True)[:5]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for item in data:
                prev_titles.add(item.get("title", "")[:30])
        except Exception:
            continue

    # 新規・進展のある情報のみフィルタリング
    new_items = []
    for item in patent_items:
        title_key = item.get("title", "")[:30]
        if title_key not in prev_titles:
            new_items.append(item)
        elif any(kw in item.get("title", "") for kw in PROGRESS_KEYWORDS):
            item = dict(item)
            item["note"] = "進展あり"
            new_items.append(item)

    print(f"  📋 特許: 全{len(patent_items)}件 → 新規{len(new_items)}件（前日重複排除）")

    # 本日分を保存（次回の重複排除に使用）
    if patent_items:
        date_str  = datetime.now().strftime("%Y-%m-%d_%H%M")
        save_path = PATENT_DIR / f"{date_str}_patent.json"
        save_path.write_text(
            json.dumps(patent_items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return new_items


def summarize_patent_news(patent_items: list, llm_func=None) -> str:
    """
    特許ニュースをLLMで要約して投資・経済的影響を分析する。
    RSS取得失敗等で patent_items が空の場合は空文字を返す。
    """
    if not patent_items:
        return ""

    titles = "\n".join(
        f"・{item['title'][:80]}"
        for item in patent_items[:10]
        if item.get("title")
    )
    if not titles:
        return ""

    prompt = (
        "以下の特許・知財ニュースを読んで、"
        "経済・投資への影響を50文字以内で要約してください。\n"
        "影響が小さい場合は「特筆すべき特許動向はありません」と回答してください。\n\n"
        f"特許ニュース:\n{titles}\n\n"
        "要約（50文字以内）:"
    )

    try:
        from llm import ask_plain
        return ask_plain(prompt)
    except Exception:
        return ""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="汎用ニュース収集システム")
    parser.add_argument("--genre", help="収集するジャンル（tech/ai/finance/general/science/security/gadget）")
    parser.add_argument("--stats", action="store_true", help="統計表示")
    parser.add_argument("--no-skip", action="store_true", help="既読をスキップしない")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        genres = [args.genre] if args.genre else None
        print(f"\n{'='*50}")
        print(f"  ニュース収集開始: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  ジャンル: {genres or '全ジャンル'}")
        print(f"{'='*50}\n")
        results  = collect_news(genres=genres, skip_seen=not args.no_skip)
        total    = sum(len(v) for v in results.values())
        print(f"\n完了: 合計 {total}件")
