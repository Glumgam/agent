"""
技術記事自動生成システム。
RAGを使って最新情報を補完しながら
Python・技術ネタの記事を自動生成する。
出力: content/YYYYMMDD_{slug}.md
"""
import re
import json
import unicodedata
from pathlib import Path
from datetime import datetime

AGENT_ROOT   = Path(__file__).parent
CONTENT_DIR  = AGENT_ROOT / "content"
PERF_LOG     = AGENT_ROOT / "memory" / "content_log.json"

# 技術記事のジャンル定義
TECH_GENRES = [
    {
        "id":       "python_tips",
        "label":    "Python実践テクニック",
        "queries":  ["Python tips 2026", "Python best practices"],
        "template": "tips",
    },
    {
        "id":       "ai_tools",
        "label":    "AIツール活用法",
        "queries":  ["AI agent tool 2026", "LLM automation Python"],
        "template": "tutorial",
    },
    {
        "id":       "library_intro",
        "label":    "Pythonライブラリ紹介",
        "queries":  ["Python new library 2026", "Python productivity tool"],
        "template": "introduction",
    },
    {
        "id":       "automation",
        "label":    "Python自動化",
        "queries":  ["Python automation script 2026", "Python workflow automation"],
        "template": "tutorial",
    },
]

# 全テンプレートに適用する品質ルール
_QUALITY_RULES = """
【絶対条件】
- 必ず最初の行を「# 記事タイトル」の形式で始めること（例: # Pythonで並列処理を実装する3つの方法）
- 最低1500文字以上で書くこと（これより短い場合は失敗とみなす）
- ## 見出しを最低3つ以上含めること
- コード例（```python）を最低2つ以上含めること
- 記事と無関係なコード（Flask、JWT等）は絶対に含めないこと

【品質ルール（必ず守ること）】
1. プレースホルダー禁止: 「よくある質問1」「回答」のような仮の内容は絶対に書かない
2. 繰り返し禁止: 同じコード例や説明を複数セクションで繰り返さない
3. 具体性必須: 全てのコード例は実際に動作する具体的なコードにする
4. FAQ必須: 実際に初心者が疑問に思う具体的な質問と回答を3〜5個書く
5. 比較必須（比較記事の場合）: 表形式での比較を必ず含める
6. 文字数: 2500文字以上を目標にする

"""

# 記事テンプレート
ARTICLE_TEMPLATES = {
    "tips": """
以下の情報を使って、Pythonエンジニア向けの実践的なtips記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}
記事の構成:
# {topic}
## はじめに
（なぜこのテクニックが重要か、2〜3文）
## 基本的な使い方
（コード例付きで説明）
## 実践例
（実際のユースケースとコード例）
## 応用テクニック
基本の使い方を理解した上で、実務でよく使われる
上級者向けのパターンやテクニックを説明してください。
基本的な使い方の繰り返しではなく、
実務で役立つ発展的な内容にすること。
コード例を必ず含めること。
## いつ使うべきか（使い分けガイド）
以下の観点で使い分けを表形式で示してください（該当する場合）。
具体的な比較表を含めること。
## まとめ
この記事で学んだことを5点以上の箇条書きにまとめてください。
単なる特徴の羅列ではなく、「〜する場合は〜を使う」という
実践的な判断基準を含めること。
## FAQ
このトピックに関してよくある疑問を3〜5個、具体的に考えて
Q&A形式で書いてください。
「よくある質問1」のようなプレースホルダーは絶対に使わないこと。
実際に初心者が疑問に思うことを具体的に書くこと。
制約:
- 2500文字以上
- コード例を必ず含める
- 日本語で書く
- Markdownフォーマット
""",
    "tutorial": """
以下の情報を使って、Pythonエンジニア向けのチュートリアル記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}
記事の構成:
# {topic}
## この記事でわかること
（箇条書き3〜5点）
## 環境準備
（必要なライブラリのインストール方法）
## ステップ1: 基礎実装
（コード例付き）
## ステップ2: 機能追加
（基礎実装とは別の新しいコード例付き）
## ステップ3: 実用化
（完成コードと説明）
## トラブルシューティング
実際によく起きるエラーと具体的な対処法を3件以上書くこと。
「エラー例1」のようなプレースホルダーは使わないこと。
## FAQ
このトピックに関してよくある疑問を3〜5個、具体的に考えて
Q&A形式で書いてください。
実際に初心者が疑問に思うことを具体的に書くこと。
## まとめ
制約:
- 2500文字以上
- 各ステップにコード例を含める
- 日本語で書く
- Markdownフォーマット
""",
    "introduction": """
以下の情報を使って、Pythonライブラリの紹介記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}
記事の構成:
# {topic}
## このライブラリとは
（概要と特徴）
## インストール方法
```bash
pip install xxx
```
## 基本的な使い方
（コード例付き）
## 実践サンプル
（実際に使えるコード例）
## 類似ライブラリとの比較
具体的なライブラリ名を挙げて表形式で比較してください。
| 観点 | このライブラリ | 代替ライブラリ |
のような表を必ず含めること。
## FAQ
このトピックに関してよくある疑問を3〜5個、具体的に考えて
Q&A形式で書いてください。
実際に初心者が疑問に思うことを具体的に書くこと。
## まとめ
この記事で学んだことを5点以上の箇条書きにまとめてください。
「〜する場合は〜を使う」という実践的な判断基準を含めること。
制約:
- 2500文字以上
- 実用的なコード例を必ず含める
- 日本語で書く
- Markdownフォーマット
""",
}


