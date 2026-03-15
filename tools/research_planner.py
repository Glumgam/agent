import re


def _extract_version(goal: str) -> str:
    if not goal:
        return ""
    m = re.search(r"(Python\\s*\\d+\\.\\d+)", goal, re.IGNORECASE)
    if m:
        return m.group(1).replace(" ", "")
    return ""


def create_research_plan(goal: str) -> list:
    if not goal:
        return []

    goal_lower = goal.lower()
    version = _extract_version(goal) or "Python 3"

    queries = []

    if "release" in goal_lower or "schedule" in goal_lower:
        queries.append(f"{version} release schedule")

    if "change" in goal_lower or "changes" in goal_lower or "explain" in goal_lower:
        queries.extend([
            f"{version} new features",
            f"{version} performance improvements",
            f"{version} compatibility changes",
        ])

    if not queries:
        queries = [
            f"{version} release schedule",
            f"{version} new features",
            f"{version} performance improvements",
        ]

    # de-dup and limit to 3-5 queries
    seen = set()
    uniq = []
    for q in queries:
        if q in seen:
            continue
        seen.add(q)
        uniq.append(q)

    if len(uniq) < 3:
        uniq.append(f"{version} features")
    uniq = uniq[:5]
    return uniq
