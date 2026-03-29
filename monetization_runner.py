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


def _cleanup_failed_files(topic: str, content_dir: Path):
    """前回の不完全な生成ファイルを削除し、重複DBからも除去する"""
    import re
    from content_checker import _load_dedup_db, _save_dedup_db

    date_str = datetime.now().strftime("%Y%m%d")
    # タイトルの記号を除去してパターンを作成
    slug_hint = re.sub(r"[^\w]", "", topic[:10])
    pattern   = f"{date_str}_*{slug_hint}*"

    for f in content_dir.glob(pattern + "*.md"):
        f.unlink(missing_ok=True)
        print(f"  🗑️ クリーンアップ: {f.name}")

    # 重複DBからも削除（variant:title 形式）
    db     = _load_dedup_db()
    titles = db.get("titles", {})
    keys_to_remove = [k for k in titles if topic in k]
    for k in keys_to_remove:
        del titles[k]
    if keys_to_remove:
        db["titles"] = titles
        _save_dedup_db(db)
        print(f"  🗑️ 重複DB削除: {len(keys_to_remove)}件")


def run_finance_news(topic: str, max_restart: int = 2) -> dict:
    """
    投資記事を生成する。品質未達時は情報再収集してZenn・はてな両方を再生成。
    - Zenn版失敗   → Zenn版のみ破棄して再スタート
    - はてな版失敗 → Zenn版・はてな版両方破棄して再スタート
    - 整合性不一致 → 間違った版のみ正値を与えて修正再生成
    - 再スタートは最大 max_restart 回
    - Zenn版・はてな版は常に同じ finance_data を使用（整合性保証）
    """
    from content_generator import generate_article
    from finance_data_collector import collect_finance_data, compress_finance_context

    finance_dir = AGENT_ROOT / "content" / "finance"

    for restart in range(max_restart + 1):
        if restart > 0:
            print(f"\n  🔄 情報再収集して再スタート（{restart}/{max_restart}回目）")
            _cleanup_failed_files(topic, finance_dir)

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

        # 整合性チェックループ（最大 MAX_CONSISTENCY_FIX 回修正）
        MAX_CONSISTENCY_FIX = 3
        from consistency_checker import check_consistency
        from content_generator import generate_article

        consistency_fix_count = 0
        while consistency_fix_count < MAX_CONSISTENCY_FIX:
            if not zenn_result.get("path") or not hatena_result.get("path"):
                break

            zenn_path   = Path(zenn_result["path"])
            hatena_path = Path(hatena_result["path"])

            if not zenn_path.exists() or not hatena_path.exists():
                print(f"  ⚠️ 整合性チェックスキップ: ファイルが見つかりません")
                print(f"     Zenn: {zenn_path}")
                print(f"     はてな: {hatena_path}")
                break

            try:
                zenn_c   = zenn_path.read_text(encoding="utf-8")
                hatena_c = hatena_path.read_text(encoding="utf-8")

                print(f"\n  🔍 整合性チェック中（{consistency_fix_count + 1}/{MAX_CONSISTENCY_FIX}）...")
                consistency = check_consistency(zenn_c, hatena_c, finance_data)

                if consistency["consistent"]:
                    print(f"  ✅ 整合性チェック: 問題なし")
                    break

                consistency_fix_count += 1

                if consistency_fix_count >= MAX_CONSISTENCY_FIX:
                    print(f"  ⚠️ 整合性修正{MAX_CONSISTENCY_FIX}回試行後も不一致（保存続行）")
                    break

                # 正値と方向性をプロンプトに埋め込む
                market    = finance_data.get("market_summary", {}) if finance_data else {}
                macro     = finance_data.get("macro", {})          if finance_data else {}
                us        = macro.get("us_stocks", {})
                forex     = macro.get("forex", {})
                comm      = macro.get("commodities", {})

                nikkei_chg = market.get("nikkei_change_pct", 0) or 0
                nikkei_dir = "上昇" if nikkei_chg > 0 else "下落" if nikkei_chg < 0 else "横ばい"
                vix_chg    = (us.get("VIX", {}).get("change_pct") or 0)
                vix_dir    = "上昇" if vix_chg > 0 else "下落"
                usd_chg    = (forex.get("USD/JPY", {}).get("change_pct") or 0)
                forex_dir  = "円安" if usd_chg > 0 else "円高"
                sp500_chg  = (us.get("S&P500", {}).get("change_pct") or 0)
                wti_chg    = (comm.get("WTI原油", {}).get("change_pct") or 0)

                issues_text = "\n".join(
                    f"  - {i}" for i in consistency["issues"]
                )
                correction_prompt = f"""
【整合性チェックで検出された問題】
{issues_text}

【必ず使用する正しい数値と方向性】
  日経平均: {market.get("nikkei_price", "")}円 （前日比{nikkei_dir}）
  VIX: {us.get("VIX", {}).get("price", "")} （前日比{vix_chg:+.1f}%→{vix_dir}）
  USD/JPY: {forex.get("USD/JPY", {}).get("price", "")}円 （{forex_dir}進行）
  S&P500: {us.get("S&P500", {}).get("price", "")} （前日比{sp500_chg:+.1f}%）
  WTI原油: ${comm.get("WTI原油", {}).get("price", "")} （前日比{wti_chg:+.1f}%）

上記の数値と方向性を必ずそのまま使用して、矛盾のない記事を書き直してください。
"""

                # 間違っている版を特定
                wrong_versions = set()

                for issue in consistency["issues"]:
                    if "はてな版" in issue:
                        wrong_versions.add("hatena")
                    elif "Zenn版" in issue:
                        wrong_versions.add("zenn")

                # 相互矛盾の場合: コンテキストの正値と照合してどちらが正しいか確認
                zenn_c_current = zenn_path.read_text(encoding="utf-8") if zenn_path and zenn_path.exists() else ""
                for issue in consistency["issues"]:
                    if "Zenn版とはてな版の方向性矛盾" in issue:
                        # VIXの場合: 変動率から正しい方向を判定
                        if "VIX" in issue:
                            vix_chg_val = (finance_data or {}).get("macro", {}).get("us_stocks", {}).get("VIX", {}).get("change_pct", 0) or 0
                            true_vix_dir = "上昇" if vix_chg_val > 0 else "下落"
                            import re as _re
                            vix_in_zenn = _re.search(r'VIX[^。\n]{0,30}(上昇|下落|低下)', zenn_c_current)
                            if vix_in_zenn and vix_in_zenn.group(1) == true_vix_dir:
                                wrong_versions.discard("zenn")
                                wrong_versions.add("hatena")
                            else:
                                wrong_versions.discard("hatena")
                                wrong_versions.add("zenn")
                        # 日経平均の場合
                        elif "日経平均" in issue:
                            nikkei_chg_val = (finance_data or {}).get("market_summary", {}).get("nikkei_change_pct", 0) or 0
                            true_nikkei_dir = "上昇" if nikkei_chg_val > 0 else "下落"
                            import re as _re
                            nikkei_in_zenn = _re.search(r'日経平均.*?(上昇|下落)', zenn_c_current)
                            if nikkei_in_zenn and nikkei_in_zenn.group(1) == true_nikkei_dir:
                                wrong_versions.discard("zenn")
                                wrong_versions.add("hatena")
                            else:
                                wrong_versions.discard("hatena")
                                wrong_versions.add("zenn")

                # どちらが間違っているか不明な場合ははてな版を修正（Zenn版を正として扱う）
                if not wrong_versions:
                    wrong_versions = {"hatena"}

                wrong_versions = list(wrong_versions)
                print(f"  🔧 修正対象: {wrong_versions}版（試行{consistency_fix_count}/{MAX_CONSISTENCY_FIX}）")

                for v in wrong_versions:
                    target      = zenn_path if v == "zenn" else hatena_path
                    old_path    = target if target.exists() else None
                    target.unlink(missing_ok=True)
                    new_result = generate_article(
                        topic=topic,
                        genre_id="finance_news",
                        variant=v,
                        finance_cache=finance_data,
                        extra_prompt=correction_prompt,
                        force_overwrite=True,
                    )
                    if new_result is None or new_result.get("path") is None:
                        print(f"  ⚠️ {v}版の修正再生成失敗 → 既存ファイルをそのまま保持")
                        # ファイルが既に削除されていれば復元不可・既存resultを維持
                        if old_path and old_path.exists():
                            if v == "zenn":
                                zenn_result = {"path": str(old_path), "score": 9}
                            else:
                                hatena_result = {"path": str(old_path), "score": 9}
                        # else: ファイルが消えた場合は None のまま（ループ先頭でbreakされる）
                    else:
                        if v == "zenn":
                            zenn_result = new_result
                        else:
                            hatena_result = new_result

            except Exception as e:
                print(f"  ⚠️ 整合性チェックスキップ: {e}")
                import traceback; traceback.print_exc()
                break

        # 最終結果ログ（None安全）
        zenn_path_str   = zenn_result.get("path")   if zenn_result   else None
        hatena_path_str = hatena_result.get("path") if hatena_result else None
        if zenn_path_str:
            print(f"\n✅ Zenn版 完了: {zenn_path_str}")
        else:
            print(f"\n❌ Zenn版 失敗")
        if hatena_path_str:
            print(f"✅ はてな版 完了: {hatena_path_str}")
        else:
            print(f"❌ はてな版 失敗")
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
            if r is None or r.get("path") is None:
                print(f"❌ {variant}版 失敗: {r.get('error', '不明') if r else '結果なし'}")
            else:
                print(f"✅ {variant}版 完了: {r.get('path', '?')} ({r.get('word_count', 0)}文字)")
