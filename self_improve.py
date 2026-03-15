import json
import re

from llm import ask_planner, ask_coder
from parser import extract_json


FORBIDDEN_PATTERNS = [
    r"rm\s+-rf",
    r"os\.remove",
    r"shutil\.rmtree",
    r"\brmtree\s*\(",
    r"\bos\.rmdir\b",
    r"\bunlink\s*\(",
]


def _contains_forbidden(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, lowered):
            return True
    return False


def analyze_failure(task, history, result):
    """
    Use LLM to analyze failure reasons based on task, history, and result.
    Returns plain text analysis.
    """
    history_lines = []
    for h in history[-6:]:
        action = h.get("action", {})
        tool = action.get("tool", "")
        path = action.get("path", "")
        command = action.get("command", "")
        res = str(h.get("result", ""))[:500]
        history_lines.append(f"- tool={tool} path={path} cmd={command} result={res}")

    prompt = (
        "Analyze why the agent failed and suggest a concrete fix direction.\n\n"
        f"Task:\n{task}\n\n"
        "Recent history:\n"
        + "\n".join(history_lines)
        + "\n\n"
        f"Latest result:\n{str(result)[:1000]}\n\n"
        "Return a short diagnosis and a fix strategy."
    )

    try:
        analysis = ask_planner(prompt)
        return analysis.strip()
    except Exception:
        return "analysis failed"


def propose_fix(analysis):
    """
    Use LLM to propose a safe patch based on analysis.
    Returns dict: {path, content} or error dict.
    """
    prompt = (
        "You are generating a safe patch to fix an agent failure.\n"
        "Return ONLY valid JSON with keys: path, content.\n"
        "The content must be the full file content after the fix.\n"
        "Do NOT include dangerous deletions or system file removal.\n"
        "Forbidden patterns: rm -rf, os.remove, shutil.rmtree.\n\n"
        f"Analysis:\n{analysis}\n"
    )

    response = ask_coder(prompt)
    patch = extract_json(response)

    if not isinstance(patch, dict):
        return {"error": "invalid patch format"}

    path = patch.get("path", "")
    content = patch.get("content", "")
    if not path or content is None:
        return {"error": "missing path or content"}

    if _contains_forbidden(str(content)):
        return {"error": "forbidden pattern detected in patch"}

    return {"path": path, "content": content}
