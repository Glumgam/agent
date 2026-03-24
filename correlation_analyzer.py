"""
株価と各種指標の相関分析システム。
分析対象:
- 個別株 vs 日経平均・TOPIX
- 個別株 vs 為替（USD/JPY等）
- 個別株 vs コモディティ（原油・金・穀物）
- 個別株 vs 米国株（S&P500・NASDAQ）
出力:
- 相関係数テキスト
- ヒートマップ画像（PNG）
- 折れ線比較グラフ（PNG）
※ 相関は過去データの統計的関係のみ。
※ 将来の予測・投資助言は行わない。
"""
import json
import time
import requests
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

AGENT_ROOT = Path(__file__).parent
CORR_DIR   = AGENT_ROOT / "knowledge" / "correlation"
CHART_DIR  = AGENT_ROOT / "content" / "charts"
HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}

# 日本語フォント設定（japanize_matplotlib の代替）
_JP_FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",   # macOS
    "/System/Library/Fonts/ヒラギノ角ゴ Pro W3.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # Linux
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
]

def _setup_japanese_font():
    """利用可能な日本語フォントを matplotlib に登録する"""
    try:
        import matplotlib
        import matplotlib.font_manager as fm
        for fpath in _JP_FONT_CANDIDATES:
            if Path(fpath).exists():
                fm.fontManager.addfont(fpath)
                prop = fm.FontProperties(fname=fpath)
                matplotlib.rcParams["font.family"] = prop.get_name()
                return prop.get_name()
        # フォールバック: DejaVu Sans（日本語は□になるが動作はする）
        return "DejaVu Sans"
    except Exception:
        return "DejaVu Sans"

# =====================================================
# 指標定義
# =====================================================
INDICATORS = {
    # 日本株指数
    "日経平均":   "^N225",
    "TOPIX":      "^TOPX",
    # 為替
    "USD/JPY":    "USDJPY=X",
    "EUR/JPY":    "EURJPY=X",
    # コモディティ
    "WTI原油":    "CL=F",
    "金":         "GC=F",
    "銅":         "HG=F",
    "コーン":     "ZC=F",
    "小麦":       "ZW=F",
    "大豆":       "ZS=F",
    # 米国株
    "S&P500":     "^GSPC",
    "NASDAQ":     "^IXIC",
    "NYダウ":     "^DJI",
    "VIX":        "^VIX",
}

# 業種別・典型的な相関指標
SECTOR_INDICATORS = {
    "自動車":     ["USD/JPY", "日経平均", "WTI原油"],
    "商社":       ["WTI原油", "金", "銅", "USD/JPY"],
    "半導体":     ["NASDAQ", "S&P500", "USD/JPY"],
    "食品":       ["コーン", "小麦", "大豆", "USD/JPY"],
    "銀行":       ["日経平均", "USD/JPY", "TOPIX"],
    "不動産":     ["日経平均", "TOPIX"],
    "エネルギー": ["WTI原油", "金", "USD/JPY"],
    "医薬品":     ["日経平均", "NASDAQ", "USD/JPY"],
}

# 企業→業種マッピング
COMPANY_SECTOR = {
    "7203": "自動車", "7267": "自動車", "7201": "自動車",
    "8053": "商社",   "8058": "商社",   "8031": "商社",
    "6758": "半導体", "6857": "半導体", "8035": "半導体",
    "2802": "食品",   "2914": "食品",   "2503": "食品",
    "8306": "銀行",   "8316": "銀行",   "8411": "銀行",
    "9984": "半導体", "4755": "半導体",
}


# =====================================================
# 価格データ取得（Yahoo Finance）
# =====================================================
def fetch_price_history(symbol: str, days: int = 90) -> list:
    """
    Yahoo Finance から過去N日間の終値を取得する。
    Returns: [(date, close), ...]
    """
    try:
        end   = int(datetime.now().timestamp())
        start = int((datetime.now() - timedelta(days=days)).timestamp())
        url   = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?period1={start}&period2={end}&interval=1d"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data   = resp.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes     = result["indicators"]["quote"][0]["close"]
        prices = [
            (datetime.fromtimestamp(ts).strftime("%Y-%m-%d"), close)
            for ts, close in zip(timestamps, closes)
            if close is not None
        ]
        return prices
    except Exception:
        return []


