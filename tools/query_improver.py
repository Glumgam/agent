import re


def improve_query(query: str, error: str) -> str:
    if not query:
        return query

    q = query.strip()
    q_lower = q.lower()

    # Remove generic words
    generic = ["explain", "overview", "details", "summary", "introduction"]
    for g in generic:
        q_lower = q_lower.replace(g, "")

    q_clean = re.sub(r"\s+", " ", q_lower).strip()

    # Add version number if missing
    if "python" in q_clean and not re.search(r"python\\s*\\d+\\.\\d+", q_clean):
        q_clean = q_clean.replace("python", "python 3.13", 1)

    # Add authoritative site if no site hint
    if "site:" not in q_clean:
        q_clean = f"{q_clean} site:python.org"

    # Ensure original structure if cleaned too short
    if len(q_clean) < 5:
        q_clean = q
        if "python" in q_clean.lower() and "3.13" not in q_clean:
            q_clean = q_clean + " 3.13"
        if "site:" not in q_clean.lower():
            q_clean = q_clean + " site:python.org"

    return q_clean.strip()
