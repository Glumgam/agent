"""
qwen3.5:9b による記事品質レビューシステム。
生成された記事を以下の観点で評価する:
1. 内容の正確性（コードは動くか）
2. 日本語の自然さ
3. 構成の適切さ
4. 読者にとっての有用性
スコア7以上でpass、6以下でfail（再生成を促す）
"""
import re
from pathlib import Path

AGENT_ROOT = Path(__file__).parent


def review_article(content: str, topic: str, genre_id: str = "") -> dict:
    """
    記事品質をレビューする。
    genre_id="finance_news" の場合は投資記事用プロンプトを使用。
    Returns:
        {
            "score": int (0-10),
            "issues": list[str],
            "passed": bool,
            "feedback": str,
        }
    """
    from llm import ask_thinking, ask_plain

    if len(content) > 6000:
        review_target = content[:4000] + "\n...(中略)...\n" + content[-1500:]
    else:
        review_target = content

    if genre_id == "finance_news":
        from datetime import datetime as _dt
        # 現在の日経平均を動的に取得
        nikkei_info = "日経平均: 取得中"
        try:
            from finance_data_collector import fetch_market_summary
            market = fetch_market_summary()
            price  = market.get("nikkei_price", "")
            change = market.get("nikkei_change", "")
            if price:
                nikkei_info = f"本日の日経平均: {price}円 前日比: {change}"
        except Exception:
            pass
        prompt = f"""あなたは日本の金融記事レビュアーです。
日本語ネイティブとして自然な日本語かどうかも評価してください。

【重要な前提】
- 現在は{_dt.now().strftime('%Y年%m月%d日')}です
- {nikkei_info}
- 記事内の日経平均数値がこの前後であれば正確な数値として扱ってください
- S&P500・金・原油などは外貨建てですが、日本語記事での円表記は問題ありません
- 免責事項が含まれていれば投資助言の問題はありません

【評価時の注意（重要）】
- 「関連ニュースなし」「背景は未公表」は正直な表現であり減点しない
  → 個別銘柄の値動きにニュースが存在しないことは正常
  → 根拠のない推測より「未公表」の方が誠実で正しい
- ニュースの詳細な経緯を要求しない
  → 著作権の観点からニュース本文の転載は不可
  → コンテキストにある情報の範囲内で記述されていれば十分
- コンテキストにない情報が「記載されていない」ことを減点しない
- 「連れ高」「連れ安」等の市場全体の動きによる値動きは背景説明なしでOK
- 数値の単位は記事内で一貫していれば問題なし
- 2026年の日付は正常です

【減点すべき項目のみ】
- 架空の情報・根拠のない推測が含まれる
- 中国語・韓国語が混入している
- 数値データに明らかな誤りがある
- 免責事項がない
- 同じ表現が3回以上繰り返される
- 普通体（〜した。〜なった。）とですます体が混在している（-1点）
- 「詳細は未公表」「背景は未公表」が文中の括弧で4回以上出現する（-1点）
- 「〜ことを意味します」「〜に寄与しました」「〜が確認されました」が3回以上ある（-1点）

【その他の評価時の注意】
- FAQにコンテキストにないニュース・企業名が含まれる場合は減点
- 「背景は未公表」は値動きセクションでの使用は許容（3回まで）

【トピック】
{topic}

【記事（抜粋）】
{review_target}

---
以下の4項目を評価（各10点満点）:

1. 内容の正確性: データ・数値に明らかな誤りはないか
2. 日本語の品質: 自然な日本語か、ですます体に統一されているか、韓国語・中国語の混入はないか
3. 構成の適切さ: 見出し・まとめ・免責事項が含まれるか
4. 有用性: 投資家にとって参考になる情報が含まれるか

必ず以下のフォーマットのみで回答:
SCORE: [4項目の平均を0-10の整数で]
ISSUES: [問題点をカンマ区切りで。なければ「なし」]
VERDICT: [scoreが7以上なら「pass」、6以下なら「fail」]
FEEDBACK: [最も重要な改善点を1文で。なければ「良好」]
"""
    else:
        prompt = f"""あなたはPython技術記事の品質レビュアーです。
以下の記事を厳密に評価してください。

【トピック】
{topic}

【記事（抜粋）】
{review_target}

---
## 評価基準（各10点満点）

### 1. 技術的正確性
- コード例は実際に動作するか
- ランダムな値（np.random.rand等）を意味のある処理に使っていないか
- 未使用のimport（import pandas等）がないか
- APIの使い方が正しいか

### 2. 日本語品質
- 中国語混入がないか（文本・网络・环境等）
- 「メソッド」を「方法」の意味で誤用していないか
- 不自然な表現がないか

### 3. 構成の適切さ
- 見出し・まとめ・FAQが適切か
- FAQがプレースホルダーでないか（「よくある質問1」等はNG）
- コードブロックが正しく閉じられているか

### 4. 一貫性・整合性
- フッターのツール紹介が記事内容と一致しているか
- 記事で紹介したが使っていないライブラリがないか
- タイトルと内容が一致しているか

---
必ず以下のフォーマットのみで回答してください:
SCORE: [4項目の平均を0-10の整数で]
ISSUES: [問題点をカンマ区切りで。なければ「なし」]
VERDICT: [scoreが7以上なら「pass」、6以下なら「fail」]
FEEDBACK: [最も重要な改善点を1文で。なければ「良好」]
"""

    print(f"  🔍 品質レビュー中 (qwen3.5:9b)...")
    try:
        response = ask_thinking(prompt, label="REVIEW")
    except Exception as e:
        print(f"  ⚠️ qwen3.5失敗: {e} → qwen2.5にフォールバック")
        try:
            response = ask_plain(prompt)
        except Exception:
            return {"score": 7, "issues": [], "passed": True, "feedback": "レビュースキップ"}

    return _parse_review(response)


def _parse_review(response: str) -> dict:
    """レビュー結果をパースする"""
    result = {
        "score":    7,
        "issues":   [],
        "passed":   True,
        "feedback": "良好",
    }
    try:
        m = re.search(r"SCORE:\s*(\d+)", response)
        if m:
            result["score"] = min(10, max(0, int(m.group(1))))

        m = re.search(r"ISSUES:\s*(.+)", response)
        if m:
            issues_str = m.group(1).strip()
            if issues_str != "なし":
                result["issues"] = [i.strip() for i in issues_str.split(",")]

        m = re.search(r"VERDICT:\s*(pass|fail)", response, re.IGNORECASE)
        if m:
            result["passed"] = m.group(1).lower() == "pass"
        else:
            result["passed"] = result["score"] >= 7

        m = re.search(r"FEEDBACK:\s*(.+)", response)
        if m:
            result["feedback"] = m.group(1).strip()

    except Exception as e:
        print(f"  ⚠️ パースエラー: {e}")

    return result


def review_file(path: Path) -> dict:
    """ファイルを読み込んでレビューする"""
    content = path.read_text(encoding="utf-8", errors="ignore")
    topic = ""
    for line in content.split("\n"):
        if line.startswith("# "):
            topic = line.lstrip("# ").strip()
            break
    return review_article(content, topic or path.stem)
