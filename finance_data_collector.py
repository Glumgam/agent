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
            "?interval=1d&range=2d"
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
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose", "N/A")
        change = ""
        if isinstance(price, (int, float)) and isinstance(prev, (int, float)) and prev:
            diff   = price - prev
            pct    = diff / prev * 100
            change = f"{'+' if diff >= 0 else ''}{diff:,.2f} ({pct:+.2f}%)"
        return {
            "date":          datetime.now().strftime("%Y-%m-%d"),
            "nikkei_price":  f"{price:,.2f}" if isinstance(price, float) else str(price),
            "nikkei_change": change,
            "nikkei_prev":   f"{prev:,.2f}" if isinstance(prev, float) else str(prev),
            "source":        "Yahoo Finance (^N225)",
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
    ソース1: Yahoo Finance Japan → ソース2: kabutan の順にフォールバック。
    """
    # ソース1: Yahoo Finance Japan
    try:
        url = (
            "https://finance.yahoo.co.jp/stocks/ranking/up"
            if rank_type == "up"
            else "https://finance.yahoo.co.jp/stocks/ranking/down"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        rows    = re.findall(r'<tr[^>]*>(.*?)</tr>', resp.text, re.DOTALL)
        results = []
        for row in rows[:30]:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            cells = [c for c in cells if c]
            if not cells:
                continue
            raw_name = cells[0]
            # セル1: "企業名コード東証XXX掲示板" から企業名だけ抽出
            # 例: "(株)アスタリスク6522東証GRT掲示板" → "(株)アスタリスク"
            # 例: "インフォメティス(株)281A東証GRT掲示板" → "インフォメティス(株)"
            m = re.match(r'^(.+?)\d{3,4}[A-Z]?(?:東証|名証|札証|福証)', raw_name)
            name = m.group(1).strip() if m else raw_name
            # HTMLエンティティを復元
            name = name.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            # 短すぎ・長すぎ・数字のみはスキップ
            if len(name) < 2 or len(name) > 30:
                continue
            if re.match(r'^[\d,\.%+\-\s]+$', name):
                continue
            # 変動率: セル3に "+金額+XX.XX%" 形式 → XX.XX% を取り出す
            change = "N/A"
            for cell in cells:
                pcts = re.findall(r'([+\-]\d+\.\d+)%', cell)
                if pcts:
                    change = pcts[-1] + "%"  # 末尾（パーセント変化率）
                    break
            results.append(f"{len(results)+1}. {name} ({change})")
            if len(results) >= 10:
                break
        if results:
            print(f"  ✅ Yahoo Finance ランキング({rank_type}): {len(results)}件")
            return results
    except Exception as e:
        print(f"  ⚠️ Yahoo Finance ランキング取得失敗: {e}")

    # ソース2: kabutan
    try:
        url = (
            "https://kabutan.jp/warning/?mode=2_1"
            if rank_type == "up"
            else "https://kabutan.jp/warning/?mode=2_2"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        rows    = re.findall(r'<tr[^>]*>(.*?)</tr>', resp.text, re.DOTALL)
        results = []
        for row in rows[1:30]:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            cells = [c for c in cells if c and len(c) > 1]
            if len(cells) < 2:
                continue
            name = cells[0]
            if re.match(r'^[+\-]?[\d,，\.%]+$', name):
                continue
            if len(name) < 2 or len(name) > 25:
                continue
            change = "N/A"
            for c in cells[1:]:
                if re.search(r'[+\-]?\d+\.\d+%', c):
                    change = re.search(r'[+\-]?\d+\.\d+%', c).group()
                    break
            results.append(f"{len(results)+1}. {name} ({change})")
            if len(results) >= 10:
                break
        if results:
            print(f"  ✅ kabutan ランキング({rank_type}): {len(results)}件")
            return results
    except Exception as e:
        print(f"  ⚠️ kabutan ランキング取得失敗: {e}")

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

    # SNSデータ収集（ランキング上位銘柄＋高信頼ニュースでクロスチェック）
    try:
        from social_collector import collect_social_data, format_social_for_article
        # ランキングから銘柄コードを抽出
        top_codes = []
        for item in data.get("up_ranking", [])[:3]:
            m = re.search(r'\((\d{4})\)', item)
            if m:
                top_codes.append(m.group(1))
        high_cred = [
            n for n in data.get("news", [])
            if n.get("credibility_score", 0) >= 0.7
        ]
        social_data         = collect_social_data(top_codes, high_cred)
        data["social"]      = social_data
        data["social_text"] = format_social_for_article(social_data)
    except Exception as e:
        print(f"  ⚠️ SNSデータ取得失敗: {e}")
        data["social"]      = {}
        data["social_text"] = ""

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

    # 先物データ収集
    print("  📊 先物データ収集中...")
    FUTURES_SYMBOLS = {
        "日経225先物(大阪)": "^N225F",
        "CME日経先物":       "NIY=F",
        "TOPIX先物":         "TOPIXF.T",
    }
    futures = {}
    for name, symbol in FUTURES_SYMBOLS.items():
        try:
            url  = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                    f"?range=1d&interval=1m")
            resp = requests.get(url, headers=HEADERS, timeout=10)
            meta = resp.json()["chart"]["result"][0]["meta"]
            price   = meta.get("regularMarketPrice", 0)
            prev    = meta.get("previousClose", 1) or 1
            chg_pct = round((price - prev) / prev * 100, 2)
            futures[name] = {"price": price, "change_pct": chg_pct}
            print(f"  ✅ {name}: {price} ({chg_pct:+.2f}%)")
        except Exception as e:
            print(f"  ⚠️ {name} 取得失敗: {e}")
    data["futures"] = futures

    # 求人データ収集（ランキング上位企業の採用動向）
    try:
        from job_analyzer import collect_job_data, format_jobs_for_article
        from stock_linker import COMPANY_CODE_MAP
        # ランキング上位銘柄コード → 企業名に変換
        code_to_company = {v: k for k, v in COMPANY_CODE_MAP.items()}
        top_companies = []
        for item in data.get("up_ranking", [])[:3]:
            m = re.search(r'\((\d{4})\)', item)
            if m and m.group(1) in code_to_company:
                top_companies.append(code_to_company[m.group(1)])
        job_data         = collect_job_data(target_companies=top_companies or None)
        data["jobs"]     = job_data
        data["job_text"] = format_jobs_for_article(job_data)
    except Exception as e:
        print(f"  ⚠️ 求人データ取得失敗: {e}")
        data["jobs"]     = {}
        data["job_text"] = ""

    # 法務・行政処分データ収集
    try:
        from legal_collector import collect_legal_data, format_legal_for_article
        legal_data         = collect_legal_data(top_companies or None)
        data["legal"]      = legal_data
        data["legal_text"] = format_legal_for_article(legal_data)
    except Exception as e:
        print(f"  ⚠️ 法務データ取得失敗: {e}")
        data["legal"]      = {}
        data["legal_text"] = ""

    # 相関分析（ランキング上位銘柄）
    try:
        from correlation_analyzer import analyze_stock_correlations, format_correlations_for_article
        if top_codes:
            corr_results         = analyze_stock_correlations(top_codes[:3], days=60)
            data["correlations"] = corr_results
            data["corr_text"]    = format_correlations_for_article(corr_results)
            # トラッキングテキスト
            from correlation_tracker import format_tracking_for_article
            tracking_list        = corr_results.get("_tracking_summary", [])
            data["tracking_text"] = format_tracking_for_article(tracking_list)
        else:
            data["corr_text"]     = ""
            data["tracking_text"] = ""
    except Exception as e:
        print(f"  ⚠️ 相関分析失敗: {e}")
        data["corr_text"]     = ""
        data["tracking_text"] = ""

    # ローカルニュースから法務・経済関連情報を取得
    try:
        from local_news_collector import collect_local_news
        from legal_collector import extract_legal_from_local_news
        print("  🗾 ローカルニュース収集中...")
        local_items = collect_local_news()
        # 法務関連をlegalに追加
        legal_from_local = extract_legal_from_local_news(local_items)
        if legal_from_local:
            existing_legal = data.get("legal", {})
            existing_high  = existing_legal.get("high", [])
            existing_high.extend(legal_from_local)
            data["legal"]["high"] = existing_high
            print(f"  ⚖️ ローカル法務情報追加: {len(legal_from_local)}件")
        # 一般ニュースをnewsに追加
        existing_news = data.get("news", [])
        # 重複除去（URL基準）
        existing_urls = {n.get("url", "") for n in existing_news}
        new_local = [
            item for item in local_items
            if item.get("url", "") not in existing_urls
        ]
        data["news"] = existing_news + new_local[:20]  # 最大20件追加
        print(f"  🗾 ローカルニュース追加: {len(new_local[:20])}件")
    except Exception as e:
        print(f"  ⚠️ ローカルニュース収集スキップ: {e}")

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


# =====================================================
# コンテキスト圧縮（LLM向け・情報密度最適化）
# =====================================================
def _estimate_market_drivers(data: dict) -> str:
    """
    コンテキストから市場の上昇・下落の主因候補を推定する。
    架空補完を防ぐため、データにある情報のみを使う。
    """
    drivers = []
    macro = data.get("macro", {})
    us    = macro.get("us_stocks", {})
    comm  = macro.get("commodities", {})
    forex = macro.get("forex", {})

    sp_chg = us.get("S&P500", {}).get("change_pct")
    if isinstance(sp_chg, float):
        if sp_chg > 0.5:
            drivers.append(f"米国株上昇（S&P500 {sp_chg:+.1f}%）→ リスクオン傾向")
        elif sp_chg < -0.5:
            drivers.append(f"米国株下落（S&P500 {sp_chg:+.1f}%）→ リスクオフ懸念")

    vix = us.get("VIX", {}).get("price")
    if isinstance(vix, float):
        if vix < 20:
            drivers.append(f"VIX低水準（{vix}）→ 市場の不安感が低い")
        elif vix > 25:
            drivers.append(f"VIX高水準（{vix}）→ 市場の不安感が継続")

    wti_chg = comm.get("WTI原油", {}).get("change_pct")
    if isinstance(wti_chg, float):
        if wti_chg < -3:
            drivers.append(f"原油急落（{wti_chg:+.1f}%）→ エネルギーコスト低下")
        elif wti_chg > 3:
            drivers.append(f"原油急騰（{wti_chg:+.1f}%）→ エネルギーコスト上昇")

    usd_change = forex.get("USD/JPY", {}).get("change_pct")
    if isinstance(usd_change, float):
        if usd_change > 0.5:
            drivers.append(f"円安進行（USD/JPY {usd_change:+.1f}%）→ 輸出株に有利")
        elif usd_change < -0.5:
            drivers.append(f"円高進行（USD/JPY {usd_change:+.1f}%）→ 輸出株に不利")

    if not drivers:
        drivers.append("主因は複合的な要因と推測（コンテキストに明確な材料なし）")

    return "\n".join(f"・{d}" for d in drivers)


def compress_finance_context(data: dict) -> str:
    """
    投資データを意味単位で圧縮してLLM向けコンテキストを生成する。
    目標: 4000〜5000文字（情報密度優先）
    セクション順（LLMは前半を重視するため重要度降順）:
    [重要:最優先]   市況データ
    [重要:企業影響] マクロ環境
    [重要:最優先]   適時開示サマリー
    [中:参考]       相関分析の解釈
    [重要:企業影響] 法務リスク
    [中:参考]       ニューストピック要約
    [補助:傾向]     求人トレンド
    [補助:傾向]     SNS感情傾向
    """
    from llm import ask_plain
    sections = []
    date_str = data.get("date", "")

    # =====================================================
    # 1. [重要:最優先] 市況データ
    # =====================================================
    market        = data.get("market_summary", {})
    nikkei        = market.get("nikkei_price", "N/A")
    nikkei_change = market.get("nikkei_change", "")
    up_top3       = data.get("up_ranking", [])[:3]
    down_top3     = data.get("down_ranking", [])[:3]
    sections.append(
        f"[重要:最優先] 本日の市況（{date_str}）\n"
        f"日経平均: {nikkei}円 前日比: {nikkei_change if nikkei_change else '取得中'}\n"
        f"値上がり上位: {' / '.join(up_top3)}\n"
        f"値下がり上位: {' / '.join(down_top3)}"
    )

    # =====================================================
    # 1.5 [重要:先物] 日経先物（朝の記事で特に重要）
    # =====================================================
    futures = data.get("futures", {})
    if futures:
        lines = [
            f"{k}: {v['price']} ({v['change_pct']:+.2f}%)"
            for k, v in futures.items() if v.get("price")
        ]
        if lines:
            sections.append("[重要:先物] 本日の日経先物\n" + "\n".join(lines))

    # =====================================================
    # 2. [重要:企業影響] マクロ環境（数値のみ）
    # =====================================================
    macro   = data.get("macro", {})
    forex   = macro.get("forex", {})
    us      = macro.get("us_stocks", {})
    comm    = macro.get("commodities", {})
    usd_jpy  = forex.get("USD/JPY", {}).get("price", "N/A")
    sp500    = us.get("S&P500", {}).get("price", "N/A")
    sp_chg   = us.get("S&P500", {}).get("change_pct", "N/A")
    vix_val  = us.get("VIX", {}).get("price", "N/A")
    vix_chg  = us.get("VIX", {}).get("change_pct")
    wti      = comm.get("WTI原油", {}).get("price", "N/A")
    wti_chg  = comm.get("WTI原油", {}).get("change_pct", "N/A")
    gold_p   = comm.get("金", {}).get("price", "N/A")
    gold_chg = comm.get("金", {}).get("change_pct")
    sp_chg_str  = f"{sp_chg:+.1f}%" if isinstance(sp_chg, float) else str(sp_chg)
    wti_chg_str = f"{wti_chg:+.1f}%" if isinstance(wti_chg, float) else str(wti_chg)
    # VIX: 変動率と方向性を【】で明示（記事の誤記防止）
    if isinstance(vix_val, float) and isinstance(vix_chg, float):
        if vix_chg < -3:
            vix_note = (
                f"{vix_val}({vix_chg:+.1f}%) "
                f"【VIXは下落=恐怖感低下=市場は安定方向】"
            )
        elif vix_chg > 3:
            vix_note = (
                f"{vix_val}({vix_chg:+.1f}%) "
                f"【VIXは上昇=恐怖感上昇=市場は不安定方向】"
                f"【記事でVIXが「低下」「緩和」と書くのは誤り】"
            )
        else:
            vix_note = f"{vix_val}({vix_chg:+.1f}%→高水準維持)" if isinstance(vix_val, float) and vix_val > 20 else f"{vix_val}({vix_chg:+.1f}%)"
    else:
        vix_note = str(vix_val)
    # 金: 変動率付き
    gold_str = f"${gold_p}" + (f"({gold_chg:+.1f}%)" if isinstance(gold_chg, float) else "")
    sections.append(
        f"[重要:企業影響] マクロ({date_str[:10]})\n"
        f"【単位: 為替=円建て、株価指数=ドル/ポイント、原油・金=ドル建て1オンス】\n"
        f"日経: {nikkei}円 前日比: {nikkei_change if nikkei_change else '取得中'}\n"
        f"USD/JPY: {usd_jpy}円（円安＝輸出企業に有利）\n"
        f"S&P500: {sp500}ドル({sp_chg_str}) / VIX: {vix_note}\n"
        f"WTI原油: ${wti}({wti_chg_str}) / 金: {gold_str}"
    )

    # =====================================================
    # 2b. [重要:最優先] 本日の市場変動の主因候補（架空補完防止）
    # =====================================================
    drivers = _estimate_market_drivers(data)
    sections.append(f"[重要:最優先] 本日の市場変動の主因候補\n{drivers}")

    # =====================================================
    # 3. [重要:最優先] 適時開示サマリー（分類済み）
    # =====================================================
    disclosure = data.get("disclosure_results", {})
    pos     = disclosure.get("positive", [])[:3]
    neg     = disclosure.get("negative", [])[:3]
    neutral = disclosure.get("neutral",  [])[:5]
    notable = disclosure.get("notable",  [])[:2]
    # 数値データが混入しているエントリを除外（company名が数字のみ等）
    def _valid_disclosure(d: dict) -> bool:
        company = d.get("company", "")
        title   = d.get("title", "")
        return bool(company) and not company.replace(",", "").replace(".", "").replace(" ", "").isdigit() and len(title) > 5

    pos     = [d for d in pos     if _valid_disclosure(d)]
    neg     = [d for d in neg     if _valid_disclosure(d)]
    neutral = [d for d in neutral if _valid_disclosure(d)]
    notable = [d for d in notable if _valid_disclosure(d)]
    disc_lines = ["[重要:最優先] 本日の適時開示"]
    if pos:
        disc_lines.append("【ポジティブ】 " + " / ".join(
            d.get("company", "") + "「" + d.get("title", "")[:25] + "」"
            for d in pos
        ))
    if neg:
        disc_lines.append("【ネガティブ】 " + " / ".join(
            d.get("company", "") + "「" + d.get("title", "")[:25] + "」"
            for d in neg
        ))
    if neutral:
        disc_lines.append("【中立】 " + " / ".join(
            d.get("company", "") + "「" + d.get("title", "")[:20] + "」"
            for d in neutral[:3]
        ))
    if notable:
        disc_lines.append("【注目提携】 " + " / ".join(
            d.get("company", "") + "×" + str(d.get("partners", ["?"])[:1])
            for d in notable
        ))
    if len(disc_lines) == 1:
        disc_lines.append("本日は特筆すべき適時開示はありませんでした。")
    sections.append("\n".join(disc_lines))

    # =====================================================
    # 4. [中:参考] 相関分析（解釈のみ・数値なし）
    # =====================================================
    corr_text = data.get("corr_text", "")
    # キャッシュが空の場合、最新の相関分析ファイルから読み込む
    if not corr_text:
        try:
            import json as _json
            corr_dir = AGENT_ROOT / "knowledge" / "correlation"
            corr_dir.mkdir(parents=True, exist_ok=True)
            corr_files = sorted(
                corr_dir.glob("*_correlations.json"),
                reverse=True
            )
            if corr_files:
                corr_data = _json.loads(corr_files[0].read_text(encoding="utf-8"))
                from correlation_analyzer import format_correlations_for_article
                corr_text = format_correlations_for_article(corr_data)
                print(f"  📊 相関データをキャッシュから読み込み: {len(corr_text)}文字")
        except Exception as e:
            print(f"  ⚠️ 相関キャッシュ読み込み失敗: {e}")
    if corr_text:
        interp_lines = []
        for line in corr_text.split("\n"):
            if "—" in line:
                parts = line.split("—")
                if len(parts) > 1:
                    interp = parts[-1].strip()
                    if "相関" in interp or "連動" in interp or "傾向" in interp:
                        interp_lines.append(f"・{interp}")
        if interp_lines:
            sections.append("[中:参考] 相関分析（解釈）\n" + "\n".join(interp_lines[:5]))

    # =====================================================
    # 5. [重要:企業影響] 法務リスク（高+中リスク、前日重複排除済み）
    # =====================================================
    legal      = data.get("legal", {})
    high_legal = legal.get("high", [])
    med_legal  = legal.get("medium", [])
    # 新規・進展のある情報のみに絞り込む
    try:
        from legal_collector import filter_new_legal_items
        all_legal_items = high_legal + med_legal
        new_legal_items = filter_new_legal_items(all_legal_items, date_str)
        high_legal = [i for i in new_legal_items if i.get("risk", {}).get("level") == "high"][:5]
        med_legal  = [i for i in new_legal_items if i.get("risk", {}).get("level") == "medium"][:2]
    except Exception as e:
        print(f"  ⚠️ 法務重複排除スキップ: {e}")
        high_legal = high_legal[:5]
        med_legal  = med_legal[:2]
    if high_legal or med_legal:
        legal_lines = ["[重要:企業影響] 法務リスク情報（本日新規・進展）"]
        for item in high_legal:
            note = f"（{item['note']}）" if item.get("note") else ""
            legal_lines.append(f"🔴 {item.get('title', '')[:60]}{note}")
        for item in med_legal:
            note = f"（{item['note']}）" if item.get("note") else ""
            legal_lines.append(f"🟡 {item.get('title', '')[:60]}{note}")
        sections.append("\n".join(legal_lines))
    else:
        sections.append("[重要:企業影響] 法務リスク情報\n本日新たな行政処分情報はありません")

    # =====================================================
    # 6. [中:参考] ニュース → トピック要約
    # =====================================================
    news = data.get("news", [])[:20]
    if news:
        news_titles = "\n".join(
            f"- [{n.get('source', '')}] {n.get('title', '')}"
            for n in news[:15]
            if n.get('title')
        )
        summary_prompt = (
            "以下のニュースタイトル一覧を読んで、3〜5つのグループにまとめてください。\n"
            "【絶対ルール】\n"
            "- 各タイトルをそのまま使う（言い換えや補完は禁止）\n"
            "- タイトルにない情報を追加しない\n"
            "- カテゴリ名はタイトルの内容から自然に決める\n"
            "- 形式: 「・[カテゴリ]: タイトルの要点をそのまま引用」\n"
            "- 日本語のみ（英語・中国語・韓国語禁止）\n"
            "- 全体200文字以内\n"
            f"ニュースタイトル:\n{news_titles}\n"
            "まとめ（タイトルの言葉をそのまま使うこと）:"
        )
        try:
            news_summary = ask_plain(summary_prompt)
            # 要約が有効な場合のみ使用
            if news_summary and len(news_summary) > 30 and not news_summary.strip().startswith("{"):
                sections.append("[中:参考] 本日のニューストピック\n" + news_summary[:400])
            else:
                raise ValueError("invalid summary")
        except Exception:
            # フォールバック: タイトルをそのまま列挙
            fallback = "\n".join(
                f"・{n.get('title', '')[:50]}"
                for n in news[:5]
                if n.get('title')
            )
            sections.append("[中:参考] 本日のニュース\n" + fallback)

    # =====================================================
    # 7. [補助:傾向] 求人トレンド
    # =====================================================
    jobs     = data.get("jobs", {})
    industry = jobs.get("industry_trends", {})
    if industry:
        job_lines = ["[補助:傾向] 求人トレンド（業界別）"]
        for ind, info in list(industry.items())[:5]:
            raw_kw    = info.get("top_keywords", info.get("keywords", {}))
            job_count = info.get("job_count", 0)
            # top_keywords は dict or list どちらも対応
            if isinstance(raw_kw, dict):
                kw_list = list(raw_kw.keys())
            elif isinstance(raw_kw, list):
                kw_list = raw_kw
            else:
                kw_list = []
            # キーワード数で活発度を判定
            if len(kw_list) >= 3:
                trend = f"活発（注目KW: {', '.join(kw_list[:2])}）"
            elif len(kw_list) >= 1:
                trend = f"普通（{kw_list[0]}）"
            elif job_count >= 10:
                trend = "普通（件数十分）"
            else:
                trend = "低調"
            job_lines.append(f"・{ind}: {trend}")
        sections.append("\n".join(job_lines))

    # =====================================================
    # 8. [補助:傾向] SNS感情
    # =====================================================
    social     = data.get("social", {})
    sentiments = social.get("stock_sentiment", {})
    if sentiments:
        sent_lines = ["[補助:傾向] 掲示板感情傾向"]
        for code, s in list(sentiments.items())[:3]:
            sent = s.get("sentiment", "中立")
            sent_lines.append(f"・{code}: {sent}")
        sections.append("\n".join(sent_lines))

    # =====================================================
    # 8.5 [中:参考] 値動き銘柄の関連ニュース紐付け
    # =====================================================
    def _find_stock_news(company_name: str, news_list: list) -> str:
        """
        ニュース一覧から特定企業に言及しているものを探す。
        完全一致優先 → 先頭4文字の部分一致 → なし
        """
        company_short = company_name[:4]  # 先頭4文字で部分一致

        for news in news_list:
            title   = news.get("title", "")
            summary = news.get("summary", "")
            text    = title + " " + summary
            # 完全一致優先
            if company_name in text:
                return title[:60]

        # 部分一致（4文字以上の場合のみ）
        if len(company_short) >= 4:
            for news in news_list:
                title   = news.get("title", "")
                summary = news.get("summary", "")
                text    = title + " " + summary
                if company_short in text:
                    return title[:60]

        return ""

    all_news          = data.get("news", [])
    stock_news_lines  = []
    up_items   = data.get("up_ranking",   [])[:5]
    down_items = data.get("down_ranking", [])[:5]
    for item in up_items + down_items:
        m = re.match(r'\d+\.\s*(.+?)\s*\([+-]', item)
        if m:
            company = m.group(1).strip()
            related = _find_stock_news(company, all_news)
            if related:
                stock_news_lines.append(f"・{company}: {related}")
    if stock_news_lines:
        sections.append("[中:参考] 値動き銘柄の関連ニュース\n" + "\n".join(stock_news_lines))
    else:
        sections.append(
            "[中:参考] 値動き銘柄の関連ニュース\n"
            "・本日は各銘柄の明確な材料ニュースは確認できませんでした"
        )

    # =====================================================
    # 8.7 [中:参考] 特許・知財動向（前日重複排除）
    # =====================================================
    patent_items = data.get("patent", [])
    if patent_items:
        try:
            from news_collector import filter_new_patent_items
            patent_new = filter_new_patent_items(patent_items)
        except Exception as e:
            print(f"  ⚠️ 特許重複排除スキップ: {e}")
            patent_new = patent_items

        if patent_new:
            patent_titles = "\n".join(
                f"・{item['title'][:60]}"
                + ("（進展あり）" if item.get("note") == "進展あり" else "")
                for item in patent_new[:5]
            )
            sections.append(f"[中:参考] 本日の特許・知財動向\n{patent_titles}")
        else:
            sections.append(
                "[補助:傾向] 本日の特許・知財動向\n本日新たな特許・知財情報はありません"
            )

    # =====================================================
    # [必須知識] 経済常識RAG注入
    # =====================================================
    economics_file = AGENT_ROOT / "knowledge" / "economics" / "basics.md"
    if economics_file.exists():
        relevant = []
        usd_chg_val = forex.get("USD/JPY", {}).get("change_pct", 0) or 0
        if isinstance(usd_chg_val, (int, float)):
            if usd_chg_val > 0:
                relevant.append("[経済原則] 円安進行: 輸出企業に有利・輸入コスト上昇")
            else:
                relevant.append("[経済原則] 円高進行: 輸出企業に不利（海外売上が円換算で目減り）・輸入コスト低下")
        vix_chg_val = us.get("VIX", {}).get("change_pct", 0) or 0
        if isinstance(vix_chg_val, (int, float)):
            if vix_chg_val > 3:
                relevant.append("[経済原則] VIX上昇: 市場の不安感が高まっている・リスクオフ")
            elif vix_chg_val < -3:
                relevant.append("[経済原則] VIX下落: 市場の不安感が緩和・リスクオン傾向")
        wti_chg_val = comm.get("WTI原油", {}).get("change_pct", 0) or 0
        if isinstance(wti_chg_val, (int, float)) and wti_chg_val > 3:
            relevant.append("[経済原則] 原油急騰: 製造業・運輸業に不利・エネルギーコスト上昇")
        if relevant:
            sections.append("[必須知識] 本日の市場に関連する経済原則\n" + "\n".join(relevant))

    # =====================================================
    # [制約] 利用可能なデータ一覧（架空補完防止）
    # =====================================================
    sections.append(
        "[制約] 利用可能なデータ\n"
        "以下のデータのみを使用すること。データにない企業名・数値は記載しない:\n"
        f"- 市況: 日経平均・値上がり/値下がりランキング（上記のみ）\n"
        f"- マクロ: USD/JPY・S&P500・VIX・WTI原油・金（上記のみ）\n"
        "- ニュース: 上記のトピック要約のみ\n"
        "- 法務: 上記の行政処分・訴訟情報のみ\n"
        "- 適時開示: 上記の分類結果のみ\n"
        "データに含まれない: ファナック・トヨタ等の個別銘柄の業績・株価予測"
    )

    # =====================================================
    # 結合して返す
    # =====================================================
    context = "\n\n".join(sections)
    print(f"  📐 コンテキスト圧縮: {len(context)}文字")
    return context
