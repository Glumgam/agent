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
# データ保存
# =====================================================
def collect_finance_data() -> dict:
    """全ての投資データを収集してまとめて返す"""
    print("  📈 投資データ収集中...")

    from disclosure_analyzer import analyze_today_disclosures, format_for_article

    data = {
        "date":              datetime.now().strftime("%Y-%m-%d"),
        "market_summary":    fetch_market_summary(),
        "up_ranking":        fetch_ranking("up"),
        "down_ranking":      fetch_ranking("down"),
        "disclosure_results": analyze_today_disclosures(),
    }

    # 記事用テキストを生成
    data["disclosure_text"] = format_for_article(data["disclosure_results"])

    # 保存
    FINANCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FINANCE_DIR / f"{data['date']}_finance_data.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  💾 保存: {out_path.name}")
    return data
