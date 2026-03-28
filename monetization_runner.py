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
from datetime import datetime, date

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

# 投資系トピックは実行時に日付を埋め込む（遅延評価）
def _finance_topics() -> list:
    _d = datetime.now()
    return [
        f"本日の日本株市況まとめ（{_d.strftime('%Y年%m月%d日')}）",
        f"今週の株主優待・株式分割情報（{_d.strftime('%Y年%m月第%W週')}）",
        f"値上がり率ランキング解説（{_d.strftime('%Y年%m月%d日')}）",
        f"値下がり率ランキング解説（{_d.strftime('%Y年%m月%d日')}）",
        f"今週の配当・優待情報まとめ（{_d.strftime('%Y年%m月')}）",
    ]


def select_topic(genre_id: str) -> str:
    """未生成・未飽和のトピックをランダムに選ぶ"""
    generated = set()
    perf_log  = AGENT_ROOT / "memory" / "content_log.json"
    if perf_log.exists():
        try:
            logs      = json.loads(perf_log.read_text(encoding="utf-8"))
            generated = {l.get("title", "") for l in logs}
        except Exception:
            pass

    if genre_id == "finance_news":
        candidates = _finance_topics()
    else:
        candidates = SEED_TOPICS.get(genre_id, SEED_TOPICS["python_tips"])

    # 未生成かつ未飽和のトピックを選ぶ
    try:
        from content_checker import check_topic_saturation
        remaining = []
        for t in candidates:
            if t in generated:
                continue
            saturated, _ = check_topic_saturation(genre_id, t)
            if not saturated:
                remaining.append(t)
    except Exception:
        remaining = [t for t in candidates if t not in generated]

    if not remaining:
        remaining = candidates  # 全て生成済みならランダム選択
    return random.choice(remaining)


def run_finance_news(topic: str, max_restart: int = 2) -> dict:
    """
    投資記事を生成する。品質未達時は情報再収集してZenn・はてな両方を再生成。
    - Zenn版失敗   → Zenn版のみ破棄して再スタート
    - はてな版失敗 → Zenn版・はてな版両方破棄して再スタート
    - 再スタートは最大 max_restart 回
    - Zenn版・はてな版は常に同じ finance_data を使用（整合性保証）
    """
    from content_generator import generate_article
    from finance_data_collector import collect_finance_data, compress_finance_context

    for restart in range(max_restart + 1):
        if restart > 0:
            print(f"\n  🔄 情報再収集して再スタート（{restart}/{max_restart}回目）")

        # 毎回新鮮なデータを収集
        print(f"  📈 投資データ収集中...")
        try:
            finance_data = collect_finance_data()
            ctx = compress_finance_context(finance_data)
            print(f"  📐 コンテキスト: {len(ctx)}文字")
        except Exception as e:
            print(f"  ⚠️ データ収集失敗: {e}")
            finance_data = None

        # Zenn版生成
        print(f"\n--- Zenn版（概要）---")
        zenn_result = generate_article(
            topic=topic,
            genre_id="finance_news",
            variant="zenn",
            finance_cache=finance_data,
        )
        zenn_failed = zenn_result.get("path") is None or "error" in zenn_result
        if zenn_failed:
            if restart < max_restart:
                print(f"  ❌ Zenn版品質未達 → 再スタート")
                if zenn_result.get("path"):
                    Path(zenn_result["path"]).unlink(missing_ok=True)
                continue
            else:
                print(f"  ❌ Zenn版: {max_restart}回再スタート後も品質未達 → 終了")
                return {"zenn": zenn_result, "hatena": None}

        # はてな版生成（Zenn版と同じ finance_data を使用）
        print(f"\n--- はてな版（詳細）---")
        hatena_result = generate_article(
            topic=topic,
            genre_id="finance_news",
            variant="hatena",
            finance_cache=finance_data,
        )
        hatena_failed = hatena_result.get("path") is None or "error" in hatena_result
        if hatena_failed:
            if restart < max_restart:
                print(f"  ❌ はてな版品質未達 → Zenn版も破棄して再スタート")
                if zenn_result.get("path"):
                    Path(zenn_result["path"]).unlink(missing_ok=True)
                if hatena_result.get("path"):
                    Path(hatena_result["path"]).unlink(missing_ok=True)
                continue
            else:
                print(f"  ❌ はてな版: {max_restart}回再スタート後も品質未達 → 終了")
                return {"zenn": zenn_result, "hatena": hatena_result}

        # 両方成功
        print(f"\n✅ Zenn版 完了: {zenn_result['path']}")
        print(f"✅ はてな版 完了: {hatena_result['path']}")
        return {"zenn": zenn_result, "hatena": hatena_result}

    return {"zenn": None, "hatena": None}


def run_single(genre_id: str = None, topic: str = None) -> dict:
    """1トピックについてZenn版（概要）・はてな版（詳細）の2記事を生成する"""
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

    # 投資記事は再スタートロジックを含む専用関数に委譲
    if genre_id == "finance_news":
        return run_finance_news(topic)

    # 技術記事: Zenn版・はてな版を順次生成
    results = {}
    print(f"\n--- Zenn版（概要）---")
    results["zenn"] = generate_article(
        topic=topic, genre_id=genre_id, variant="zenn",
    )
    print(f"\n--- はてな版（詳細）---")
    results["hatena"] = generate_article(
        topic=topic, genre_id=genre_id, variant="hatena",
    )
    return results


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
        # run_single は {"zenn": ..., "hatena": ...} を返す
        for variant, r in result.items():
            if "error" in r:
                print(f"❌ {variant}版 失敗: {r['error']}")
            else:
                print(f"✅ {variant}版 完了: {r.get('path', '?')} ({r.get('word_count', 0)}文字)")
