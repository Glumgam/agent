import json
import os
from typing import List

import faiss

from project_map import safe_path


INDEX_PATH = "vector.index"
META_PATH = "vector_meta.json"
MODEL_NAME = "BAAI/bge-m3"

_model = None
_index = None
_meta = {"ids": [], "docs": {}}
_dim = None


def _ensure_loaded():
    global _model, _index, _meta, _dim
    if _model is None:
        from sentence_transformers import SentenceTransformer  # 遅延ロード
        _model = SentenceTransformer(MODEL_NAME)

    index_path = safe_path(INDEX_PATH)
    meta_path = safe_path(META_PATH)

    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _meta = data
        except Exception:
            _meta = {"ids": [], "docs": {}}

    if os.path.exists(index_path):
        try:
            _index = faiss.read_index(index_path)
            _dim = _index.d
        except Exception:
            _index = None
            _dim = None


def _save():
    if _index is None:
        return
    faiss.write_index(_index, safe_path(INDEX_PATH))
    with open(safe_path(META_PATH), "w", encoding="utf-8") as f:
        json.dump(_meta, f, ensure_ascii=False, indent=2)


def create_embedding(text: str) -> List[float]:
    _ensure_loaded()
    if not text:
        return []
    emb = _model.encode([text], normalize_embeddings=True)
    return emb[0].astype("float32").tolist()


def add_document(doc_id: str, text: str):
    _ensure_loaded()
    if not doc_id or not text:
        return
    if doc_id in _meta.get("docs", {}):
        return

    vec = _model.encode([text], normalize_embeddings=True)
    vec = vec.astype("float32")

    global _index, _dim
    if _index is None:
        _dim = vec.shape[1]
        _index = faiss.IndexFlatIP(_dim)
    elif vec.shape[1] != _index.d:
        return

    _index.add(vec)
    _meta.setdefault("ids", []).append(doc_id)
    _meta.setdefault("docs", {})[doc_id] = {"text": text}
    _save()


def search_similar(query: str, k: int = 5):
    _ensure_loaded()
    if _index is None or not query:
        return []

    vec = _model.encode([query], normalize_embeddings=True)
    vec = vec.astype("float32")

    scores, indices = _index.search(vec, k)
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        try:
            doc_id = _meta.get("ids", [])[idx]
        except Exception:
            continue
        doc = _meta.get("docs", {}).get(doc_id, {})
        item = {
            "doc_id": doc_id,
            "text": doc.get("text", ""),
            "_score": float(score),
        }
        results.append(item)

    return results
