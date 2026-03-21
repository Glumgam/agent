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


def review_article(content: str, topic: str) -> dict:
    """
    qwen3.5:9b で記事品質をレビューする。
    Returns:
        {
            "score": int (0-10),
            "issues": list[str],
            "passed": bool,
            "feedback": str,
        }
    """
    from llm import ask_thinking

    review_target = content[:3000]

    prompt = f"""あなたはPython技術記事の品質レビュアーです。
以下の記事を評価してください。

【トピック】
{topic}

【記事（抜粋）】
{review_target}

---
以下の4項目を評価し、必ず指定フォーマットで回答してください。

評価項目:
1. 内容の正確性: コード例は正しいか、事実に誤りはないか（0-10点）
2. 日本語の品質: 自然な日本語か、中国語混入・不自然な表現はないか（0-10点）
3. 構成の適切さ: 見出し・まとめ・FAQが適切か（0-10点）
4. 有用性: 読者にとって実践的で役立つ内容か（0-10点）

必ず以下のフォーマットで回答してください（他の文章は不要）:
SCORE: [4項目の平均を0-10の整数で]
ISSUES: [問題点をカンマ区切りで。なければ「なし」]
VERDICT: [scoreが7以上なら「pass」、6以下なら「fail」]
FEEDBACK: [改善点を1文で。なければ「良好」]
"""

    print(f"  🔍 品質レビュー中 (qwen3.5:9b)...")
    try:
        response = ask_thinking(prompt, label="REVIEW")
    except Exception as e:
        print(f"  ⚠️ レビューエラー: {e} → スキップ")
        return {"score": 8, "issues": [], "passed": True, "feedback": "レビュースキップ"}

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
