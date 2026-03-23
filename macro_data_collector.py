"""
マクロ経済データ収集システム。

収集するデータ:
- 為替（USD/JPY・EUR/JPY・GBP/JPY・CNY/JPY）
- 原油価格（WTI・ブレント）
- 米国株（NYダウ・S&P500・NASDAQ・VIX・Russell2000）
- 金・銀・天然ガス
- 米10年債利回り

全て Yahoo Finance v8 API（無料）から取得。
※ 投資助言は行わない。データ収集・整理のみ。
"""
import json
import requests
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent
MACRO_DIR  = AGENT_ROOT / "knowledge" / "macro"
HEADERS    = {
    "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
    "Accept":     "application/json",
}

# =====================================================
# シンボル定義
# =====================================================
FOREX_SYMBOLS = {
    "USD/JPY": "USDJPY=X",
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "CNY/JPY": "CNYJPY=X",
}

COMMODITY_SYMBOLS = {
    "WTI原油":    "CL=F",
    "ブレント原油": "BZ=F",
    "金":         "GC=F",
    "銀":         "SI=F",
    "天然ガス":   "NG=F",
}

US_INDEX_SYMBOLS = {
    "NYダウ":       "^DJI",
    "S&P500":       "^GSPC",
    "NASDAQ":       "^IXIC",
    "VIX":          "^VIX",
    "Russell2000":  "^RUT",
}

BOND_SYMBOLS = {
    "米10年債利回り": "^TNX",
    "米2年債利回り":  "^IRX",
}


# =====================================================
# 共通取得関数
# =====================================================
def _fetch_symbol(symbol: str) -> dict:
    """
    Yahoo Finance v8 API から1銘柄のデータを取得する。
    Returns: {"price", "prev_close", "change", "change_pct", "high", "low"}
    """
    try:
        url  = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            "?interval=1d&range=1d"
        )
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        meta = resp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})

        price = meta.get("regularMarketPrice")
        prev  = meta.get("previousClose") or meta.get("chartPreviousClose")
        high  = meta.get("regularMarketDayHigh")
        low   = meta.get("regularMarketDayLow")

        if price is None:
            return {"error": "price=None"}

        change     = round(price - prev, 4) if prev else 0.0
        change_pct = round(change / prev * 100, 2) if prev else 0.0

        return {
            "price":      price,
            "prev_close": prev,
            "change":     change,
            "change_pct": change_pct,
            "high":       high,
            "low":        low,
        }
    except Exception as e:
        return {"error": str(e)}


def _fetch_group(symbol_map: dict, label: str) -> dict:
    """複数シンボルを一括取得してラベル付き辞書で返す"""
    results = {}
    ok = 0
    for name, symbol in symbol_map.items():
        data = _fetch_symbol(symbol)
        data["symbol"] = symbol
        results[name]  = data
        if "error" not in data:
            ok += 1
            price      = data["price"]
            change_pct = data["change_pct"]
            print(f"  ✅ {name:15s}: {price:>12,.4f}  ({change_pct:+.2f}%)")
        else:
            print(f"  ⚠️ {name:15s}: {data['error']}")
    print(f"  [{label}] {ok}/{len(symbol_map)} ソース")
    return results


# =====================================================
# 各カテゴリ取得
# =====================================================
def fetch_forex() -> dict:
    """為替レートを取得する"""
    print("  💱 為替...")
    return _fetch_group(FOREX_SYMBOLS, "為替")


def fetch_commodities() -> dict:
    """原油・金・銀・天然ガスを取得する"""
    print("  🛢️  コモディティ...")
    return _fetch_group(COMMODITY_SYMBOLS, "コモディティ")


def fetch_us_stocks() -> dict:
    """米国主要株価指数を取得する"""
    print("  🇺🇸 米国株式...")
    return _fetch_group(US_INDEX_SYMBOLS, "米国株")


def fetch_bond_yields() -> dict:
    """米国債利回りを取得する"""
    print("  📊 債券利回り...")
    return _fetch_group(BOND_SYMBOLS, "債券")


