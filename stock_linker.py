"""
ニュース→銘柄紐付けシステム。
ニューステキストから企業名を抽出し、銘柄コードと株価データを紐付ける。

※ 投資助言は行わない。データの収集・整理・紹介のみ。
"""
import re
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta

AGENT_ROOT  = Path(__file__).parent
STOCK_DIR   = AGENT_ROOT / "knowledge" / "stock_cache"
HEADERS     = {
    "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
    "Accept":     "application/json",
}

# =====================================================
# 企業名 → 銘柄コード マスター辞書
# 主要銘柄のみ。kabutan APIで補完する。
# =====================================================
COMPANY_CODE_MAP = {
    # 自動車
    "トヨタ":           "7203", "トヨタ自動車":    "7203",
    "ホンダ":           "7267", "本田技研":        "7267",
    "日産":             "7201", "日産自動車":      "7201",
    "マツダ":           "7261",
    "スズキ":           "7269",
    "三菱自動車":       "7211",
    "SUBARU":           "7270", "スバル":          "7270",
    "デンソー":         "6902",
    # 電機・IT
    "ソニー":           "6758", "ソニーグループ":  "6758",
    "パナソニック":     "6752",
    "日立":             "6501", "日立製作所":      "6501",
    "富士通":           "6702",
    "NEC":              "6701",
    "シャープ":         "6753",
    "キヤノン":         "7751",
    "東芝":             "6502",
    "ルネサス":         "6723",
    "村田製作所":       "6981",
    # 通信
    "NTT":              "9432", "NTTドコモ":       "9437",
    "ソフトバンク":     "9434", "ソフトバンクグループ": "9984",
    "KDDI":             "9433",
    "楽天":             "4755", "楽天グループ":    "4755",
    # 金融
    "三菱UFJ":          "8306", "三菱UFJフィナンシャル": "8306",
    "三井住友":         "8316", "三井住友フィナンシャルグループ": "8316",
    "みずほ":           "8411", "みずほフィナンシャルグループ": "8411",
    "野村":             "8604", "野村ホールディングス": "8604",
    "東京海上":         "8766", "東京海上ホールディングス": "8766",
    "第一生命":         "8750",
    "三井住友銀行":     "8316",
    # 流通・小売
    "イオン":           "8267",
    "セブン":           "3382", "セブン＆アイ":    "3382",
    "ファーストリテイリング": "9983", "ユニクロ":  "9983",
    "ニトリ":           "9843",
    "マツキヨ":         "3088",
    # 食品・飲料
    "キリン":           "2503", "キリンホールディングス": "2503",
    "アサヒ":           "2502", "アサヒグループ":  "2502",
    "サントリー":       "2587",
    "日清食品":         "2897",
    "味の素":           "2802",
    "明治":             "2269",
    # 薬・ヘルスケア
    "武田薬品":         "4502",
    "アステラス製薬":   "4503",
    "大塚ホールディングス": "4578",
    "エーザイ":         "4523",
    # 不動産
    "三井不動産":       "8801",
    "三菱地所":         "8802",
    "住友不動産":       "8830",
    # その他主要
    "任天堂":           "7974",
    "キーエンス":       "6861",
    "ファナック":       "6954",
    "リクルート":       "6098",
    "電通":             "4324",
    "日本郵政":         "6178",
    "JR東日本":         "9020",
    "ANA":              "9202", "全日空":          "9202",
    "JAL":              "9201", "日本航空":        "9201",
    "日本板硝子":       "5202",
}

