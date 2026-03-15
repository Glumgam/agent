# QA Report — Round 3

Run: 2026-03-15 03:44
Model: qwen2.5-coder:7b

## Summary

| 指標 | 値 |
|------|-----|
| 総テスト数 | 18 |
| 成功 | 17 (94%) |
| 失敗 | 1 |
| リトライで成功 | 8 |
| 総実行時間 | 1529.9s |

## Coding (3/3)

| ID | Label | 結果 | Steps | Retry | 時間 | 理由 |
|----|-------|------|-------|-------|------|------|
| C1 | FizzBuzz実装 | ✅ | 5 | 0 | 113.4s | done宣言あり、'FizzBuzz' をログ内で検出 |
| C2 | バグ修正 | ✅ | 9 | 1 | 335.3s | done宣言あり、'7' をログ内で検出 |
| C3 | unittest | ✅ | 9 | 1 | 422.6s | 'OK' が実行結果行に含まれる |

## File Operations (4/4)

| ID | Label | 結果 | Steps | Retry | 時間 | 理由 |
|----|-------|------|-------|-------|------|------|
| F1 | 拡張子別フォルダ振り分け | ✅ | 5 | 0 | 62.6s | exit code 0 を確認、エラーなし |
| F2 | 重複ファイル検出・削除 | ✅ | 6 | 0 | 387.1s | exit code 0 を確認、エラーなし |
| F3 | ファイル行数集計 | ✅ | 3 | 0 | 64.7s | exit code 0 を確認、エラーなし |
| F4 | ログファイル解析 | ✅ | 25 | 0 | 415.5s | done宣言あり、'ERROR' をログ内で検出 |

## PDF (4/4)

| ID | Label | 結果 | Steps | Retry | 時間 | 理由 |
|----|-------|------|-------|-------|------|------|
| P1 | PDF生成 | ✅ | 3 | 0 | 65.6s | exit code 0 を確認、エラーなし |
| P2 | PDFテキスト抽出 | ✅ | 9 | 1 | 134.1s | exit code 0 を確認（警告あり） |
| P3 | PDF複数ページ生成 | ✅ | 3 | 1 | 68.3s | exit code 0 を確認、エラーなし |
| P4 | PDF結合 | ✅ | 15 | 1 | 116.9s | exit code 0 を確認（警告あり） |

## Excel (4/4)

| ID | Label | 結果 | Steps | Retry | 時間 | 理由 |
|----|-------|------|-------|-------|------|------|
| E1 | Excel生成 | ✅ | 4 | 1 | 81.4s | exit code 0 を確認、エラーなし |
| E2 | Excel集計 | ✅ | 7 | 0 | 161.6s | exit code 0 を確認、エラーなし |
| E3 | Excel→CSV変換 | ✅ | 10 | 0 | 170.5s | exit code 0 を確認、エラーなし |
| E4 | Excelグラフ | ✅ | 13 | 1 | 190.1s | exit code 0 を確認、エラーなし |

## Web (2/3)

| ID | Label | 結果 | Steps | Retry | 時間 | 理由 |
|----|-------|------|-------|-------|------|------|
| W1 | HTTPリクエスト | ❌ | 17 | 1 | 234.2s | LLM判定: エージェントがfetch.pyファイルを作成し、requestsラ |
| W2 | HTML解析 | ✅ | 18 | 1 | 277.3s | exit code 0 を確認、エラーなし |
| W3 | JSON API保存 | ✅ | 6 | 0 | 87.5s | exit code 0 を確認、エラーなし |

## Failed Tests

### W1: HTTPリクエスト

**根本原因:** ループ検出による強制終了
**修正方針:** タスク文に「同じコマンドを繰り返さず、前の結果をよく読め」と追記

**最終ログ抜粋:**
```
===== STEP 17 =====
[LOOP DETECTED] sigs=['create_file::fetch.py', 'create_file::fetch.py', 'create_file::fetch.py'] obs_unique=1
⚠️ ループ検出 → 強制終了

終了処理
完了
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.

Loading weights:   0%|          | 0/199 [00:00<?, ?it/s]
Loading weights: 100%|██████████| 199/199 [00:00<00:00, 19665.59it/s]
[1mBertModel LOAD REPORT[0m from: BAAI/bge-small-en-v1.5
Key                     | Status     |  | 
------------------------+------------+--+-
embeddings.position_ids | UNEXPECTED |  | 

[3mNotes:
- UNEXPECTED[3m	:can be ignored when loading from different task/architecture; not ok if you expect identical arch.[0m
```
