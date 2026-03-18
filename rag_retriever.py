"""
RAG Retriever - Phase1。
knowledge/ のMarkdownをQdrantにインデックスし、
タスク時に関連情報をLLMに注入する。
"""
import uuid
import re
from pathlib import Path

AGENT_ROOT    = Path(__file__).parent
KNOWLEDGE_DIR = AGENT_ROOT / "knowledge"
COLLECTION    = "knowledge"
QDRANT_PATH   = str(AGENT_ROOT / "memory" / "qdrant_db")
VECTOR_SIZE   = 1024

# =====================================================
# 遅延ロード
# =====================================================
_embed_model   = None
_qdrant_client = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(
            "BAAI/bge-m3",
            device="mps",
        )
    return _embed_model


def get_client():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
        _qdrant_client = QdrantClient(path=QDRANT_PATH)
        existing = [c.name for c in _qdrant_client.get_collections().collections]
        if COLLECTION not in existing:
            _qdrant_client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
    return _qdrant_client


def embed(texts: list) -> list:
    model = get_embed_model()
    vecs  = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )
    return vecs.tolist()


# =====================================================
# Markdown分割
# =====================================================

def split_markdown(text: str, source: str, max_chars: int = 800) -> list:
    """ヘッダー単位で分割。コードブロック保護・空chunk除外。"""
    chunks = []

    # コードブロックを保護
    code_blocks = {}
    def replace_code(m):
        key = f"__CODE_{len(code_blocks)}__"
        code_blocks[key] = m.group(0)
        return key
    protected = re.sub(r"```.*?```", replace_code, text, flags=re.DOTALL)

    # ヘッダーで分割
    sections = re.split(r"(?=^#{1,3} )", protected, flags=re.MULTILINE)

    for section in sections:
        for key, code in code_blocks.items():
            section = section.replace(key, code)
        section = section.strip()
        if not section or len(section) < 20:
            continue
        if len(section) <= max_chars:
            chunks.append({"text": section, "source": source})
        else:
            for i in range(0, len(section), max_chars):
                chunk = section[i:i + max_chars].strip()
                if chunk:
                    chunks.append({"text": chunk, "source": source})
    return chunks


# =====================================================
# インデックス構築
# =====================================================

def index_knowledge() -> int:
    """knowledge/ のMarkdownを全てQdrantにupsertする"""
    from qdrant_client.models import PointStruct

    client   = get_client()
    md_files = list(KNOWLEDGE_DIR.rglob("*.md"))
    total    = 0

    if not md_files:
        print("  knowledge/ にMarkdownファイルなし")
        return 0

    print(f"  インデックス対象: {len(md_files)}ファイル")

    for md_file in md_files:
        try:
            text   = md_file.read_text(encoding="utf-8", errors="ignore")
            source = str(md_file.relative_to(AGENT_ROOT))
            chunks = split_markdown(text, source)
            if not chunks:
                continue
            texts   = [c["text"] for c in chunks]
            vectors = embed(texts)
            points  = []
            for chunk, vec in zip(chunks, vectors):
                uid = str(uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    source + chunk["text"][:50]
                ))
                points.append(PointStruct(
                    id=uid,
                    vector=vec,
                    payload={
                        "text":   chunk["text"],
                        "source": chunk["source"],
                        "length": len(chunk["text"]),
                    }
                ))
            client.upsert(collection_name=COLLECTION, points=points)
            total += len(points)
        except Exception as e:
            print(f"  ⚠️ {md_file.name}: {e}")

    print(f"  ✅ インデックス完了: {total}チャンク")
    return total


# =====================================================
# 検索
# =====================================================

def _should_use(scores: list) -> bool:
    """絶対値 + 相対評価でスコア判定"""
    if not scores:
        return False
    top = scores[0]
    if top < 0.45:
        return False
    if len(scores) == 1:
        return True
    # BGE-M3 + 日本語はスコアが接近しやすいため gap 閾値を緩く設定
    # top >= 0.60 は高信頼 → gap 不問で採用
    if top >= 0.60:
        return True
    gap = (top - scores[1]) / top
    return gap > 0.01


def search(query: str, top_k: int = 3) -> list:
    """クエリに関連するknowledgeを検索する"""
    client  = get_client()
    vec     = embed([query])[0]
    # qdrant-client 1.x: query_points (旧 search は廃止)
    response = client.query_points(
        collection_name=COLLECTION,
        query=vec,
        limit=top_k + 2,
    )
    results = response.points
    if not results:
        return []
    scores = [r.score for r in results]
    if not _should_use(scores):
        return []
    return [
        {
            "text":   r.payload["text"],
            "source": r.payload["source"],
            "score":  r.score,
        }
        for r in results[:top_k]
        if r.score >= 0.45
    ]


def format_context(results: list, max_chars: int = 1500) -> str:
    """検索結果をLLM用コンテキストに整形する"""
    if not results:
        return ""
    context = ""
    for i, r in enumerate(results, 1):
        snippet  = r["text"][:400]
        context += f"[知識{i}] (score={r['score']:.2f})\n{snippet}\n\n"
        if len(context) > max_chars:
            break
    return context.strip()


def run_rag(query: str) -> str:
    """RAGを実行してLLM用コンテキスト文字列を返す"""
    try:
        results = search(query, top_k=3)
        return format_context(results)
    except Exception:
        return ""
