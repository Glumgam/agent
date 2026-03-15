from llm import ask
from parser import extract_json


def _repair_json(response: str):
    if not response:
        return None
    repair_prompt = f"""
The previous output was not valid JSON.

Output:
{response[:500]}

Return ONLY valid JSON.
"""
    repaired = ask(repair_prompt)
    return extract_json(repaired)


def generate_candidates(prompt, k=2):
    candidates = []
    for _ in range(k):
        response = ask(prompt)
        action = extract_json(response)
        if not action:
            action = _repair_json(response)
        if action:
            candidates.append(action)
    return candidates


def score_candidate(task, candidate):
    if not isinstance(candidate, dict):
        return 1
    score = 5
    tool = candidate.get("tool")
    thought = candidate.get("thought")
    if tool:
        score += 2
    if thought:
        score += 1

    if tool in ("create_file", "write_file", "edit_file", "diff_edit", "append_file"):
        if candidate.get("path"):
            score += 1
        if tool == "diff_edit":
            if candidate.get("old") and candidate.get("new"):
                score += 1
    if tool in ("read_file", "read_directory", "make_dir"):
        if candidate.get("path"):
            score += 1
    if tool in ("run", "run_test"):
        if candidate.get("command") or candidate.get("path"):
            score += 1
    if tool == "done":
        score += 1

    if score < 1:
        return 1
    if score > 10:
        return 10
    return score


def select_best(candidates, task: str = ""):
    if not candidates:
        return {}
    best = candidates[0]
    best_score = None
    for cand in candidates:
        try:
            score = score_candidate(task, cand)
        except Exception:
            score = None
        if score is None:
            continue
        if best_score is None or score > best_score:
            best = cand
            best_score = score
    return best
