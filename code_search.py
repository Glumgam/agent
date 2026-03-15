import vector_store


def search_code(query: str):
    from code_indexer import ensure_index
    ensure_index()
    results = vector_store.search(query, top_k=5)
    output = []
    for item in results:
        output.append(
            {
                "path": item.get("path", ""),
                "snippet": item.get("text", ""),
            }
        )
    return output
