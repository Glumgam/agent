import faiss
import numpy as np


MODEL_NAME = "BAAI/bge-small-en-v1.5"

_model = None
_index = None
_documents = []
_embeddings = None


def _ensure_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer  # 遅延ロード
        _model = SentenceTransformer(MODEL_NAME)


def create_index():
    global _index
    global _documents
    global _embeddings

    _ensure_model()

    if _index is None:
        dim = _model.get_sentence_embedding_dimension()
        _index = faiss.IndexFlatIP(dim)
        _documents = []
        _embeddings = None

    return _index


def _encode(text: str):
    _ensure_model()
    emb = _model.encode([text], normalize_embeddings=True)
    return emb.astype("float32")


def create_embedding(text: str):
    if not text:
        return []
    vec = _encode(text)
    return vec[0].tolist()


def add_document(path: str, text: str):
    global _index
    global _documents
    global _embeddings

    if not path or not text:
        return

    create_index()
    vec = _encode(text)

    _index.add(vec)
    _documents.append({"path": path, "text": text})

    if _embeddings is None:
        _embeddings = vec
    else:
        _embeddings = np.vstack([_embeddings, vec])


def search(query: str, top_k: int = 5):
    global _index
    global _documents
    global _embeddings

    if not query:
        return []

    create_index()

    if _index is None or _index.ntotal == 0:
        return []

    q = _encode(query)
    scores, indices = _index.search(q, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_documents):
            continue
        doc = _documents[idx]
        snippet = doc.get("text", "")[:400]
        results.append(
            {
                "path": doc.get("path", ""),
                "snippet": snippet,
                "score": float(score),
            }
        )

    return results