# --- QUALITY FILTER START ---
def _quality_check(content: str) -> tuple:
    """
    記事の品質をチェックする。
    Returns: (passed: bool, reason: str)
    """
    if not content or len(content) < 1500:
        return False, f"文字数不足: {len(content) if content else 0}文字（最低1500文字）"
    # 最初の非空行が # タイトルであることを確認
    first_line = next((l for l in content.split("\n") if l.strip()), "")
    if not first_line.startswith("# "):
        return False, f"タイトル行なし（最初の行が '# 記事タイトル' 形式でない）: {first_line[:50]!r}"
    heading_count = content.count("\n## ")
    if heading_count < 3:
        return False, f"見出し不足: {heading_count}個（最低3個）"
    if "```python" not in content and "```bash" not in content:
        return False, "コードブロックなし（最低1個必要）"
    if "## まとめ" not in content:
        return False, "まとめセクションなし"
    return True, "OK"
# --- QUALITY FILTER END ---


# --- CJK FILTER START ---
_ZH_REPLACEMENTS = {
    "网络": "ネットワーク",
    "环境": "環境",
    "连接": "接続",
    "安装": "インストール",
    "运行": "実行",
    "错误": "エラー",
    "程序": "プログラム",
    "文件": "ファイル",
    "数据": "データ",
    "系统": "システム",
    "接口": "インターフェース",
    "库": "ライブラリ",
    "模型": "モデル",
    "语言": "言語",
    "代码": "コード",
    "功能": "機能",
    "方法": "メソッド",
    "类": "クラス",
    "对象": "オブジェクト",
    "变量": "変数",
}

_ZH_DETECT_PATTERNS = [
    "网络", "环境", "连接", "安装", "运行", "错误",
    "程序", "文件", "数据", "系统", "接口",
]


def _remove_chinese_chars(text: str) -> str:
    """
    中国語固有の文字を除去または日本語に置換する。
    qwen2.5-coder:7b が中国語文字を混入するバグへの対策。
    """
    for zh, ja in _ZH_REPLACEMENTS.items():
        text = text.replace(zh, ja)
    return text


def _quality_check_v2(content: str) -> tuple:
    """品質チェック + 中国語文字検出"""
    passed, reason = _quality_check(content)
    if not passed:
        return passed, reason
    found = [p for p in _ZH_DETECT_PATTERNS if p in content]
    if found:
        return False, f"中国語文字が混入: {found}"
    return True, "OK"
# --- CJK FILTER END ---


# --- MONETIZATION FOOTER START ---
_FOOTER_TEMPLATE = """
---
## 🛠️ この記事で紹介した環境・ツール
| ツール | 用途 | 入手先 |
|--------|------|--------|
| Python | プログラミング言語 | python.org |
| VS Code | コードエディタ | code.visualstudio.com |
| Ollama | ローカルLLM実行 | ollama.ai |

## 📚 関連記事
- Pythonで始めるAI開発
- ローカルLLMの活用法
- 自動化スクリプトの作り方

---
*この記事はAIエージェントによって自動生成されました。*
*誤りや改善点があればコメントでお知らせください。*
"""


