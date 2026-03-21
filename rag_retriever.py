"""
RAG Retriever - Phase1 + 公式ドキュメント対応版。
コレクション:
  knowledge     - ニュース・論文・ブログ（7日で更新）
  official_docs - 公式ドキュメント・法律・規格（永久保存・バージョン管理）
"""
import json
import uuid
import re
from datetime import datetime
from pathlib import Path

AGENT_ROOT    = Path(__file__).parent
KNOWLEDGE_DIR = AGENT_ROOT / "knowledge"
DOCS_DIR      = AGENT_ROOT / "official_docs"
QDRANT_PATH   = str(AGENT_ROOT / "memory" / "qdrant_db")
VECTOR_SIZE   = 1024

COLLECTIONS = {
    "knowledge":     {"permanent": False},
    "official_docs": {"permanent": True},
}

_embed_model   = None
_qdrant_client = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("BAAI/bge-m3", device="mps")
    return _embed_model


def get_client():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
        _qdrant_client = QdrantClient(path=QDRANT_PATH)
        existing = [c.name for c in _qdrant_client.get_collections().collections]
        for name in COLLECTIONS:
            if name not in existing:
                _qdrant_client.create_collection(
                    collection_name=name,
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
# チャンク品質フィルタ
# =====================================================

def is_valid_chunk(text: str) -> bool:
    """低品質チャンクを除外する"""
    # 短すぎる（日本語は1文字あたりの情報量が多いため30文字）
    if len(text) < 30:
        return False
    # 記号だらけ（コード断片・壊れたデータ）
    # スペースも記号に含まれるため isalpha でなく isalnum を使用
    # ただしURLやコードブロックが混在するため閾値は0.6に設定
    symbol_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text)
    if symbol_ratio > 0.6:
        return False
    # 改行だらけ（構造崩壊）
    if text.count("\n") > len(text) * 0.3:
        return False
    return True


# =====================================================
# Markdown分割
# =====================================================

def split_markdown(
    text:      str,
    source:    str,
    max_chars: int = 800,
    doc_id:    str = None,
    version:   str = None,
) -> list:
    """ヘッダー単位で分割。コードブロック保護・空chunk除外。"""
    chunks      = []
    code_blocks = {}

    def replace_code(m):
        key = f"__CODE_{len(code_blocks)}__"
        code_blocks[key] = m.group(0)
        return key

    protected = re.sub(r"```.*?```", replace_code, text, flags=re.DOTALL)
    sections  = re.split(r"(?=^#{1,3} )", protected, flags=re.MULTILINE)

    for section in sections:
        for key, code in code_blocks.items():
            section = section.replace(key, code)
        section = section.strip()
        if not section or len(section) < 20:
            continue
        base_meta = {"source": source}
        if doc_id:
            base_meta["doc_id"]  = doc_id
        if version:
            base_meta["version"] = version
        if len(section) <= max_chars:
            if is_valid_chunk(section):
                chunks.append({"text": section, **base_meta})
        else:
            for i in range(0, len(section), max_chars):
                chunk = section[i:i + max_chars].strip()
                if chunk and is_valid_chunk(chunk):
                    chunks.append({"text": chunk, **base_meta})

    return chunks


# =====================================================
# インデックス構築（ニュース・論文）
# =====================================================

def index_knowledge() -> int:
    """knowledge/ のMarkdownを knowledge コレクションにupsertする"""
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
                        "text":         chunk["text"],
                        "source":       chunk["source"],
                        "length":       len(chunk["text"]),
                        "trust":        0.75,
                        "collected_at": datetime.now().isoformat(),
                    }
                ))
            client.upsert(collection_name="knowledge", points=points)
            total += len(points)
        except Exception as e:
            print(f"  ⚠️ {md_file.name}: {e}")

    print(f"  ✅ knowledgeインデックス完了: {total}チャンク")
    return total


# =====================================================
# 公式ドキュメント管理（永久保存）
# =====================================================