# =====================================================
# 企業名抽出
# =====================================================
def extract_companies_from_text(text: str) -> list:
    """
    テキストから企業名を抽出してコードと一覧を返す。
    Returns: [{"name": str, "code": str}, ...]
    """
    found   = []
    matched = set()

    # 長い名前優先でマッチ（部分一致を避けるため）
    for name in sorted(COMPANY_CODE_MAP.keys(), key=len, reverse=True):
        if name in text and name not in matched:
            code = COMPANY_CODE_MAP[name]
            if code not in {c["code"] for c in found}:  # コード重複除去
                found.append({"name": name, "code": code})
                matched.add(name)

    # 未登録企業をパターンで補完（株式会社〇〇、〇〇HD等）
    patterns = [
        r'([\u4e00-\u9fff\u30a0-\u30ff]{2,8}(?:ホールディングス|グループ|製薬|自動車|電機|工業|銀行|証券|保険|不動産))',
        r'(?:株式会社|㈱)([\u4e00-\u9fff\u30a0-\u30ff]{2,12})',
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            name = m.group(1) if '(?:' in pattern else m.group(1)
            if name and name not in matched and name not in COMPANY_CODE_MAP:
                found.append({"name": name, "code": None})  # コード未解決
                matched.add(name)

    return found[:10]  # 最大10社


def resolve_code_from_kabutan(company_name: str) -> str | None:
    """
    kabutan の検索から銘柄コードを解決する。
    COMPANY_CODE_MAP にない企業に使用。
    """
    try:
        url  = f"https://kabutan.jp/stock/search?keyword={requests.utils.quote(company_name)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        # 4桁の数字コードを抽出
        codes = re.findall(r'/stock/\?code=(\d{4})', resp.text)
        return codes[0] if codes else None
    except Exception:
        return None


# =====================================================
# 株価取得
# =====================================================
def fetch_stock_price(code: str) -> dict:
    """
    銘柄コードから直近の株価データを取得する。
    Yahoo Finance API (^N225 形式) を使用。

    Returns:
        {
            "code": str, "price": float, "prev_close": float,
            "change": float, "change_pct": float,
            "high": float, "low": float, "volume": int,
            "date": str, "error": str (失敗時のみ)
        }
    """
    try:
        ticker = f"{code}.T"
        url    = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            "?interval=1d&range=5d"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        result_data = data.get("chart", {}).get("result", [])
        if not result_data:
            return {"code": code, "error": "データなし"}

        meta     = result_data[0].get("meta", {})
        price    = meta.get("regularMarketPrice")
        prev     = meta.get("previousClose") or meta.get("chartPreviousClose")
        high     = meta.get("regularMarketDayHigh")
        low      = meta.get("regularMarketDayLow")
        volume   = meta.get("regularMarketVolume")
        currency = meta.get("currency", "JPY")

        if price is None:
            return {"code": code, "error": "価格取得失敗"}

        change     = (price - prev) if prev else 0.0
        change_pct = (change / prev * 100) if prev else 0.0

        return {
            "code":       code,
            "price":      price,
            "prev_close": prev,
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "high":       high,
            "low":        low,
            "volume":     volume,
            "currency":   currency,
            "date":       datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as e:
        return {"code": code, "error": str(e)}


def fetch_stock_prices_bulk(codes: list) -> dict:
    """
    複数銘柄の株価を一括取得する。
    Returns: {code: price_dict}
    """
    results = {}
    for code in codes:
        if code:
            results[code] = fetch_stock_price(code)
    return results


# =====================================================
# ニュース→銘柄紐付け
# =====================================================
def enrich_news_with_stocks(news_items: list) -> list:
    """
    ニュースリストに関連銘柄と株価データを付与する。

    各ニュースに:
        "companies": [{"name": str, "code": str, "price_data": dict}]
    を追加する。
    """
    # 全ニュースから企業名を抽出してコードをまとめて取得（API節約）
    all_codes: set = set()
    enriched = []
    for item in news_items:
        text      = item.get("title", "") + " " + item.get("summary", "")
        companies = extract_companies_from_text(text)
        # コード未解決をkabutan補完
        for c in companies:
            if c["code"] is None:
                c["code"] = resolve_code_from_kabutan(c["name"])
            if c["code"]:
                all_codes.add(c["code"])
        item = dict(item)
        item["companies"] = companies
        enriched.append(item)

    # 株価一括取得
    price_map = fetch_stock_prices_bulk(list(all_codes))

    # 各ニュースにprice_dataを紐付け
    for item in enriched:
        for c in item["companies"]:
            code = c.get("code")
            if code and code in price_map:
                c["price_data"] = price_map[code]
            else:
                c["price_data"] = {}

    return enriched


# =====================================================
# 記事用フォーマット
# =====================================================
def format_stock_news_for_article(enriched_items: list, max_items: int = 8) -> str:
    """
    銘柄情報付きニュースを記事挿入用 Markdown に変換する。
    投資助言的な表現を排除し、事実のみを記述する。
    """
    if not enriched_items:
        return ""

    lines = ["## 関連銘柄の動き\n"]
    shown = 0

    for item in enriched_items:
        companies = [c for c in item.get("companies", []) if c.get("price_data")]
        if not companies:
            continue

        lines.append(f"### 📰 {item.get('title', '')}")
        lines.append(f"> 出典: {item.get('source', '')}\n")

        for c in companies[:3]:
            pd = c["price_data"]
            if "error" in pd:
                continue
            price  = pd.get("price", 0)
            change = pd.get("change", 0)
            pct    = pd.get("change_pct", 0)
            arrow  = "▲" if change >= 0 else "▼"
            sign   = "+" if change >= 0 else ""

            lines.append(
                f"- **{c['name']}**（{c['code']}）: "
                f"¥{price:,.0f}  {arrow}{sign}{change:,.0f}円 ({sign}{pct:.2f}%)"
            )

        lines.append("")
        shown += 1
        if shown >= max_items:
            break

    if shown == 0:
        return ""

    lines.append(
        "> ⚠️ 株価データは参考情報です。投資判断はご自身の責任で行ってください。"
    )
    return "\n".join(lines)


# =====================================================
# キャッシュ保存
# =====================================================
def save_stock_snapshot(enriched_items: list):
    """銘柄スナップショットをキャッシュに保存する"""
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = STOCK_DIR / f"{stamp}_stocks.json"
    out_path.write_text(
        json.dumps(enriched_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ニュース→銘柄紐付けシステム")
    parser.add_argument("--code",  help="株価取得テスト（例: 7203）")
    parser.add_argument("--text",  help="企業名抽出テスト")
    args = parser.parse_args()

    if args.code:
        pd = fetch_stock_price(args.code)
        print(json.dumps(pd, ensure_ascii=False, indent=2))
    elif args.text:
        companies = extract_companies_from_text(args.text)
        for c in companies:
            print(f"企業: {c['name']}  コード: {c['code']}")
    else:
        # デモ実行
        print("=== 企業名抽出テスト ===")
        text = "トヨタ自動車がソニーグループと提携を発表。楽天グループも注目される。"
        companies = extract_companies_from_text(text)
        for c in companies:
            print(f"  {c['name']} → {c['code']}")

        print("\n=== 株価取得テスト ===")
        for code in ["7203", "6758", "4755"]:
            pd = fetch_stock_price(code)
            if "error" not in pd:
                sign = "+" if pd["change"] >= 0 else ""
                print(f"  {code}: ¥{pd['price']:,.0f}  {sign}{pd['change']:,.0f}円 ({sign}{pd['change_pct']:.2f}%)")
            else:
                print(f"  {code}: エラー - {pd['error']}")