def _add_footer(content: str, topic: str) -> str:
    """記事末尾に収益導線フッターを追加する"""
    if "この記事で紹介した環境" in content:
        return content  # 既にフッターがある場合はスキップ
    return content + _FOOTER_TEMPLATE
# --- MONETIZATION FOOTER END ---


# --- TOPIC KNOWLEDGE START ---
def _get_topic_knowledge(topic: str) -> str:
    """
    トピックに応じた正確な技術知識を返す。
    RAGが取得できない場合の補完として使用する。
    """
    topic_lower = topic.lower()
    if "ollama" in topic_lower:
        return """
【Ollamaの正確な使い方】
- Ollamaはapi_keyが不要。ローカルで動作する。
- Pythonからの呼び出し例:
  import requests
  response = requests.post('http://localhost:11434/api/generate',
      json={"model": "qwen2.5-coder:7b", "prompt": "Hello", "stream": False})
  print(response.json()["response"])
- または公式ライブラリ:
  import ollama
  response = ollama.generate(model='llama2', prompt='Hello')
  print(response['response'])
- モデル一覧取得: ollama.list()
- チャット形式: ollama.chat(model='llama2', messages=[...])
"""
    if "fastapi" in topic_lower or "flask" in topic_lower:
        return """
【WebフレームワークAPIの正確な使い方】
- Flask: from flask import Flask, jsonify; app = Flask(__name__)
- FastAPI: from fastapi import FastAPI; app = FastAPI()
- どちらもapi_keyは不要（ローカル開発時）
"""
    return ""
# --- TOPIC KNOWLEDGE END ---


def generate_article(
    topic: str,
    genre_id: str = "python_tips",
    extra_context: str = "",
    max_retries: int = 3,
) -> dict:
    """
    RAGを使って技術記事を生成する。
    Args:
        topic:         記事のトピック
        genre_id:      ジャンルID
        extra_context: 追加コンテキスト
        max_retries:   生成リトライ上限（デフォルト3）
    Returns:
        {"title", "content", "path", "rag_hits", "word_count"}
    """
    print(f"\n  📝 記事生成: {topic}")

    # RAGで関連情報を取得
    rag_context = ""
    rag_hits    = 0
    try:
        from rag_retriever import search, format_context
        results     = search(topic, top_k=4)
        rag_context = format_context(results, max_chars=2000)
        rag_hits    = len(results)
        if rag_context:
            # 無関係コードの混入チェック
            noise_patterns = [
                "return jsonify", "app.route", "@app.",
                "JWT", "client.generate(text=", "{'error':",
            ]
            if any(p in rag_context for p in noise_patterns):
                print(f"  ⚠️ RAGコンテキストに無関係コード混入 → スキップ")
                rag_context = ""
                rag_hits    = 0
            else:
                print(f"  📚 RAG: {rag_hits}件の関連知識を注入")
    except Exception as e:
        print(f"  ⚠️ RAGスキップ: {e}")

    # コンテキストを合成
    context = ""
    # トピック固有知識を注入（RAGより優先して先頭に配置）
    topic_knowledge = _get_topic_knowledge(topic)
    if topic_knowledge:
        context += topic_knowledge + "\n\n"
        print(f"  📖 トピック知識を注入: {topic[:30]}")
    if rag_context:
        context += f"【最新情報・公式ドキュメント】\n{rag_context}\n\n"
    if extra_context:
        context += f"【追加情報】\n{extra_context}\n"
    if not context:
        context = "（関連情報なし：一般的な知識で補完してください）"

    # テンプレート選択
    genre    = next((g for g in TECH_GENRES if g["id"] == genre_id), TECH_GENRES[0])
    template = ARTICLE_TEMPLATES.get(genre["template"], ARTICLE_TEMPLATES["tips"])
    prompt   = _QUALITY_RULES + template.format(topic=topic, context=context[:3000])

    # 記事生成（品質チェック付きリトライあり）
    from llm import ask_plain
    content = ""
    for attempt in range(max_retries):
        print(f"  🧠 生成中 (qwen2.5-coder:7b)"
              f"{' 再試行 ' + str(attempt) if attempt > 0 else ''}...")
        content = ask_plain(prompt)
        # 中国語文字を除去（置換リストで対応済みの文字を日本語化）
        content = _remove_chinese_chars(content)
        passed, reason = _quality_check_v2(content)
        if passed:
            break
        if attempt < max_retries - 1:
            print(f"  ⚠️ 品質不足: {reason} → リトライ {attempt + 1}/{max_retries - 1}")
            prompt = (
                prompt
                + f"\n\n【重要・再試行{attempt + 1}回目】\n"
                + f"前回の出力が品質基準を満たしませんでした。理由: {reason}\n"
                + "必ず1500文字以上・見出し(##)3個以上・コード例(```python)1個以上"
                + "・まとめセクションを含めてください。"
                + "\n必ず日本語で書いてください。中国語（简体字）は絶対に使わないこと。"
            )
        else:
            print(f"  ❌ 品質基準未達: {reason}")
            return {"error": f"品質基準未達: {reason}"}

    # フッターを追加
    content = _add_footer(content, topic)

    # ファイル保存
    path = _save_article(topic, content)

    # メタデータ記録
    result = {
        "title":        topic,
        "genre":        genre_id,
        "content":      content,
        "path":         str(path),
        "rag_hits":     rag_hits,
        "word_count":   len(content),
        "generated_at": datetime.now().isoformat(),
    }
    _log_performance(result)
    print(f"  ✅ 生成完了: {path.name} ({len(content)}文字)")

    # Qdrantクライアントの明示的クローズ（終了時 __del__ エラー抑制）
    try:
        import rag_retriever
        if rag_retriever._qdrant_client is not None:
            rag_retriever._qdrant_client.close()
            rag_retriever._qdrant_client = None  # __del__ 二重呼び出し防止
    except Exception:
        pass

    return result