def index_official_doc(
    doc_id:  str,
    content: str,
    source:  str,
    version: str = "latest",
    force:   bool = False,
) -> int:
    """
    公式ドキュメントを official_docs コレクションに保存する。
    Args:
        doc_id:  ドキュメントID（例: "python_3.14", "japanese_copyright_law"）
        content: ドキュメントのテキスト内容
        source:  出典URL
        version: バージョン文字列
        force:   Trueなら既存を上書き（バージョン更新時）
    """
    from qdrant_client.models import PointStruct

    client = get_client()

    # 既存チャンク確認（バージョン変化がなければスキップ）
    if not force:
        existing = _get_doc_version(doc_id)
        if existing == version:
            print(f"  ℹ️ スキップ（最新版）: {doc_id} v{version}")
            return 0
        elif existing:
            print(f"  🔄 バージョン更新: {doc_id} {existing} → {version}")
            _delete_doc(client, doc_id)

    chunks = split_markdown(content, source, doc_id=doc_id, version=version)
    if not chunks:
        return 0

    texts   = [c["text"] for c in chunks]
    vectors = embed(texts)
    points  = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        uid = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{doc_id}:{version}:{i}"
        ))
        points.append(PointStruct(
            id=uid,
            vector=vec,
            payload={
                "text":    chunk["text"],
                "source":  chunk["source"],
                "doc_id":  doc_id,
                "version": version,
                "length":  len(chunk["text"]),
                "trust":   0.9,
            }
        ))

    client.upsert(collection_name="official_docs", points=points)
    _save_doc_meta(doc_id, version, source, len(points))
    print(f"  ✅ 公式ドキュメント登録: {doc_id} v{version} ({len(points)}チャンク)")
    return len(points)


def _get_doc_version(doc_id: str) -> str | None:
    """登録済みドキュメントのバージョンを確認する"""
    meta_path = AGENT_ROOT / "memory" / "official_docs_meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return meta.get(doc_id, {}).get("version")


def _delete_doc(client, doc_id: str):
    """古いバージョンのドキュメントを削除する"""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    client.delete(
        collection_name="official_docs",
        points_selector=Filter(
            must=[FieldCondition(
                key="doc_id",
                match=MatchValue(value=doc_id),
            )]
        ),
    )


