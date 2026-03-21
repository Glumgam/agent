# アーキテクチャ詳細

## コアコンポーネント

### main.py — タスク実行エンジン

タスクを受け取り **Plan → Execute → Evaluate** のループを実行する。

- **MAX_STEPS**: 30（1タスクあたりの最大実行ステップ数）
- **RAG注入**: タスク前に関連知識を検索してプロンプトに注入
- **自己修復**: 失敗時に `self_evaluator` → `self_improver` を呼ぶ
- **スキル保存**: 成功時に `skill_extractor` でスキルを抽出・保存

---

### self_evaluator.py — 失敗分類器

失敗を以下の11種類に分類する:

| 分類 | 説明 |
|------|------|
| `import_error` | モジュール未インストール |
| `syntax_error` | 構文エラー |
| `loop_detected` | 同じ操作の繰り返し |
| `timeout` | 実行タイムアウト |
| `wrong_output` | 期待値不一致 |
| `file_not_found` | ファイル未生成 |
| `permission_error` | 権限エラー |
| `network_error` | ネットワーク障害 |
| `max_steps` | ステップ上限到達 |
| `unknown` | 未分類 |

---

### skill_extractor.py — ゲットアビリティシステム

成功タスクからスキルを抽出して `skill_db.json` に保存する。

```python
# スキルの構造
{
  "name": "web_scraping",
  "tools_used": ["web_search", "create_file", "run"],  # 実行順序（テンプレート）
  "key_imports": ["requests", "bs4"],                  # 使用ライブラリ
  "success_count": 10,                                 # 成功回数
  "last_used": "2026-03-21T...",                       # 最終使用日時
}
```

スコア計算（検索時）:

```
score = name_match(+10) + keyword_match(+2×n) + success_count + recency_bonus
```

現在の習得スキル数: **22個**

---

### rag_retriever.py — RAGシステム

#### スコア計算

```
knowledge:     final_score = raw_score × 0.75 × freshness
official_docs: final_score = raw_score × 0.90
```

#### freshness補正（knowledgeのみ）

| 経過日数 | freshness係数 |
|------|------|
| 3日未満 | 1.0 |
| 7日未満 | 0.9 |
| 30日未満 | 0.75 |
| 30日以上 | 0.6 |

#### フィルタリング

- **絶対値下限**: `knowledge=0.38`、`official_docs=0.45`
- **相対評価**: 1位スコアが2位より1%以上高い場合に採用
- **重複除去**: `text[:100]` のハッシュで重複チャンクを除去
- **品質フィルタ**: `is_valid_chunk()` で短文・記号過多を除外

#### デバッグ関数

```python
debug_rag(query, top_k=5)    # スコア分布表示 + JSONLines記録
show_rag_stats(last_n=50)    # 直近N件の集計統計
# ログ: logs/rag_search_log.jsonl
```

---

### deep_researcher.py — ツール自動獲得

```
候補発見（ask_plain）
  ↓
PyPI存在確認（API）
  ↓
GitHub・Web・PyPIで深掘り調査
  ↓
コード生成（ask_plain）
  ↓
code_checker.py（静的解析 + LLMレビュー）
  ↓
動作テスト（subprocess）
  ↓
toolkit統合（toolkit_manager.py）
```

自動獲得済みツール（`tools/evolved/`）: **6個**

---

## メモリ構造

```
memory/
  skill_db.json           # 習得スキル（22個）
  repair_patterns.json    # 修復パターン
  content_log.json        # 記事生成ログ
  official_docs_meta.json # 公式ドキュメント管理
  seen_urls.json          # 既読URL（7日間）
  qdrant_db/              # ベクトルDB（knowledge + official_docs）
```

---

## 自律ループのフェーズ詳細

```
loop_forever.sh
  └── autonomous_loop.py（永続実行）
        ├── Phase 0: official_doc_collector.py（8サイクルに1回）
        ├── Phase 1: research_agent.py（毎サイクル）
        │     └── deep_researcher.py（スキル獲得）
        ├── Phase 1.5: evolve_existing_skills()（2サイクルに1回）
        ├── Phase 1.7: monetization_runner.py（24サイクルに1回）
        └── Phase 2: tester.py（毎サイクル・品質監視）
```

---

## コードチェックパイプライン

```
生成コード
  ↓
static_check()（8ルール）
  ├── SYNTAX:        構文エラー
  ├── ASYNC-IN-SYNC: 非async関数内のawait
  ├── DEAD-EXCEPT:   到達不能ハンドラ
  ├── AES-KEY-LEN:   暗号化キー長
  ├── EXCEL-FORMULA: 数式の誤代入
  ├── ASYNCIO-IMPORT: 未インポート
  ├── CLOSURE-BUG:   クロージャバグ
  └── UNDEF-VAR:     未定義変数
  ↓
llm_review()（deepseek-coder-v2:lite / フォールバック: qwen2.5-coder:7b）
  ↓
auto_fix()（最大2回）
  ↓
toolkit統合
```

---

## LLMルーティング

```
llm_router.py
  ├── ask_plain()      → qwen2.5-coder:7b（通常タスク）
  ├── ask_thinking()   → qwen3.5:9b（複雑推論・タイムアウト時はask_plainにフォールバック）
  └── ask_review()     → deepseek-coder-v2:lite（コードレビュー）
```

タスク複雑度の判定基準（planner_light.py）:

| 判定 | 条件 | モデル |
|------|------|------|
| シンプル | ステップ数≤3、既知パターン | qwen2.5-coder:7b |
| 複雑 | 多段階推論、設計判断が必要 | qwen3.5:9b |

---

## コンテンツ生成システム

```
monetization_runner.py
  ├── SEED_TOPICS（4ジャンル × 6〜8トピック）
  ├── select_topic()  → 未生成トピックを優先選択
  └── run_single()    → generate_article()呼び出し

content_generator.py
  ├── _QUALITY_RULES（6品質ルール）
  ├── ARTICLE_TEMPLATES（tips / tutorial / introduction）
  ├── generate_article()
  │     ├── RAG検索（関連知識を注入）
  │     ├── ask_thinking()（→ フォールバック: ask_plain()）
  │     └── content/ に保存（Markdown）
  └── get_stats() → 生成統計
```

品質ルール:
1. プレースホルダー禁止
2. 繰り返し禁止
3. 具体的な動作コード必須
4. 実際のFAQ必須（3〜5個）
5. 比較記事は表形式必須
6. 2500文字以上