def _save_article(topic: str, content: str) -> Path:
    """記事をMarkdownファイルとして保存する"""
    CONTENT_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    slug     = re.sub(r"[^\w\s-]", "", topic.lower())
    slug     = re.sub(r"\s+", "_", slug.strip())[:30] or "article"
    filename = f"{date_str}_{slug}.md"
    path     = CONTENT_DIR / filename
    counter  = 1
    while path.exists():
        path    = CONTENT_DIR / f"{date_str}_{slug}_{counter}.md"
        counter += 1
    path.write_text(content, encoding="utf-8")
    return path


def _log_performance(result: dict):
    """生成ログを記録する"""
    PERF_LOG.parent.mkdir(exist_ok=True)
    logs = []
    if PERF_LOG.exists():
        try:
            logs = json.loads(PERF_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    log_entry = {k: v for k, v in result.items() if k != "content"}
    # 品質チェック結果を追加
    passed, reason = _quality_check(result.get("content", ""))
    log_entry["quality_passed"] = passed
    log_entry["quality_reason"] = reason
    logs.append(log_entry)
    logs = logs[-500:]
    PERF_LOG.write_text(
        json.dumps(logs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def show_content_stats() -> str:
    """生成コンテンツの統計を表示する"""
    if not PERF_LOG.exists():
        return "生成記事なし"
    logs  = json.loads(PERF_LOG.read_text(encoding="utf-8"))
    files = list(CONTENT_DIR.glob("*.md")) if CONTENT_DIR.exists() else []
    lines = [
        f"## 📝 コンテンツ統計",
        f"生成記事数: {len(files)}件",
        f"総生成数:   {len(logs)}件",
    ]
    if logs:
        avg_words    = sum(l.get("word_count", 0) for l in logs) / len(logs)
        avg_rag      = sum(l.get("rag_hits",   0) for l in logs) / len(logs)
        quality_pass = sum(1 for l in logs if l.get("quality_passed", True))
        lines.append(f"平均文字数: {avg_words:.0f}文字")
        lines.append(f"平均RAGヒット: {avg_rag:.1f}件")
        lines.append(f"品質通過率: {quality_pass}/{len(logs)} ({quality_pass / len(logs) * 100:.0f}%)")
        lines.append("")
        lines.append("### 最新5件")
        for log in reversed(logs[-5:]):
            lines.append(
                f"- {log.get('generated_at','')[:10]} "
                f"{log.get('title','')[:40]} "
                f"({log.get('word_count',0)}文字)"
            )
    return "\n".join(lines)