def fetch_returns(symbol: str, days: int = 90) -> dict:
    """日次リターン（%変化）を計算して返す"""
    prices = fetch_price_history(symbol, days)
    if len(prices) < 10:
        return {}
    returns = {}
    for i in range(1, len(prices)):
        date = prices[i][0]
        prev = prices[i - 1][1]
        curr = prices[i][1]
        if prev and prev != 0:
            returns[date] = (curr - prev) / prev * 100
    return returns


# =====================================================
# 相関計算
# =====================================================
def calculate_correlation(
    stock_code: str,
    indicators: list = None,
    days: int = 90,
) -> dict:
    """
    株価と各指標の相関係数を計算する。
    Returns:
        {指標名: {"corr": float, "interpretation": str, "data_points": int}}
    """
    if not indicators:
        sector     = COMPANY_SECTOR.get(stock_code, "")
        indicators = SECTOR_INDICATORS.get(sector, list(INDICATORS.keys())[:6])

    print(f"  📊 {stock_code} の相関分析中（{days}日間）...")

    # 株価リターンを取得（.T 付きで試し、失敗したらそのまま）
    stock_returns = fetch_returns(stock_code + ".T", days)
    if not stock_returns:
        stock_returns = fetch_returns(stock_code, days)
    if not stock_returns:
        print(f"    ⚠️ {stock_code}: 株価データ取得失敗")
        return {}

    results = {}
    for ind_name in indicators:
        symbol = INDICATORS.get(ind_name)
        if not symbol:
            continue
        ind_returns = fetch_returns(symbol, days)
        if not ind_returns:
            continue

        # 共通日付で相関計算
        common_dates = sorted(set(stock_returns.keys()) & set(ind_returns.keys()))
        if len(common_dates) < 20:
            continue

        stock_arr = np.array([stock_returns[d] for d in common_dates])
        ind_arr   = np.array([ind_returns[d]   for d in common_dates])

        # NaN除去
        mask      = ~(np.isnan(stock_arr) | np.isnan(ind_arr))
        stock_arr = stock_arr[mask]
        ind_arr   = ind_arr[mask]
        if len(stock_arr) < 15:
            continue

        corr           = float(np.corrcoef(stock_arr, ind_arr)[0, 1])
        interpretation = _interpret_correlation(corr, ind_name)
        results[ind_name] = {
            "corr":           round(corr, 3),
            "interpretation": interpretation,
            "data_points":    len(stock_arr),
        }
        time.sleep(0.3)  # レート制限

    # 相関の強い順にソート
    results = dict(sorted(
        results.items(),
        key=lambda x: abs(x[1]["corr"]),
        reverse=True,
    ))
    return results


def _interpret_correlation(corr: float, indicator: str) -> str:
    """相関係数を自然言語で解釈する"""
    abs_corr  = abs(corr)
    direction = "正の" if corr > 0 else "負の"

    if abs_corr >= 0.7:
        strength = "強い"
    elif abs_corr >= 0.5:
        strength = "中程度の"
    elif abs_corr >= 0.3:
        strength = "弱い"
    else:
        return f"統計的な連動性はほぼ見られない（{abs_corr:.2f}）"

    return (
        f"{indicator}と{direction}{strength}連動が見られる"
        f"（相関係数: {corr:.2f}、過去データ）"
    )


