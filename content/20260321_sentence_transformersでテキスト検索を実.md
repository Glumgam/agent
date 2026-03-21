{texts[i]}: {score.item():.4f}")


## ステップ2: 機能追加
基本的な実装をした後、複雑な検索機能を追加します。以下に具体的なコード例を示します。

python
from sentence_transformers import SentenceTransformer, util

# モデルの読み込み
model = SentenceTransformer('all-MiniLM-L6-v2')

# 検索対象のテキストリスト
texts = [
    "私はAIエンジニアです。",
    "Pythonは強力なプログラミング言語です。",
    "Sentence Transformersはテキストをベクトルに変換します。",
    "機械学習は人工知能の基礎です。"
]

# ベクトル化
text_embeddings = model.encode(texts)

# 検索対象のテキスト
query = "Pythonについて教えてください。"

# クエリベクトル化
query_embedding = model.encode(query)

# 類似度計算
cos_scores = util.cos_sim(query_embedding, text_embeddings)

# 結果表示
for i, score in enumerate(cos_scores[0]):
    print(f"{texts[i]}: {score.item():.4f}")

# 上位3件の結果を抽出
top_results = sorted(enumerate(cos_scores[0]), key=lambda x: x[1], reverse=True)[:3]

print("\n上位3件の結果:")
for idx, score in top_results:
    print(f"{texts[idx]}: {score.item():.4f}")


## ステップ3: 実用化
完成したコードを実際のプロジェクトに適用します。以下に具体的なコード例を示します。

python
from sentence_transformers import SentenceTransformer, util

# モデルの読み込み
model = SentenceTransformer('all-MiniLM-L6-v2')

# 検索対象のテキストリスト
texts = [
    "私はAIエンジニアです。",
    "Pythonは強力なプログラミング言語です。",
    "Sentence Transformersはテキストをベクトルに変換します。",
    "機械学習は人工知能の基礎です。"
]

# ベクトル化
text_embeddings = model.encode(texts)

def search(query):
    # クエリベクトル化
    query_embedding = model.encode(query)
    
    # 類似度計算
    cos_scores = util.cos_sim(query_embedding, text_embeddings)
    
    # 上位3件の結果を抽出
    top_results = sorted(enumerate(cos_scores[0]), key=lambda x: x[1], reverse=True)[:3]
    
    return [(texts[idx], score.item()) for idx, score in top_results]

# テスト
query = "Pythonについて教えてください。"
results = search(query)
for text, score in results:
    print(f"{text}: {score:.4f}