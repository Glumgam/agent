"""
相関変化の継続トラッキングシステム。

機能:
1. 過去の相関データと現在を比較
2. 相関の強化・弱化・逆転を検知
3. 異常な相関変化をアラート
4. トレンド（変化の方向性）を計算

※ 過去データの統計的変化の記録のみ。
※ 将来予測・投資助言は行わない。
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

AGENT_ROOT = Path(__file__).parent
TRACKER_DB = AGENT_ROOT / "memory" / "correlation_tracker.json"
CORR_DIR   = AGENT_ROOT / "knowledge" / "correlation"

# 変化の閾値
CHANGE_THRESHOLDS = {
    "significant": 0.2,   # 有意な変化
    "major":       0.35,  # 大きな変化
    "reversal":    0.0,   # 符号が逆転
}


# =====================================================
# データ管理
# =====================================================

def _load_tracker_db() -> dict:
    """トラッカーDBを読み込む"""
    if TRACKER_DB.exists():
        try:
            return json.loads(TRACKER_DB.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_tracker_db(db: dict):
    """トラッカーDBを保存する"""
    TRACKER_DB.parent.mkdir(exist_ok=True)
    TRACKER_DB.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_correlation_snapshot(
    stock_code: str,
    correlations: dict,
    date: str = None,
):
    """相関データのスナップショットを保存する"""
    db   = _load_tracker_db()
    date = date or datetime.now().strftime("%Y-%m-%d")

    if stock_code not in db:
        db[stock_code] = []

    # 既存の同日データを上書き
    db[stock_code] = [
        s for s in db[stock_code]
        if s.get("date") != date
    ]

    db[stock_code].append({
        "date": date,
        "correlations": {
            k: v.get("corr", 0) if isinstance(v, dict) else v
            for k, v in correlations.items()
        },
    })

    # 最新180日分のみ保持
    db[stock_code] = sorted(
        db[stock_code], key=lambda x: x["date"]
    )[-180:]

    _save_tracker_db(db)


# =====================================================
# 変化検知
# =====================================================

def detect_correlation_changes(
    stock_code: str,
    current_correlations: dict,
    lookback_days: int = 30,
) -> list:
    """
    現在の相関と過去の相関を比較して変化を検知する。

    Returns:
        [{"indicator", "prev_corr", "curr_corr", "change", "type", "message"}]
    """
    db = _load_tracker_db()

    if stock_code not in db or len(db[stock_code]) < 2:
        return []

    snapshots   = db[stock_code]
    cutoff_date = (
        datetime.now() - timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    past_snapshots = [s for s in snapshots if s["date"] <= cutoff_date]
    if not past_snapshots:
        past_snapshots = [snapshots[0]]

    past    = past_snapshots[-1]
    changes = []

    for indicator, curr_info in current_correlations.items():
        curr_corr = curr_info.get("corr", 0) if isinstance(curr_info, dict) else curr_info
        past_corr = past["correlations"].get(indicator)

        if past_corr is None:
            continue

        change     = curr_corr - past_corr
        abs_change = abs(change)

        change_type = _classify_change(past_corr, curr_corr, change)
        if not change_type:
            continue

        message = _format_change_message(
            indicator, past_corr, curr_corr, change, change_type
        )

        changes.append({
            "indicator":  indicator,
            "prev_corr":  round(past_corr, 3),
            "curr_corr":  round(curr_corr, 3),
            "change":     round(change, 3),
            "abs_change": round(abs_change, 3),
            "type":       change_type,
            "message":    message,
            "past_date":  past["date"],
        })

    # 変化の大きい順にソート
    changes.sort(key=lambda x: x["abs_change"], reverse=True)
    return changes


def _classify_change(prev: float, curr: float, change: float) -> str:
    """変化タイプを分類する"""
    abs_change = abs(change)

    # 符号逆転（相関の方向が変わった）
    if prev * curr < 0 and abs(prev) > 0.2 and abs(curr) > 0.2:
        return "reversal"

    # 大きな変化
    if abs_change >= CHANGE_THRESHOLDS["major"]:
        return "major_increase" if change > 0 else "major_decrease"

    # 有意な変化
    if abs_change >= CHANGE_THRESHOLDS["significant"]:
        return "increase" if change > 0 else "decrease"

    return None  # 変化なし


def _format_change_message(
    indicator: str,
    prev: float,
    curr: float,
    change: float,
    change_type: str,
) -> str:
    """変化を自然言語で説明する（断定しない表現）"""
    templates = {
        "reversal": (
            f"**{indicator}との相関が逆転**（{prev:+.2f} → {curr:+.2f}）"
            f" — 過去データ上、連動の方向性が変化している可能性がある"
        ),
        "major_increase": (
            f"**{indicator}との相関が大幅強化**（{prev:+.2f} → {curr:+.2f}、"
            f"+{change:.2f}）"
            f" — 連動性が高まっている傾向が見られる"
        ),
        "major_decrease": (
            f"**{indicator}との相関が大幅低下**（{prev:+.2f} → {curr:+.2f}、"
            f"{change:.2f}）"
            f" — 連動性が弱まっている傾向が見られる"
        ),
        "increase": (
            f"{indicator}との相関が強化（{prev:+.2f} → {curr:+.2f}）"
        ),
        "decrease": (
            f"{indicator}との相関が低下（{prev:+.2f} → {curr:+.2f}）"
        ),
    }
    return templates.get(change_type, "変化検知")


# =====================================================
# トレンド計算
# =====================================================

def calculate_correlation_trend(
    stock_code: str,
    indicator: str,
    window_days: int = 90,
) -> dict:
    """
    相関係数のトレンド（時系列変化）を計算する。

    Returns:
        {"trend": "increasing/decreasing/stable", "slope": float, "data": [...]}
    """
    db = _load_tracker_db()

    if stock_code not in db:
        return {"trend": "data_insufficient", "slope": 0, "data": []}

    snapshots = db[stock_code]
    cutoff    = (
        datetime.now() - timedelta(days=window_days)
    ).strftime("%Y-%m-%d")

    recent = [s for s in snapshots if s["date"] >= cutoff]
    if len(recent) < 5:
        return {"trend": "data_insufficient", "slope": 0, "data": []}

    corr_series = [
        (s["date"], s["correlations"].get(indicator))
        for s in recent
        if s["correlations"].get(indicator) is not None
    ]

    if len(corr_series) < 5:
        return {"trend": "data_insufficient", "slope": 0, "data": corr_series}

    values = np.array([v for _, v in corr_series])
    x      = np.arange(len(values))
    slope  = float(np.polyfit(x, values, 1)[0])

    if abs(slope) < 0.002:
        trend = "stable"
    elif slope > 0:
        trend = "increasing"
    else:
        trend = "decreasing"

    return {
        "trend":  trend,
        "slope":  round(slope, 4),
        "data":   corr_series[-30:],  # 最新30件
        "latest": round(float(values[-1]), 3),
        "oldest": round(float(values[0]), 3),
    }


# =====================================================
# 異常検知
# =====================================================

def detect_anomalies(
    stock_code: str,
    current_correlations: dict,
    z_threshold: float = 2.0,
) -> list:
    """
    統計的に異常な相関値を検知する（Zスコアベース）。
    """
    db = _load_tracker_db()

    if stock_code not in db or len(db[stock_code]) < 10:
        return []

    anomalies = []
    snapshots = db[stock_code]

    for indicator, curr_info in current_correlations.items():
        curr_corr = curr_info.get("corr", 0) if isinstance(curr_info, dict) else curr_info

        historical = [
            s["correlations"].get(indicator)
            for s in snapshots
            if s["correlations"].get(indicator) is not None
        ]

        if len(historical) < 10:
            continue

        hist_arr = np.array(historical)
        mean     = float(np.mean(hist_arr))
        std      = float(np.std(hist_arr))

        if std < 0.01:
            continue

        z_score = (curr_corr - mean) / std

        if abs(z_score) >= z_threshold:
            anomalies.append({
                "indicator": indicator,
                "curr_corr": round(curr_corr, 3),
                "mean_corr": round(mean, 3),
                "z_score":   round(z_score, 3),
                "message": (
                    f"{indicator}との相関が統計的に異常な水準"
                    f"（現在: {curr_corr:+.2f}、"
                    f"過去平均: {mean:+.2f}、"
                    f"Zスコア: {z_score:+.1f}）"
                ),
            })

    return anomalies


# =====================================================
# トレンドチャート生成
# =====================================================

def generate_trend_chart(
    stock_code: str,
    stock_name: str,
    indicators: list,
    output_path: Path = None,
) -> Path:
    """相関係数の時系列トレンドチャートを生成する"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        # 日本語フォント設定（correlation_analyzerと同じロジック）
        from correlation_analyzer import _setup_japanese_font
        _setup_japanese_font()

        db = _load_tracker_db()
        if stock_code not in db or len(db[stock_code]) < 3:
            return None

        snapshots = db[stock_code][-60:]  # 最新60件
        dates     = [s["date"] for s in snapshots]

        fig, ax = plt.subplots(figsize=(12, 5))
        colors  = ["#1976d2", "#e65100", "#388e3c", "#7b1fa2", "#f57f17"]

        for i, indicator in enumerate(indicators[:5]):
            values = [
                s["correlations"].get(indicator)
                for s in snapshots
            ]
            valid = [(d, v) for d, v in zip(dates, values) if v is not None]
            if len(valid) < 3:
                continue

            x_vals = list(range(len(valid)))
            y_vals = [v for _, v in valid]
            color  = colors[i % len(colors)]

            ax.plot(x_vals, y_vals, label=indicator,
                    color=color, linewidth=2, marker="o", markersize=3)

        ax.axhline(y=0,    color="black", linewidth=0.8)
        ax.axhline(y=0.5,  color="gray",  linewidth=0.5, linestyle="--", alpha=0.5)
        ax.axhline(y=-0.5, color="gray",  linewidth=0.5, linestyle="--", alpha=0.5)
        ax.axhline(y=0.7,  color="gray",  linewidth=0.5, linestyle=":",  alpha=0.3)
        ax.axhline(y=-0.7, color="gray",  linewidth=0.5, linestyle=":",  alpha=0.3)

        ax.set_ylim(-1.1, 1.1)
        ax.set_ylabel("相関係数", fontsize=11)
        ax.set_xlabel("日数（古→新）", fontsize=10)
        ax.legend(loc="upper right", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_title(f"{stock_name} の相関係数トレンド", fontsize=13)

        fig.text(
            0.5, 0.01,
            "※ 過去データの統計的変化です。将来の価格動向を保証するものではありません。",
            ha="center", fontsize=8, color="gray",
        )
        plt.tight_layout(rect=[0, 0.04, 1, 1])

        if not output_path:
            from correlation_analyzer import CHART_DIR
            CHART_DIR.mkdir(parents=True, exist_ok=True)
            date_str    = datetime.now().strftime("%Y%m%d")
            output_path = CHART_DIR / f"{date_str}_{stock_name}_trend.png"

        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  🖼️  トレンドチャート: {output_path.name}")
        return output_path

    except Exception as e:
        print(f"  ⚠️ トレンドチャートエラー: {e}")
        return None


# =====================================================
# メイン処理
# =====================================================

def track_and_analyze(
    stock_code: str,
    current_correlations: dict,
    stock_name: str = None,
) -> dict:
    """
    相関データを保存してトラッキング分析を実行する。
    """
    # スナップショット保存
    save_correlation_snapshot(stock_code, current_correlations)

    # 変化検知
    changes = detect_correlation_changes(stock_code, current_correlations)

    # 異常検知
    anomalies = detect_anomalies(stock_code, current_correlations)

    # トレンド計算（上位3指標）
    top_indicators = list(current_correlations.keys())[:3]
    trends = {}
    for ind in top_indicators:
        trends[ind] = calculate_correlation_trend(stock_code, ind)

    # トレンドチャート生成（スナップショットが3件以上あれば）
    chart = None
    if stock_name and len(_load_tracker_db().get(stock_code, [])) >= 3:
        chart = generate_trend_chart(stock_code, stock_name, top_indicators)

    result = {
        "stock_code":  stock_code,
        "stock_name":  stock_name or stock_code,
        "changes":     changes,
        "anomalies":   anomalies,
        "trends":      trends,
        "chart":       str(chart) if chart else None,
        "analyzed_at": datetime.now().isoformat(),
    }

    # 重要な変化をログ
    if changes:
        print(f"  🔔 {stock_name}: {len(changes)}件の相関変化を検知")
        for c in changes[:2]:
            print(f"     {c['message'][:70]}")

    if anomalies:
        print(f"  ⚡ {stock_name}: {len(anomalies)}件の異常検知")

    return result


def format_tracking_for_article(tracking_results: list) -> str:
    """トラッキング結果を記事用テキストに変換する"""
    lines = [
        "## 🔔 相関変化トラッキング（前回比）\n",
        "> ⚠️ 以下は過去データの統計的変化の記録です。",
        "> 将来の株価動向を示すものではありません。\n",
    ]

    has_content = False

    for result in tracking_results:
        name      = result.get("stock_name", result.get("stock_code", ""))
        changes   = result.get("changes", [])
        anomalies = result.get("anomalies", [])
        trends    = result.get("trends", {})
        chart     = result.get("chart")

        if not (changes or anomalies):
            continue

        has_content = True
        lines.append(f"### {name}")

        # 重要な変化
        if changes:
            lines.append("**相関変化:**")
            for c in changes[:3]:
                tag = (
                    "🔴" if c["type"] == "reversal" else
                    "🟠" if "major" in c["type"] else
                    "🟡"
                )
                lines.append(f"- {tag} {c['message']}")
            lines.append("")

        # 異常検知
        if anomalies:
            lines.append("**統計的異常:**")
            for a in anomalies[:2]:
                lines.append(f"- ⚡ {a['message']}")
            lines.append("")

        # トレンドサマリー
        trend_summary = []
        for ind, trend in trends.items():
            t = trend.get("trend", "")
            if t == "increasing":
                trend_summary.append(f"{ind}: 相関強化傾向")
            elif t == "decreasing":
                trend_summary.append(f"{ind}: 相関弱化傾向")

        if trend_summary:
            lines.append("**トレンド:**")
            for s in trend_summary:
                lines.append(f"- {s}")
            lines.append("")

        # チャート
        if chart:
            lines.append(f"![{name}相関トレンド]({chart})\n")

    if not has_content:
        lines.append(
            "前回比較データが蓄積中です（初回実行時は変化検知なし）。\n"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="相関変化トラッキング")
    parser.add_argument("--code",  default="7203", help="銘柄コード")
    parser.add_argument("--name",  default="",     help="銘柄名")
    parser.add_argument("--days",  type=int, default=60, help="相関計算日数")
    args = parser.parse_args()

    from correlation_analyzer import calculate_correlation
    corr   = calculate_correlation(args.code, days=args.days)
    result = track_and_analyze(args.code, corr, args.name or args.code)

    print(f"\n変化: {len(result['changes'])}件  異常: {len(result['anomalies'])}件")
    for c in result["changes"]:
        print(f"  {c['message']}")