def _save_doc_meta(doc_id: str, version: str, source: str, chunks: int):
    """ドキュメントのメタデータを保存する"""
    meta_path = AGENT_ROOT / "memory" / "official_docs_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta[doc_id] = {
        "version":      version,
        "source":       source,
        "chunks":       chunks,
        "last_updated": datetime.now().isoformat(),
    }
    meta_path.parent.mkdir(exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def list_official_docs() -> dict:
    """登録済み公式ドキュメント一覧を返す"""
    meta_path = AGENT_ROOT / "memory" / "official_docs_meta.json"
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


# =====================================================
# 検索（両コレクションを横断）
# =====================================================

def _calc_freshness(collected_at: str) -> float:
    """収集日時から新鮮度スコアを計算する（knowledge 専用）"""
    if not collected_at:
        return 0.7
    try:
        dt   = datetime.fromisoformat(collected_at)
        days = (datetime.now() - dt).days
        if days < 3:  return 1.0
        if days < 7:  return 0.9
        if days < 30: return 0.75
        return 0.6
    except Exception:
        return 0.7


def _should_use(scores: list, col: str = "official_docs") -> bool:
    if not scores:
        return False
    top       = scores[0]
    min_score = 0.45 if col == "official_docs" else 0.38
    if top < min_score:
        return False
    # top >= 0.60 は高信頼 → gap 不問で採用
    if top >= 0.60:
        return True
    if len(scores) == 1:
        return True
    # BGE-M3 + 日本語はスコアが接近しやすいため gap 閾値は緩く設定
    gap = (top - scores[1]) / top
    return gap > 0.01


def search(
    query:       str,
    top_k:       int = 3,
    collections: list = None,
) -> list:
    """
    クエリに関連するチャンクを検索する。
    official_docs を優先してマージする。
    """
    if collections is None:
        collections = ["official_docs", "knowledge"]

    client      = get_client()
    vec         = embed([query])[0]
    all_results = []

    for col in collections:
        try:
            response = client.query_points(
                collection_name=col,
                query=vec,
                limit=top_k + 2,
            )
            results = response.points
            if not results:
                continue
            scores = [r.score for r in results]
            if not _should_use(scores, col):
                continue
            min_score = 0.45 if col == "official_docs" else 0.38
            for r in results[:top_k]:
                if r.score >= min_score:
                    trust = r.payload.get("trust", 0.7)
                    if col == "knowledge":
                        freshness     = _calc_freshness(r.payload.get("collected_at", ""))
                        adjusted_score = r.score * trust * freshness
                    else:
                        adjusted_score = r.score * trust
                    all_results.append({
                        "text":         r.payload["text"],
                        "source":       r.payload["source"],
                        "score":        adjusted_score,
                        "raw_score":    r.score,
                        "trust":        trust,
                        "collection":   col,
                        "doc_id":       r.payload.get("doc_id", ""),
                        "collected_at": r.payload.get("collected_at", ""),
                    })
        except Exception:
            pass

    # スコア順ソート後に重複除去
    all_results.sort(key=lambda x: -x["score"])
    seen:    set  = set()
    deduped: list = []
    for r in all_results:
        key = r["text"][:100]
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped[:top_k]


def format_context(results: list, max_chars: int = 1500) -> str:
    """検索結果をLLM用コンテキストに整形する"""
    if not results:
        return ""
    context = ""
    for i, r in enumerate(results, 1):
        col_label = "📚公式" if r["collection"] == "official_docs" else "📰最新"
        snippet   = r["text"][:300]
        context  += (
            f"[{col_label}知識{i}] (score={r['score']:.2f})\n"
            f"{snippet}\n\n"
        )
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


# --- RAG DEBUG START ---
RAG_LOG_FILE = AGENT_ROOT / "logs" / "rag_search_log.jsonl"


def debug_rag(query: str, top_k: int = 5) -> list:
    """
    RAG検索のデバッグ出力。
    どのチャンクが使われたか・スコア分布を表示する。
    """
    results = search(query, top_k=top_k)
    print(f"\n{'='*50}")
    print(f"  RAG DEBUG")
    print(f"  Query: {query}")
    print(f"  ヒット: {len(results)}件")
    print(f"{'='*50}")
    if not results:
        print("  ヒットなし（スコア閾値以下または空）")
        _log_rag_search(query, results)
        return []
    # スコア分布
    scores = [r["score"] for r in results]
    print(f"\n  スコア分布:")
    print(f"    max={max(scores):.3f}  min={min(scores):.3f}  "
          f"avg={sum(scores)/len(scores):.3f}")
    # コレクション比率
    cols = {}
    for r in results:
        cols[r["collection"]] = cols.get(r["collection"], 0) + 1
    print(f"  コレクション: {cols}")
    # 各チャンクの詳細
    print()
    for i, r in enumerate(results, 1):
        col_label = "📚公式" if r["collection"] == "official_docs" else "📰最新"
        print(f"  [{i}] score={r['score']:.3f} raw={r.get('raw_score',0):.3f} "
              f"trust={r.get('trust',0)} {col_label}")
        print(f"       source: {r['source'][:60]}")
        print(f"       text:   {r['text'][:120].replace(chr(10), ' ')}")
        print()
    # ログに記録
    _log_rag_search(query, results)
    return results


def _log_rag_search(query: str, results: list):
    """検索結果をJSONLinesに記録する"""
    RAG_LOG_FILE.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp":  datetime.now().isoformat(),
        "query":      query,
        "hit_count":  len(results),
        "results": [
            {
                "score":      r["score"],
                "raw_score":  r.get("raw_score", 0),
                "trust":      r.get("trust", 0),
                "collection": r["collection"],
                "source":     r["source"],
                "text_head":  r["text"][:100],
            }
            for r in results
        ],
    }
    with open(RAG_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def show_rag_stats(last_n: int = 50) -> str:
    """検索ログの統計を表示する"""
    if not RAG_LOG_FILE.exists():
        return "ログなし"
    entries = []
    with open(RAG_LOG_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except Exception:
                pass
    entries = entries[-last_n:]
    if not entries:
        return "ログなし"
    total      = len(entries)
    zero_hits  = sum(1 for e in entries if e["hit_count"] == 0)
    all_scores = [r["score"] for e in entries for r in e["results"]]
    col_counts = {}
    for e in entries:
        for r in e["results"]:
            c = r["collection"]
            col_counts[c] = col_counts.get(c, 0) + 1
    lines = [
        f"## RAG検索統計（直近{total}件）",
        f"ヒットなし: {zero_hits}/{total} ({zero_hits/total*100:.0f}%)",
    ]
    if all_scores:
        lines.append(
            f"スコア: avg={sum(all_scores)/len(all_scores):.3f} "
            f"max={max(all_scores):.3f} min={min(all_scores):.3f}"
        )
    lines.append(f"コレクション比率: {col_counts}")
    return "\n".join(lines)
# --- RAG DEBUG END ---
