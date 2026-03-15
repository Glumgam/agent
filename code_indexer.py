import os

from project_map import IGNORE_DIRS
import vector_store


SUPPORTED_EXT = {".py", ".js", ".ts", ".md", ".txt"}
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MAX_FILE_SIZE = 200_000

_index_ready = False


def chunk_text(text, size=800, overlap=100):
    chunks = []
    start = 0
    if size <= 0:
        return chunks
    step = max(1, size - overlap)
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += step
    return chunks


def _should_index_file(name: str) -> bool:
    _, ext = os.path.splitext(name)
    return ext.lower() in SUPPORTED_EXT


def build_index(root: str = None):
    if root is None:
        root = os.getcwd()

    ignore_dirs = set(IGNORE_DIRS)
    ignore_dirs.add("workspace")

    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if not _should_index_file(file):
                continue
            path = os.path.join(current, file)
            try:
                size = os.path.getsize(path)
                if size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue
            rel_path = os.path.relpath(path, root)
            chunks = chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
            for chunk in chunks:
                if chunk.strip():
                    vector_store.add_document(rel_path, chunk)


def ensure_index():
    global _index_ready
    if _index_ready:
        return
    vector_store.create_index()
    if vector_store.search("sanity_check", top_k=1):
        _index_ready = True
        return
    build_index()
    _index_ready = True
