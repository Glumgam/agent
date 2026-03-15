# QA Report

Run: 2026-03-14 10:20
Model: qwen2.5-coder:7b

## Summary

| 指標 | 値 |
|------|-----|
| 総テスト数 | 3 |
| 成功 | 3 (100%) |
| 失敗 | 0 |
| リトライで成功 | 0 |
| 総実行時間 | 618.9s |

## Results by Category: Coding (3/3)

| ID | Label | 結果 | Steps | Retry | 時間 | 理由 |
|----|-------|------|-------|-------|------|------|
| C1 | FizzBuzz実装 | ✅ | 30 | 0 | 253.4s | done宣言あり、'FizzBuzz' をログ内で検出 |
| C2 | バグ修正 | ✅ | 8 | 0 | 108.9s | done宣言あり、'7' をログ内で検出 |
| C3 | unittest | ✅ | 30 | 0 | 256.5s | 'OK' が実行結果行に含まれる |

## Failed Tests

すべてのタスクが成功しました。