# =====================================================
# マクロ分析テキスト生成
# =====================================================
def analyze_macro_impact(data: dict) -> str:
    """
    マクロデータから日本株市場への影響を客観的に解説する。
    ※ 事実ベースの記述のみ。投資助言なし。
    """
    try:
        from llm import ask_plain

        forex  = data.get("forex", {})
        comm   = data.get("commodities", {})
        us     = data.get("us_stocks", {})
        bonds  = data.get("bonds", {})

        def fmt(d: dict, key: str, decimals: int = 2) -> str:
            v = d.get(key, {})
            if "error" in v or not v:
                return "N/A"
            p   = v.get("price", "N/A")
            pct = v.get("change_pct")
            if isinstance(p, float):
                p = f"{p:,.{decimals}f}"
            return f"{p} ({pct:+.2f}%)" if isinstance(pct, float) else str(p)

        usd_jpy = fmt(forex, "USD/JPY")
        eur_jpy = fmt(forex, "EUR/JPY")
        wti     = fmt(comm,  "WTI原油")
        gold    = fmt(comm,  "金")
        dow     = fmt(us,    "NYダウ",  0)
        sp500   = fmt(us,    "S&P500",  2)
        vix_raw = us.get("VIX", {}).get("price", "N/A")
        vix     = f"{vix_raw:.2f}" if isinstance(vix_raw, float) else str(vix_raw)
        tnx     = fmt(bonds, "米10年債利回り", 3)

        prompt = f"""以下のマクロ経済データを使って、日本株市場への影響を客観的に解説してください。

【本日のマクロデータ】
- ドル円: {usd_jpy}
- ユーロ円: {eur_jpy}
- WTI原油: {wti}
- 金: {gold}
- NYダウ: {dow}
- S&P500: {sp500}
- VIX（恐怖指数）: {vix}
- 米10年債利回り: {tnx}

【ルール】
- 断定的な表現は避ける（「〜の可能性がある」「〜と見られる」等を使う）
- 買い推奨・売り推奨は絶対に書かない
- 200文字以内で簡潔に
- 日本語で書く
- VIXが20以上の場合は「市場の警戒感が高まっている」等と記述する
"""
        analysis = ask_plain(prompt)
        return (analysis or "").strip()[:400]
    except Exception:
        return ""


# =====================================================
# メイン収集
# =====================================================
def collect_macro_data() -> dict:
    """全マクロデータを収集して返す"""
    print("\n  🌏 マクロデータ収集中...")

    data = {
        "date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "forex":      fetch_forex(),
        "commodities": fetch_commodities(),
        "us_stocks":  fetch_us_stocks(),
        "bonds":      fetch_bond_yields(),
    }

    # LLM分析テキスト
    data["macro_analysis"] = analyze_macro_impact(data)

    # 保存
    MACRO_DIR.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = MACRO_DIR / f"{stamp}_macro.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  💾 保存: {out_path.name}")
    return data


def format_macro_for_article(data: dict) -> str:
    """マクロデータを記事挿入用 Markdown テキストに変換する"""
    lines = ["## 🌏 マクロ経済環境\n"]

    def row(name: str, d: dict, unit: str = "", decimals: int = 2) -> str:
        if "error" in d or not d:
            return f"- {name}: 取得中"
        price      = d.get("price", "N/A")
        change_pct = d.get("change_pct")
        arrow      = ""
        if isinstance(change_pct, float):
            arrow = "▲" if change_pct >= 0 else "▼"
            chg_str = f"  {arrow}{change_pct:+.2f}%"
        else:
            chg_str = ""
        if isinstance(price, float):
            price_str = f"{price:,.{decimals}f}{unit}"
        else:
            price_str = str(price)
        return f"- **{name}**: {price_str}{chg_str}"

    # 為替
    forex = data.get("forex", {})
    if forex:
        lines.append("### 為替")
        for name, d in forex.items():
            lines.append(row(name, d, "円", 2))
        lines.append("")

    # 米国株
    us = data.get("us_stocks", {})
    if us:
        lines.append("### 米国株式市場")
        for name, d in us.items():
            dec = 2 if name != "VIX" else 2
            lines.append(row(name, d, "", dec))
        lines.append("")

    # コモディティ
    comm = data.get("commodities", {})
    if comm:
        lines.append("### コモディティ")
        for name, d in comm.items():
            lines.append(row(name, d, " USD", 2))
        lines.append("")

    # 債券
    bonds = data.get("bonds", {})
    if bonds:
        lines.append("### 債券利回り")
        for name, d in bonds.items():
            lines.append(row(name, d, "%", 3))
        lines.append("")

    # マクロ分析
    analysis = data.get("macro_analysis", "")
    if analysis:
        lines.append("### マクロ環境の概況")
        lines.append(analysis)
        lines.append("")

    lines.append(
        "> ⚠️ 上記データは情報提供のみを目的としており、投資判断の根拠としないでください。"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    data = collect_macro_data()
    print()
    print(format_macro_for_article(data))
