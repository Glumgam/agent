# Sentence Transformersでテキスト検索を実装する

この記事では、Sentence Transformersを利用してテキスト検索を実装するメソッドについて詳しく解説します。以下のことを学びます：

1. Sentence Transformersの基礎的な概念と機能
2. 環境準備：必要なライブラリをインストールするメソッド
3. ステップ1: 基礎実装：Sentence Transformersを使用した単純なテキスト検索を行う
4. ステップ2: 機能追加：検索結果のフィルタリングやソート機能を追加する
5. ステップ3: 実用化：完成したコードと実際の使用例について説明する

## 環境準備

Sentence Transformersを使用するためには、まずPython環境に`sentence-transformers`ライブラリをインストールします。以下のコマンドでインストールできます：

```python
!pip install sentence-transformers
```

また、テキストデータの扱いに便利な`pandas`と`numpy`も導入します：

```python
!pip install pandas numpy
```

## ステップ1: 基礎実装

まず、Sentence Transformersを使用して単純なテキスト検索を行うメソッドを紹介します。以下に具体的なコード例を示します。

### 1. ライブラリのインポート

```python
from sentence_transformers import SentenceTransformer, util
import numpy as np
```

### 2. モデルのロード

Sentence Transformersには様々なモデルが用意されています。ここでは、`all-MiniLM-L6-v2`モデルを使用します：

```python
model = SentenceTransformer('all-MiniLM-L6-v2')
```

### 3. 文本データの準備

検索対象のテキストデータをリストに格納します：

```python
texts = [
    "私はPythonで機械学習を行うことができます。",
    "sentence-transformersは簡単にテキストベクトル化できます。",
    "Sentence Transformersは様々なモデルが用意されています。",
    "自然言語処理の技術を理解しています。",
    "Pythonのライブラリを使用して、データ分析を行うことができます。"
]
```

### 4. ベクトル化

_sentence-transformers_を使用してテキストデータをベクトル化します：

```python
text_embeddings = model.encode(texts)
```

### 5. 検索実行

検索クエリのベクトル化を行い、類似度が最も高い文を抽出します：

```python
query_vector = np.random.rand(384)  # ランダムなベクトルを使用する場合
hits = util.semantic_search(query_vector, text_embeddings, top_k=2)
```

検索結果を表示します：

```python
for hit in hits[0]:
    print(f"文: {texts[hit['corpus_id']]}")
    print(f"類似度: {hit['score']:.4f}\n")
```

## ステップ2: 機能追加

検索結果をフィルタリングやソートする機能を追加します。以下に具体的なコード例を示します。

### 1. フィルタリング

特定のキーワードが含まれている文だけを抽出します：

```python
filter_keyword = "Python"
filtered_texts = [text for text in texts if filter_keyword in text]

filtered_text_embeddings = model.encode(filtered_texts)
query_vector = np.random.rand(384)  # ランダムなベクトルを使用する場合
hits = util.semantic_search(query_vector, filtered_text_embeddings, top_k=2)

for hit in hits[0]:
    print(f"文: {filtered_texts[hit['corpus_id']]}")
    print(f"類似度: {hit['score']:.4f}\n")
```

### 2. ソート

検索結果を類似度の順でソートします：

```python
sorted_hits = sorted(hits[0], key=lambda x: x['score'], reverse=True)

for hit in sorted_hits:
    print(f"文: {texts[hit['corpus_id']]}")
    print(f"類似度: {hit['score']:.4f}\n")
```

## ステップ3: 実用化

完成したコードと実際の使用例について説明します。以下に具体的なコードを示します。

### 1. 完成コード

