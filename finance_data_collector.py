"""
投資系記事用のデータ収集モジュール。
収集するデータ:
- 日経平均・市場概況
- 値上がり・値下がりランキング
- 株主優待・株式分割の適時開示
- 配当情報
※ 投資助言は行わない。データの収集・整理・紹介のみ。
"""
import re
import json
from datetime import datetime
from pathlib import Path

import requests
import feedparser

AGENT_ROOT  = Path(__file__).parent
FINANCE_DIR = AGENT_ROOT / "knowledge" / "finance"
HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}


# =====================================================
# 市場概況
# =====================================================
def fetch_market_summary() -> dict:
    """
    日経平均・市場概況を取得する。
    Yahoo Finance Japan から取得。
    """
    try:
        # Yahoo Finance US API (^N225) - JSON形式で安定して取得可能
        api_url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EN225"
            "?interval=1d&range=1d"
        )
        api_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
            "Accept": "application/json",
        }
        resp = requests.get(api_url, headers=api_headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        meta  = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice", "取得中")
        prev  = meta.get("previousClose", "N/A")
        change = ""
        if isinstance(price, (int, float)) and isinstance(prev, (int, float)) and prev:
            diff   = price - prev
            pct    = diff / prev * 100
            change = f"{'+' if diff >= 0 else ''}{diff:,.2f} ({pct:+.2f}%)"
        return {
            "date":         datetime.now().strftime("%Y-%m-%d"),
            "nikkei_price": f"{price:,.2f}" if isinstance(price, float) else str(price),
            "nikkei_change": change,
            "source":       "Yahoo Finance (^N225)",
        }
    except Exception as e:
        return {"error": str(e), "date": datetime.now().strftime("%Y-%m-%d")}


# =====================================================
# 適時開示（株主優待・株式分割）
# =====================================================
def fetch_tdnet_news(category: str = "株主優待") -> list:
    """
    TDnet（適時開示情報）から情報を取得する。
    kabutan経由で取得。
    category: "株主優待" or "株式分割" or "配当"
    """
    try:
        url  = f"https://kabutan.jp/disclosures/?category={requests.utils.quote(category)}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        # 開示情報を抽出（簡易パース）
        pattern = r'<td[^>]*>([^<]{2,50})</td>'
        items   = re.findall(pattern, resp.text)
        # クリーニング
        cleaned = []
        for item in items:
            item = item.strip()
            if len(item) > 4 and not item.startswith('<'):
                cleaned.append(item)
        return cleaned[:30]
    except Exception as e:
        return [f"取得エラー: {e}"]


# =====================================================
# ランキング
# =====================================================
def fetch_ranking(rank_type: str = "up") -> list:
    """
    値上がり・値下がりランキングを取得する。
    ソース1: minkabu → ソース2: kabutan の順にフォールバック。
    """
    # ソース1: minkabu
    try:
        url = "https://minkabu.jp/ranking/increase_rate" if rank_type == "up" else "https://minkabu.jp/ranking/decrease_rate"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        names   = re.findall(
            r'class="[^"]*name[^"]*"[^>]*>\s*<[^>]+>([^<]{3,20})</[^>]+>',
            resp.text
        )
        changes = re.findall(r'[+\-]?\d+\.\d+%', resp.text)
        if names and changes:
            results = [
                f"{i+1}. {n.strip()} ({changes[i] if i < len(changes) else 'N/A'})"
                for i, n in enumerate(names[:10])
            ]
            if results:
                return results
    except Exception as e:
        print(f"  ⚠️ minkabu取得失敗: {e}")

    # ソース2: kabutan
    try:
        url = "https://kabutan.jp/warning/?mode=2_1" if rank_type == "up" else "https://kabutan.jp/warning/?mode=2_2"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        rows    = re.findall(r'<tr[^>]*>(.*?)</tr>', resp.text, re.DOTALL)
        results = []
        for row in rows[1:30]:  # 多めに走査してフィルター後に10件確保
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            cells = [c for c in cells if c and len(c) > 1]
            if len(cells) >= 2:
                name = cells[0]
                # 数値・パーセント・記号のみの行をスキップ（日経平均サマリー等）
                if re.match(r'^[+\-]?[\d,，\.%]+$', name):
                    continue
                if len(name) < 2 or len(name) > 20:
                    continue
                # 変動率は後続セルから探す（cells[1]が市場区分の場合はcells[2]以降）
                change = "N/A"
                for c in cells[1:]:
                    if re.search(r'[+\-]?\d+\.\d+%', c):
                        change = c
                        break
                if change == "N/A" and len(cells) > 1:
                    change = cells[1]
                results.append(f"{len(results)+1}. {name} ({change})")
            if len(results) >= 10:
                break
        if results:
            return results
    except Exception as e:
        print(f"  ⚠️ kabutan取得失敗: {e}")

    return ["ランキングデータを取得できませんでした（市場休場または接続エラー）"]


# =====================================================
# 企業名ルックアップ
# =====================================================
def lookup_company_name(code: str) -> str:
    """
    銘柄コードから企業名を取得する。
    kabutan の銘柄ページから取得。失敗時はコードをそのまま返す。
    """
    try:
        # 英字付きコード（533A等）はそのまま使用。数字のみ抽出しない
        query_code = code.strip()
        if not query_code:
            return code
        url  = f"https://kabutan.jp/stock/?code={query_code}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        # <h1> タグから企業名を抽出（例: "農中ＳＰ５Ｕ(533A) 基本情報"）
        h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', resp.text, re.DOTALL)
        for h1 in h1s:
            # HTML タグを除去
            text = re.sub(r'<[^>]+>', '', h1).strip()
            # "（コード）基本情報" の部分を除去して企業名だけ取り出す
            text = re.sub(r'\s*\([^)]+\)\s*基本情報.*$', '', text).strip()
            text = re.sub(r'\s*基本情報.*$', '', text).strip()
            if text and len(text) >= 2 and not re.match(r'^[\d\s]+$', text):
                return text
    except Exception:
        pass
    return code


def fetch_ranking_with_names(rank_type: str = "up") -> list:
    """企業名付きランキングを取得する（銘柄コードがある場合は企業名に変換）"""
    raw = fetch_ranking(rank_type)
    results = []
    for item in raw:
        # "1. 533A (+21.38%)" パターンから銘柄コードを抽出
        m = re.match(r'(\d+)\.\s*([^\s(]+)\s*\(([^)]+)\)', item)
        if m:
            rank   = m.group(1)
            code   = m.group(2)
            change = m.group(3)
            # 銘柄コードっぽい場合（4桁数字+英字）は企業名を取得
            if re.match(r'^\d{3,4}[A-Z]?$', code):
                name = lookup_company_name(code)
                results.append(f"{rank}. {name} ({change})")
            else:
                results.append(item)
        else:
            results.append(item)
    return results


# =====================================================
# ニュース収集
# =====================================================
RSS_FEEDS = {
    "NHK経済":  "https://www3.nhk.or.jp/rss/news/cat5.xml",   # 63件・安定
    "東洋経済": "https://toyokeizai.net/list/feed/rss",        # 20件
    "Yahoo金融": "https://news.yahoo.co.jp/rss/topics/business.xml",  # 8件
}


def fetch_financial_news() -> list:
    """
    複数RSSソースから金融ニュースを収集する。
    """
    all_news = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries[:10]:
                title   = entry.get("title", "").strip()
                summary = re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:200].strip()
                link    = entry.get("link", "")
                pub     = entry.get("published", "")
                if title:
                    all_news.append({
                        "source":  source,
                        "title":   title,
                        "summary": summary,
                        "link":    link,
                        "pub":     pub,
                    })
                    count += 1
            print(f"  ✅ {source}: {count}件取得")
        except Exception as e:
            print(f"  ⚠️ {source}: {e}")

    # タイトル先頭30文字で重複除去
    seen, unique = set(), []
    for news in all_news:
        key = news["title"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(news)

    return unique[:30]


def fetch_market_news_realtime() -> list:
    """
    Yahoo Finance Japan のウェブページからリアルタイムニュースを収集する。
    NHK・東洋経済は RSS で取得済みのため対象外。
    """
    news = []

    # Yahoo Finance Japan（ウェブスクレイプ）
    try:
        url  = "https://finance.yahoo.co.jp/news/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        # <a> タグの class="title" か data 属性付きリンクテキストを抽出
        titles = re.findall(
            r'<a[^>]*class="[^"]*title[^"]*"[^>]*>([^<]{5,80})</a>',
            resp.text,
        )
        # フォールバック: li 内のリンクテキスト
        if not titles:
            titles = re.findall(
                r'<li[^>]*>\s*<a[^>]+>([^<]{8,80})</a>',
                resp.text,
            )
        # ナビ・UI テキストを除外（10文字以上、サイト名除外）
        _skip = {"Yahoo", "JAPAN", "プライバシー", "利用規約", "ヘルプ",
                 "カードローン", "ログイン", "新規登録", "サービス", "一覧"}
        for t in titles[:20]:
            t = t.strip()
            if len(t) < 10:
                continue
            if any(s in t for s in _skip):
                continue
            news.append({"source": "Yahoo Finance", "title": t})
        print(f"  ✅ Yahoo Finance(web): {len(news)}件取得")
    except Exception as e:
        print(f"  ⚠️ Yahoo Finance: {e}")

    return news


def _format_news_for_article(news_list: list) -> str:
    """ニュースリストを記事用のMarkdownテキストに変換する"""
    if not news_list:
        return "ニュースデータなし"
    by_source: dict = {}
    for n in news_list:
        src = n.get("source", "その他")
        by_source.setdefault(src, []).append(n)
    lines = []
    for src, items in by_source.items():
        lines.append(f"\n### {src}")
        for n in items[:5]:
            title = n.get("title", "")
            lines.append(f"- {title}")
    return "\n".join(lines)


# =====================================================
# データ保存
# =====================================================
def collect_finance_data() -> dict:
    """全ての投資データを収集してまとめて返す"""
    print("  📈 投資データ収集中...")

    from disclosure_analyzer import analyze_today_disclosures, format_for_article

    data = {
        "date":              datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market_summary":    fetch_market_summary(),
        "up_ranking":        fetch_ranking_with_names("up"),
        "down_ranking":      fetch_ranking_with_names("down"),
        "disclosure_results": analyze_today_disclosures(),
    }
    data["disclosure_text"] = format_for_article(data["disclosure_results"])

    # ニュース収集（複数ソース）
    print("  📰 ニュース収集中...")
    rss_news      = fetch_financial_news()
    realtime_news = fetch_market_news_realtime()
    data["news"]      = rss_news + realtime_news
    data["news_text"] = _format_news_for_article(data["news"])
    print(f"  📰 合計 {len(data['news'])} 件のニュース取得")

    # マクロ経済データ収集
    try:
        from macro_data_collector import collect_macro_data, format_macro_for_article
        macro_data         = collect_macro_data()
        data["macro"]      = macro_data
        data["macro_text"] = format_macro_for_article(macro_data)
    except Exception as e:
        print(f"  ⚠️ マクロデータ取得失敗: {e}")
        data["macro"]      = {}
        data["macro_text"] = ""

    # 保存（日時付きファイル名で重複しない）
    FINANCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = FINANCE_DIR / f"{stamp}_finance_data.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  💾 保存: {out_path.name}")
    return data