# =====================================================
# ヒートマップ（横棒グラフ形式）
# =====================================================
def generate_correlation_heatmap(
    correlations: dict,
    stock_name: str,
    output_path: Path = None,
) -> Path:
    """相関ヒートマップを生成する"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        _setup_japanese_font()

        if not correlations:
            return None

        indicators = list(correlations.keys())
        corr_vals  = [correlations[k]["corr"] for k in indicators]

        fig, ax = plt.subplots(figsize=(10, max(4, len(indicators) * 0.6 + 2)))

        colors = ["#d32f2f" if v < 0 else "#1976d2" for v in corr_vals]
        bars   = ax.barh(indicators, corr_vals, color=colors, alpha=0.8)

        for bar, val in zip(bars, corr_vals):
            x  = val + (0.02 if val >= 0 else -0.02)
            ha = "left" if val >= 0 else "right"
            ax.text(
                x, bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}", va="center", ha=ha, fontsize=10,
            )

        ax.set_xlim(-1.1, 1.1)
        ax.axvline(x=0,    color="black", linewidth=0.8)
        ax.axvline(x=0.5,  color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
        ax.axvline(x=-0.5, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
        ax.axvline(x=0.7,  color="gray", linewidth=0.5, linestyle=":",  alpha=0.5)
        ax.axvline(x=-0.7, color="gray", linewidth=0.5, linestyle=":",  alpha=0.5)

        ax.set_title(
            f"{stock_name} の相関分析\n（過去90日間・日次リターンベース）",
            fontsize=14, pad=15,
        )
        ax.set_xlabel("相関係数", fontsize=11)

        pos_patch = mpatches.Patch(color="#1976d2", alpha=0.8, label="正の相関")
        neg_patch = mpatches.Patch(color="#d32f2f", alpha=0.8, label="負の相関")
        ax.legend(handles=[pos_patch, neg_patch], loc="lower right")

        fig.text(
            0.5, 0.01,
            "※ 過去データの統計的関係です。将来の価格動向を保証するものではありません。",
            ha="center", fontsize=8, color="gray",
        )
        plt.tight_layout(rect=[0, 0.04, 1, 1])

        if not output_path:
            CHART_DIR.mkdir(parents=True, exist_ok=True)
            date_str    = datetime.now().strftime("%Y%m%d")
            output_path = CHART_DIR / f"{date_str}_{stock_name}_correlation.png"

        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  🖼️  ヒートマップ保存: {output_path.name}")
        return output_path

    except ImportError as e:
        print(f"  ⚠️ matplotlib/japanize_matplotlib が必要: {e}")
        return None
    except Exception as e:
        print(f"  ⚠️ ヒートマップ生成エラー: {e}")
        return None


# =====================================================
# 折れ線比較グラフ
# =====================================================
def generate_price_comparison_chart(
    stock_code: str,
    stock_name: str,
    top_indicators: list,
    days: int = 90,
    output_path: Path = None,
) -> Path:
    """株価と上位相関指標の折れ線比較グラフを生成する"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _setup_japanese_font()

        max_lines = min(3, len(top_indicators))
        fig, axes = plt.subplots(
            max_lines + 1, 1,
            figsize=(12, 3 * (max_lines + 1)),
            sharex=True,
        )
        if max_lines + 1 == 1:
            axes = [axes]

        # 株価（正規化）
        stock_prices = fetch_price_history(stock_code + ".T", days)
        if not stock_prices:
            stock_prices = fetch_price_history(stock_code, days)

        if stock_prices:
            prices = [p[1] for p in stock_prices]
            base   = prices[0]
            norm   = [p / base * 100 for p in prices]
            axes[0].plot(range(len(norm)), norm, color="#1976d2", linewidth=2)
            axes[0].set_ylabel(f"{stock_name}\n(正規化)", fontsize=9)
            axes[0].axhline(y=100, color="gray", linewidth=0.5, linestyle="--")
            axes[0].grid(True, alpha=0.3)

        # 各指標（正規化）
        for i, ind_name in enumerate(top_indicators[:max_lines]):
            symbol     = INDICATORS.get(ind_name)
            ind_prices = fetch_price_history(symbol, days) if symbol else []
            if ind_prices:
                ind_vals = [p[1] for p in ind_prices]
                base     = ind_vals[0]
                norm     = [v / base * 100 for v in ind_vals]
                axes[i + 1].plot(range(len(norm)), norm, color="#e65100", linewidth=2)
                axes[i + 1].set_ylabel(f"{ind_name}\n(正規化)", fontsize=9)
                axes[i + 1].axhline(y=100, color="gray", linewidth=0.5, linestyle="--")
                axes[i + 1].grid(True, alpha=0.3)
            time.sleep(0.2)

        axes[-1].set_xlabel("日数（直近→右）", fontsize=10)
        fig.suptitle(
            f"{stock_name} と関連指標の比較（過去{days}日間）",
            fontsize=13, y=1.01,
        )
        fig.text(
            0.5, -0.01,
            "※ 全て最初の値を100として正規化。過去データであり将来の予測ではありません。",
            ha="center", fontsize=8, color="gray",
        )
        plt.tight_layout()

        if not output_path:
            CHART_DIR.mkdir(parents=True, exist_ok=True)
            date_str    = datetime.now().strftime("%Y%m%d")
            output_path = CHART_DIR / f"{date_str}_{stock_name}_comparison.png"

        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  🖼️  比較チャート保存: {output_path.name}")
        return output_path

    except Exception as e:
        print(f"  ⚠️ 比較チャート生成エラー: {e}")
        return None