```python
from sentence_transformers import SentenceTransformer, util
import numpy as np

# モデルのロード
model = SentenceTransformer('all-MiniLM-L6-v2')

# 文本データの準備
texts = [
    "私はPythonで機械学習を行うことができます。",
    "sentence-transformersは簡単にテキストベクトル化できます。",
    "Sentence Transformersは様々なモデルが用意されています。",
    "自然言語処理の技術を理解しています。",
    "Pythonのライブラリを使用して、データ分析を行うことができます。"
]

# ベクトル化
text_embeddings = model.encode(texts)

# 検索実行
query_vector = np.random.rand(384)  # ランダムなベクトルを使用する場合
hits = util.semantic_search(query_vector, text_embeddings, top_k=2)

for hit in hits[0]:
    print(f"文: {texts[hit['corpus_id']]}")
    print(f"類似度: {hit['score']:.4f}\n")

# フィルタリング
filter_keyword = "Python"
filtered_texts = [text for text in texts if filter_keyword in text]

filtered_text_embeddings = model.encode(filtered_texts)
query_vector = np.random.rand(384)  # ランダムなベクトルを使用する場合
hits = util.semantic_search(query_vector, filtered_text_embeddings, top_k=2)

for hit in hits[0]:
    print(f"文: {filtered_texts[hit['corpus_id']]}")
    print(f"類似度: {hit['score']:.4f}\n")

# ソート
sorted_hits = sorted(hits[0], key=lambda x: x['score'], reverse=True)

for hit in sorted_hits:
    print(f"文: {texts[hit['corpus_id']]}")
    print(f"類似度: {hit['score']:.4f}\n")
```

### 2. 実際の使用例

実際の機械学習プロジェクトで、テキストデータに対してSimilarity Searchを行うことで、最も関連性の高い文を抽出することができます。これにより、ユーザーの質問に最適な回答や、類似の文章の探索などが可能になります。

例えば、ある企業の問い合わせに対する回答を生成する場合、質問と過去の問い合わせの類似度を計算することで、最も適切な回答を選び出すことができます。

## トラブルシューティング

実際によく起きるエラーと具体的な対処法を3件以上書くこと。

### エラー1: モデル未インストール

**エラーメッセージ**: `ModuleNotFoundError: No module named 'sentence_transformers'`

**対策**: `pip install sentence-transformers`でライブラリをインストールしてください。

### エラー2: ベクトル化失敗

**エラーメッセージ**: `TypeError: encode() missing 1 required positional argument: 'sentences'`

**対策**: ベクトル化する際に、引数に`sentences`を指定してください。例：`model.encode(sentences=texts)`

### エラー3: 検索結果が空

**エラーメッセージ**: `list index out of range`

**対策**: リストインデックスが範囲外の場合、検索対象のテキストデータに問題がある可能性があります。再度確認してください。

## FAQ

このトピックに関してよくある疑問を3〜5個、具体的に考えてQ&A形式で書いてください。

### Q1: Sentence Transformersはどのようなライブラリですか？

A1: Sentence Transformersは、自然言語処理のためのライブラリです。テキストデータをベクトル化し、類似度検索を行うことができます。

### Q2: 何種類のモデルが用意されていますか？

A2: Sentence Transformersには様々なモデルが用意されています。`all-MiniLM-L6-v2`や`all-MiniLM-L3-v2`などがあります。

### Q3: ベクトル化したデータをどのように保存できますか？

A3: `numpy.save`や`pandas.DataFrame.to_csv`などのメソッドを使用して、ベクトル化したデータを保存することができます。

### Q4: 検索結果はどのような形式で得られますか？

A4: 検索結果は、文のインデックスと類似度のリストです。例：`[{'corpus_id': 0, 'score': 0.95}, {'corpus_id': 1, 'score': 0.85}]`

### Q5: Sentence Transformersではフィルタリングやソートが可能ですか？

A5: はい、検索結果をフィルタリングやソートすることができます。例：`sorted(hits[0], key=lambda x: x['score'], reverse=True)`

## まとめ

Sentence Transformersを使用してテキスト検索を行うことで、自然言語処理の技術を簡単に実装することができます。本文では、基礎的な概念と機能を説明し、実際に使用するメソッドについても解説しました。さらに、トラブルシューティングやFAQも掲載してきました。これからは、Sentence Transformersを利用して様々な機械学習プロジェクトに活用してみてください。
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
