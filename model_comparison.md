# Model Comparison Report

Date: 2026-03-17

## qwen2.5-coder:7b（現行）

- 成功率: 23/23 (100%)
- 総実行時間: 9588.8s
- 自己修復: 6/6 (100%)
- モデルサイズ: 4.7GB
- num_ctx: 16384 対応: ✅

## qwen3.5-uncensored:latest（候補）

- 成功率: テスト不可（タイムアウト）
- 総実行時間: 測定不可
- 自己修復: 測定不可
- モデルサイズ: 7.4GB
- num_ctx: 16384 対応: ❌ (2分超でタイムアウト)

## 問題点

- `qwen3.5-uncensored:latest` は `num_ctx: 16384` 設定でOllamaが応答しない
- コーディング特化ではなく、回答品質が不適切（"hi" への返答が `, i am using react`）
- `qwen3.5:9b-q6_k` タグはOllamaレジストリに存在しない

## 判定

- 成功率: 測定不可（qwen3.5-uncensored は実質使用不可）
- 速度: qwen3.5-uncensored は著しく遅い / タイムアウト
- **推奨: qwen2.5-coder:7b を継続使用**

## 代替候補（将来）

| モデル | サイズ | 入手方法 |
|--------|--------|---------|
| qwen3.5:9b | 6.6GB | `ollama pull qwen3.5:9b` |
| qwen2.5-coder:14b | ~9GB | `ollama pull qwen2.5-coder:14b` |

## 結論

qwen2.5-coder:7b は 23/23 (100%) の成功率を達成しており、現時点で最適なモデル。
qwen3.5-uncensored:latest はコーディングタスクに不適合のためロールバック済み。