# =====================================================
# メイン処理
# =====================================================
def analyze_stock_correlations(
    stock_codes: list,
    days: int = 90,
    generate_charts: bool = True,
) -> dict:
    """複数銘柄の相関分析を実行する"""
    from stock_linker import COMPANY_CODE_MAP
    code_to_name = {v: k for k, v in COMPANY_CODE_MAP.items()}

    results = {}
    for code in stock_codes[:5]:  # 最大5銘柄
        name = code_to_name.get(code, f"銘柄{code}")
        print(f"\n  🔍 {name}({code}) を分析中...")

        corr = calculate_correlation(code, days=days)
        if not corr:
            continue

        chart_heatmap    = None
        chart_comparison = None
        if generate_charts:
            chart_heatmap    = generate_correlation_heatmap(corr, name)
            top_indicators   = list(corr.keys())[:3]
            chart_comparison = generate_price_comparison_chart(
                code, name, top_indicators, days,
            )

        results[code] = {
            "name":             name,
            "correlations":     corr,
            "chart_heatmap":    str(chart_heatmap) if chart_heatmap else None,
            "chart_comparison": str(chart_comparison) if chart_comparison else None,
            "analyzed_at":      datetime.now().isoformat(),
        }

    # トラッキング分析（スナップショット保存＋変化検知）
    try:
        from correlation_tracker import track_and_analyze
        tracking_results = []
        for code, data in results.items():
            tracking = track_and_analyze(
                code,
                data["correlations"],
                data.get("name", code),
            )
            data["tracking"] = tracking
            tracking_results.append(tracking)
        results["_tracking_summary"] = tracking_results
    except Exception as e:
        print(f"  ⚠️ トラッキング失敗: {e}")
        results["_tracking_summary"] = []

    # 保存
    CORR_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CORR_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}_correlations.json"
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  💾 保存: {out_path.name}")
    return results


def format_correlations_for_article(results: dict) -> str:
    """相関分析結果を記事用テキストに変換する"""
    lines = [
        "## 📊 相関分析（過去データ）\n",
        "> ⚠️ 以下は過去90日間の日次リターンに基づく統計的分析です。",
        "> 将来の株価動向を予測するものではありません。\n",
    ]

    for code, data in results.items():
        name         = data.get("name", code)
        correlations = data.get("correlations", {})
        chart        = data.get("chart_heatmap")

        if not correlations:
            continue

        lines.append(f"### {name}（{code}）")
        for ind_name, info in list(correlations.items())[:3]:
            corr   = info.get("corr", 0)
            interp = info.get("interpretation", "")
            lines.append(f"- **{ind_name}**: {corr:+.2f} — {interp}")

        if chart:
            lines.append(f"\n![{name}相関分析]({chart})\n")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="株価相関分析")
    parser.add_argument(
        "--codes", nargs="+", default=["7203"],
        help="分析対象の銘柄コード（例: 7203 6758）",
    )
    parser.add_argument("--days",        type=int,  default=60,   help="分析日数")
    parser.add_argument("--no-charts",   action="store_true",     help="チャート生成をスキップ")
    args = parser.parse_args()

    results = analyze_stock_correlations(
        args.codes,
        days=args.days,
        generate_charts=not args.no_charts,
    )
    print()
    print(format_correlations_for_article(results))
