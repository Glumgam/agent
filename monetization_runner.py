"""
コンテンツ自動生成ランナー。
research_agent の収集結果をもとに
技術記事を自動生成してローカルに保存する。
使い方:
  python monetization_runner.py            # ランダムジャンルで1記事
  python monetization_runner.py --genre python_tips  # 特定ジャンル
  python monetization_runner.py --topic "FastAPIの使い方"  # トピック指定
  python monetization_runner.py --all      # 全ジャンル1記事ずつ
  python monetization_runner.py --stats    # 統計表示
"""
import json
import argparse
import random
from pathlib import Path
from datetime import datetime

AGENT_ROOT   = Path(__file__).parent
TOPICS_CACHE = AGENT_ROOT / "memory" / "content_topics_cache.json"

# ジャンル別トピックの種（RAGで補完される）
SEED_TOPICS = {
    "python_tips": [
        "Pythonのデコレータを使いこなす実践テクニック",
        "Python型ヒントの活用で保守性を上げる方法",
        "Pythonの内包表記とジェネレータの使い分け",
        "Pythonで並列処理を実装する3つの方法",
        "Pythonのコンテキストマネージャを自作する方法",
        "Pythonのデータクラスとnamedtupleの使い分け",
        "Pythonのpathlib完全活用ガイド",
        "Pythonのloggingモジュール実践入門",
    ],
    "ai_tools": [
        "OllamaでローカルLLMを動かす完全ガイド",
        "PythonでAIエージェントを自作する方法",
        "LangChainなしでRAGを実装する方法",
        "qwen2.5-coderでコード補完を自動化する",
        "Sentence Transformersでテキスト検索を実装する",
        "OllamaのモデルをPythonから使う実践ガイド",
    ],
    "library_intro": [
        "httpxでモダンなHTTPクライアントを実装する",
        "richでPythonのCLI出力を美しくする",
        "typerでPython CLIツールを簡単に作る",
        "pydanticでPythonのデータ検証を強化する",
        "scheduleでPythonのタスクスケジューリングを実装する",
        "loguruでPythonのログ管理を改善する",
    ],
    "automation": [
        "PythonでファイルをGit自動管理する方法",
        "Pythonで毎日の作業を自動化するスクリプト",
        "PythonでWebスクレイピングを自動化する方法",
        "PythonでExcelレポートを自動生成する",
        "PythonでAPIデータを自動収集・保存する方法",
    ],
}


def select_topic(genre_id: str) -> str:
    """未生成のトピックをランダムに選ぶ"""
    generated = set()
    perf_log  = AGENT_ROOT / "memory" / "content_log.json"
    if perf_log.exists():
        try:
            logs      = json.loads(perf_log.read_text(encoding="utf-8"))
            generated = {l.get("title", "") for l in logs}
        except Exception:
            pass
    candidates = SEED_TOPICS.get(genre_id, SEED_TOPICS["python_tips"])
    remaining  = [t for t in candidates if t not in generated]
    if not remaining:
        remaining = candidates
    return random.choice(remaining)


def run_single(genre_id: str = None, topic: str = None) -> dict:
    """1記事を生成する"""
    from content_generator import generate_article, TECH_GENRES
    if not genre_id:
        genre_id = random.choice([g["id"] for g in TECH_GENRES])
    if not topic:
        topic = select_topic(genre_id)
    print(f"\n{'='*50}")
    print(f"  コンテンツ生成")
    print(f"  ジャンル: {genre_id}")
    print(f"  トピック: {topic}")
    print(f"{'='*50}")
    return generate_article(topic=topic, genre_id=genre_id)


def run_all() -> list:
    """全ジャンルで1記事ずつ生成する"""
    from content_generator import TECH_GENRES
    results = []
    for genre in TECH_GENRES:
        result = run_single(genre_id=genre["id"])
        results.append(result)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="コンテンツ自動生成ランナー")
    parser.add_argument("--genre", help="ジャンルID")
    parser.add_argument("--topic", help="トピック（手動指定）")
    parser.add_argument("--all",   action="store_true", help="全ジャンル実行")
    parser.add_argument("--stats", action="store_true", help="統計表示")
    args = parser.parse_args()

    if args.stats:
        from content_generator import show_content_stats
        print(show_content_stats())
    elif args.all:
        results = run_all()
        success = sum(1 for r in results if "error" not in r)
        print(f"\n完了: {success}/{len(results)}件生成")
    else:
        result = run_single(genre_id=args.genre, topic=args.topic)
        if "error" in result:
            print(f"❌ 失敗: {result['error']}")
        else:
            print(f"✅ 完了: {result['path']}")
