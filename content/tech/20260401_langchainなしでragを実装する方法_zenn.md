# LangChainなしでRAGを実装するメソッド

## はじめに（このライブラリ/技術とは）

RAG（Retrieval-Augmented Generation）は、文書検索と生成の2つのプロセスを組み合わせて、より自然な回答を生むテクノロジーです。LangChainを使用せずにRAGを実装するメソッドについて、本記事では概要と基本的な使い方、そして実践例を紹介します。

## 基本的な使い方

まずは、必要なライブラリをインストールしましょう。以下はPythonで使用できる主要なライブラリです：

```python
pip install sentence-transformers faiss-cpu transformers
```

次に、シンプルなRAGシステムを実装します。以下のコードは、文書のベクトル化と検索を行う基本的な構造です。

```python
from sentence_transformers import SentenceTransformer
import faiss
from transformers import pipeline

# 文書リスト
documents = [
 "Python is a high-level, interpreted programming language.",
 "RAG combines retrieval and generation to improve responses.",
 "LangChain simplifies working with large language models."
]

# ベクトル化モデルのロード
model = SentenceTransformer('all-MiniLM-L6-v2')
document_vectors = model.encode(documents)

# Faissインデックスの作成
index = faiss.IndexFlatL2(document_vectors.shape[1])
index.add(document_vectors)

# 検索クエリ
query = "Pythonについて教えて"
query_vector = model.encode([query])

# 検索実行
D, I = index.search(query_vector, k=1)
retrieved_document = documents[I[0][0]]

print(f"Retrieved Document: {retrieved_document}")
```

このコードでは、`SentenceTransformer`を使って文書をベクトル化し、`faiss`を使って検索インデックスを作成しています。検索クエリも同様にベクトル化し、最適なドキュメントを取得します。

## 実践例

次に、実際の応用ケースを示すコード例を見てみましょう。以下は、チャットボットでRAGを使用する実装です。

```python
from sentence_transformers import SentenceTransformer
import faiss
from transformers import pipeline

# 文書リスト（チャットボットの知識ベース）
knowledge_base = [
 "Python is a high-level, interpreted programming language.",
 "RAG combines retrieval and generation to improve responses.",
 "LangChain simplifies working with large language models."
]

# ベクトル化モデルのロード
model = SentenceTransformer('all-MiniLM-L6-v2')
knowledge_base_vectors = model.encode(knowledge_base)

# Faissインデックスの作成
index = faiss.IndexFlatL2(knowledge_base_vectors.shape[1])
index.add(knowledge_base_vectors)

def get_response(query):
 # クエリのベクトル化
 query_vector = model.encode([query])

 # 検索実行
 D, I = index.search(query_vector, k=3)
 retrieved_documents = [knowledge_base[i] for i in I[0]]

 # 生成用のコンテキスト作成
 context = " ".join(retrieved_documents)

 # テキスト生成モデルのロード
 generator = pipeline("text-generation", model="gpt2")

 # 生成タスク
 response = generator(context + query, max_length=50, num_return_sequences=1)
 return response[0]['generated_text']

# クエリの実行例
query = "Pythonについて教えて"
response = get_response(query)
print(f"Bot's Response: {response}")
```

このコードでは、複数のドキュメントを検索し、取得したドキュメントをコンテキストとして生成タスクに渡しています。`gpt2`モデルを使って、クエリとコンテキストを元にレスポンスを生成します。

## まとめ

- RAGは文書検索と生成の組み合わせで自然な回答を生むテクノロジーです。
- `SentenceTransformer`や`faiss`などのライブラリを使用すると、簡単にRAGシステムを実装できます。
- 実践例では、チャットボット用のRAGシステムを紹介しました。複数のドキュメントから情報を抽出し、生成モデルを使って応答を生み出すことができます。

この記事で紹介したメソッドは、LangChainを使用せずに基本的なRAGシステムを実装するための手順です。より高度な応用や詳細については、「詳細記事（はてなブログ）」をご覧ください。
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
## 📖 詳細版はこちら
**はてなブログの詳細版**では、より深い解説と実践的な内容を掲載しています。

👉 [詳細版を読む（はてなブログ）](（はてなブログで公開予定）)
---
*この記事はAIエージェントによって自動生成されました。*
*誤りや改善点があればコメントでお知らせください。*
<!-- score:9 variant:zenn generated:2026-04-01 02:28 -->