"""
投資記事用グラフ生成システム（Phase 1）
生成するグラフ:
1. 値上がり率ランキング棒グラフ（上位5銘柄）
2. 値下がり率ランキング棒グラフ（下位5銘柄）
3. マクロ変動率比較棒グラフ（日経/S&P500/USD/WTI/金）
"""
import re
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent
CHART_DIR  = AGENT_ROOT / "content" / "charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 日本語フォント候補
_JP_FONT_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴ Pro W3.otf",
    "/System/Library/Fonts/Supplemental/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _setup_font():
    """日本語フォントを設定する"""
    import os
    os.environ.setdefault("MPLBACKEND", "Agg")
    try:
        import matplotlib
        import matplotlib.font_manager as fm
        import warnings
        for fpath in _JP_FONT_CANDIDATES:
            try:
                if Path(fpath).exists():
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        fm.fontManager.addfont(fpath)
                    prop = fm.FontProperties(fname=fpath)
                    matplotlib.rcParams["font.family"] = prop.get_name()
                    return
            except (UnicodeDecodeError, OSError, Exception):
                continue
    except Exception:
        pass


def generate_ranking_chart(finance_data: dict, date_str: str) -> dict:
    """
    値上がり/値下がりランキング棒グラフを生成する。
    Returns:
        {"up_chart": Path, "down_chart": Path}
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _setup_font()
        result = {}

        for kind in ["up", "down"]:
            key     = f"{kind}_ranking"
            ranking = finance_data.get(key, [])
            if not ranking:
                continue

            # データ抽出
            names  = []
            values = []
            for item in ranking[:5]:
                # "1. 銘柄名 (+12.34%)" → 名前と変動率
                m = re.match(r'\d+\.\s*(.+?)\s*\(([+-]?\d+\.?\d*)%?\)', item)
                if m:
                    name = m.group(1).strip()
                    if len(name) > 10:
                        name = name[:9] + "…"
                    val  = float(m.group(2))
                    names.append(name)
                    values.append(val)

            if not names:
                continue

            fig, ax = plt.subplots(figsize=(8, 4))
            color = "#e74c3c" if kind == "up" else "#3498db"
            bars  = ax.barh(names[::-1], values[::-1], color=color, alpha=0.8)

            # 数値ラベル
            for bar, val in zip(bars, values[::-1]):
                ax.text(
                    bar.get_width() + (0.3 if kind == "up" else -0.3),
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:+.2f}%",
                    va="center",
                    ha="left" if kind == "up" else "right",
                    fontsize=9,
                )

            title = f"値{'上がり' if kind == 'up' else '下がり'}率ランキング（{date_str}）"
            ax.set_title(title, fontsize=12, pad=10)
            ax.set_xlabel("変動率（%）")
            ax.axvline(0, color="gray", linewidth=0.5)
            ax.grid(axis="x", alpha=0.3)
            plt.tight_layout()

            out_path = CHART_DIR / f"{date_str}_{kind}_ranking.png"
            fig.savefig(out_path, dpi=120, bbox_inches="tight")
            plt.close(fig)
            result[f"{kind}_chart"] = out_path
            print(f"  📊 グラフ生成: {out_path.name}")

        return result

    except Exception as e:
        print(f"  ⚠️ ランキンググラフ生成エラー: {e}")
        return {}


def generate_macro_chart(finance_data: dict, date_str: str) -> "Path | None":
    """
    マクロ変動率比較棒グラフを生成する。
    Returns:
        Path（グラフのパス）またはNone
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _setup_font()

        macro  = finance_data.get("macro", {})
        us     = macro.get("us_stocks", {})
        forex  = macro.get("forex", {})
        comm   = macro.get("commodities", {})
        market = finance_data.get("market_summary", {})

        items = []

        # 日経平均（nikkei_change_pct または nikkei_change から抽出）
        nikkei_chg = market.get("nikkei_change_pct")
        if nikkei_chg is None:
            # "前日比: +1234.56(+2.87%)" 形式から抽出
            chg_str = market.get("nikkei_change", "")
            m = re.search(r'\(([+-]?\d+\.?\d*)%\)', chg_str)
            if m:
                nikkei_chg = float(m.group(1))
        if isinstance(nikkei_chg, (int, float)):
            items.append(("日経平均", float(nikkei_chg)))

        # S&P500
        sp_chg = us.get("S&P500", {}).get("change_pct")
        if isinstance(sp_chg, (int, float)):
            items.append(("S&P500", float(sp_chg)))

        # USD/JPY
        usd_chg = forex.get("USD/JPY", {}).get("change_pct")
        if isinstance(usd_chg, (int, float)):
            items.append(("USD/JPY", float(usd_chg)))

        # WTI原油
        wti_chg = comm.get("WTI原油", {}).get("change_pct")
        if isinstance(wti_chg, (int, float)):
            items.append(("WTI原油", float(wti_chg)))

        # 金
        gold_chg = comm.get("金", {}).get("change_pct")
        if isinstance(gold_chg, (int, float)):
            items.append(("金", float(gold_chg)))

        if len(items) < 2:
            print(f"  ⚠️ マクロデータ不足（{len(items)}件）→ グラフ省略")
            return None

        labels = [i[0] for i in items]
        values = [i[1] for i in items]
        colors = ["#e74c3c" if v >= 0 else "#3498db" for v in values]

        fig, ax = plt.subplots(figsize=(8, 4))
        bars = ax.bar(labels, values, color=colors, alpha=0.8, width=0.6)

        # 数値ラベル
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + (0.05 if val >= 0 else -0.15),
                f"{val:+.2f}%",
                ha="center",
                va="bottom" if val >= 0 else "top",
                fontsize=9,
            )

        ax.set_title(f"主要指標 変動率比較（{date_str}）", fontsize=12, pad=10)
        ax.set_ylabel("変動率（%）")
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()

        out_path = CHART_DIR / f"{date_str}_macro.png"
        fig.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"  📊 グラフ生成: {out_path.name}")
        return out_path

    except Exception as e:
        print(f"  ⚠️ マクログラフ生成エラー: {e}")
        return None


def generate_all_charts(finance_data: dict) -> dict:
    """全グラフを生成して返す"""
    date_str = datetime.now().strftime("%Y%m%d")
    result   = {}
    result.update(generate_ranking_chart(finance_data, date_str))
    macro_chart = generate_macro_chart(finance_data, date_str)
    if macro_chart:
        result["macro_chart"] = macro_chart
    return result
