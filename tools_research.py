"""
tools_research.py — カテゴリE: 研究・上位ロジック (LLM呼び出しを含む)

- _parse_plan_list / _llm_plan_queries / _llm_improve_query
- tool_search_web / tool_fetch_page / tool_extract_text
- tool_create_research_plan / tool_search_knowledge / tool_search_code
- tool_run_task_loop / tool_self_improve_agent
"""

import json
import os

from project_map import safe_path, WORKSPACE
from tool_result import ToolResult

try:
    from tools.web_tools import search_web, fetch_page, extract_text, summarize_text
    from tools.research_planner import create_research_plan
    from tools.report_generator import generate_report
    from tools.query_improver import improve_query
    from tools.knowledge_base import search_knowledge, store_knowledge, knowledge_confidence
    from tools import research_notes
    from tools.task_queue import create_task_queue, add_task
    from tools.subgoal_discovery import discover_subgoals
    from tools.error_memory import record_error
    from tools.error_analyzer import analyze_errors
    from tools.patch_generator import generate_patch_prompt
    from tools.task_memory import load_tasks, save_tasks
    from llm_router import plan as llm_plan, code as llm_code
    from code_search import search_code
except ImportError:

    def search_web(query):
        return {"status": "error", "message": "search_web not implemented"}

    def fetch_page(url):
        return {"status": "error", "message": "fetch_page not implemented"}

    def extract_text(html):
        return {"status": "error", "message": "extract_text not implemented"}

    def summarize_text(text):
        return {"status": "error", "message": "summarize_text not implemented"}

    def generate_report(query, **kwargs):
        return {"status": "error", "message": "generate_report not implemented"}

    def create_research_plan(goal):
        return []

    def improve_query(query, error):
        return query

    def search_knowledge(query):
        return []

    def store_knowledge(note):
        return {"status": "error", "message": "store_knowledge not implemented"}

    def knowledge_confidence(entries, query):
        return 0.0

    class _ResearchNotesFallback:
        @staticmethod
        def save_note(note: dict) -> dict:
            return note

        @staticmethod
        def extract_research_notes(page_data: dict) -> dict:
            return page_data

    research_notes = _ResearchNotesFallback()

    def create_task_queue(goal):
        return []

    def add_task(queue, task):
        return None

    def discover_subgoals(notes):
        return []

    def record_error(task, error_message):
        return {"status": "error", "message": "record_error not implemented"}

    def analyze_errors():
        return []

    def generate_patch_prompt(error_summary):
        return []

    def load_tasks():
        return []

    def save_tasks(queue):
        return {"status": "error", "message": "save_tasks not implemented"}

    def llm_plan(prompt: str) -> str:
        return ""

    def llm_code(prompt: str) -> str:
        return ""

    def search_code(query: str):
        return []


_SEARCHED_QUERIES = set()
_LAST_SEARCH_URL = ""
_EXTRACT_TEXT_USED = False


def _rewrite_query_simple(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return q

    # Split digits from text (e.g., "ベスト5" -> "ベスト 5")
    q = re.sub(r"(\D)(\d)", r"\1 \2", q)
    q = re.sub(r"(\d)(\D)", r"\1 \2", q)

    jp_particles = [
        "で", "が", "に", "は", "を", "と", "も", "へ", "から", "まで", "より"
    ]
    for p in jp_particles:
        q = q.replace(p, " ")

    q = re.sub(r"[、。・/\\-]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    tokens = [t for t in q.split(" ") if t]

    stopwords = {
        "a", "an", "the", "of", "in", "on", "for", "to", "and", "or", "is",
        "are", "with", "about", "from", "by", "at", "as", "it", "this",
        "that", "these", "those", "what", "when", "where", "who", "why", "how",
        "です", "ます", "こと", "もの", "ため", "など"
    }

    filtered = []
    seen = set()
    for t in tokens:
        tl = t.lower()
        if tl in stopwords:
            continue
        if tl in seen:
            continue
        seen.add(tl)
        filtered.append(t)

    if not filtered:
        return query

    rewritten_tokens = filtered[:]

    # Add simple ranking hints for "ベスト"/"ランキング"/"top"
    ranking_markers = {"ベスト", "ランキング", "順位", "top", "best"}
    if any(m in q.lower() for m in ["top", "best"]) or any(m in tokens for m in ["ベスト", "ランキング", "順位"]):
        if "ランキング" not in rewritten_tokens:
            rewritten_tokens.append("ランキング")
        if "有名" not in rewritten_tokens:
            rewritten_tokens.append("有名")

    # Add locale hint for Japanese queries when missing
    if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", q):
        if all(loc not in q for loc in ["日本", "国内", "東京", "大阪", "北海道", "福岡"]):
            if "日本" not in rewritten_tokens:
                rewritten_tokens.insert(0, "日本")

    rewritten = " ".join(rewritten_tokens).strip()
    if len(rewritten) < 3:
        return query
    return rewritten


# -------------------------
# LLM RESEARCH HELPERS
# -------------------------

def _parse_plan_list(text: str) -> list:
    if not text:
        return []
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("plan", [])
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except Exception:
            pass

    lines = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if line:
            lines.append(line)
    return lines[:5]


def _llm_plan_queries(goal: str) -> list:
    if not goal:
        return []
    prompt = (
        "Create 3-5 concise research queries for the following goal. "
        "Return ONLY a JSON array of strings.\n\n"
        f"Goal: {goal}"
    )
    response = llm_plan(prompt)
    return _parse_plan_list(response)


def _llm_improve_query(query: str, error: str) -> str:
    if not query:
        return ""
    prompt = (
        "Improve the search query based on the error. "
        "Return ONLY the improved query string.\n\n"
        f"Query: {query}\n"
        f"Error: {error}"
    )
    response = llm_plan(prompt)
    if not response:
        return ""
    return response.splitlines()[0].strip()


# -------------------------
# TOOL FUNCTIONS
# -------------------------

def tool_search_web(action: dict):
    query = action.get("query", "")
    top_k = int(action.get("top_k", 3))
    if top_k > 3:
        top_k = 3
    if not query:
        return {"status": "error", "message": "query is required"}
    if query in _SEARCHED_QUERIES:
        return {"status": "error", "message": "search_web already called for this query"}
    _SEARCHED_QUERIES.add(query)
    rewritten = _rewrite_query_simple(query)
    results = search_web(rewritten, top_k=top_k)
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict) and first.get("url"):
            global _LAST_SEARCH_URL
            _LAST_SEARCH_URL = first.get("url")
    return results


def tool_fetch_page(action: dict):
    url = action.get("url", "").strip()
    if not url:
        url = _LAST_SEARCH_URL
    return fetch_page(url)


def tool_extract_text(action: dict):
    global _EXTRACT_TEXT_USED
    if _EXTRACT_TEXT_USED:
        return {"status": "error", "message": "extract_text already used in this session"}
    if "path" in action:
        return {"status": "error", "message": "extract_text only accepts html field, not path"}
    if "content" in action:
        return {"status": "error", "message": "extract_text only accepts html field, not content"}
    html = action.get("html", "")
    if isinstance(html, str):
        candidate = html.strip()
        if candidate and os.path.exists(candidate):
            return {"status": "error", "message": "extract_text expects HTML, not a file path"}
    _EXTRACT_TEXT_USED = True
    return extract_text(html)


def tool_summarize_text(action: dict):
    return summarize_text(action.get("text", ""))


def tool_generate_report(action: dict):
    summaries = action.get("summaries")
    if isinstance(summaries, list):
        cleaned = [str(s).strip() for s in summaries if str(s).strip()]
        if not cleaned:
            return ""
        return "\n\n".join(cleaned)
    query = action.get("query", "") or action.get("goal", "")
    return generate_report(query)


def tool_create_research_plan(action: dict):
    goal = action.get("goal", "")
    knowledge = search_knowledge(goal)
    confidence = knowledge_confidence(knowledge, goal)
    knowledge_first = confidence > 0.6 and len(knowledge) >= 2
    plan = [] if knowledge_first else create_research_plan(goal)
    if not knowledge_first:
        llm_plan_list = _llm_plan_queries(goal)
        if llm_plan_list:
            plan = llm_plan_list

    report = None
    if knowledge_first:
        report = generate_report(goal, entries=knowledge)

    return {
        "plan": plan,
        "knowledge": knowledge,
        "knowledge_hits": len(knowledge),
        "knowledge_confidence": confidence,
        "knowledge_first": knowledge_first,
        "report": report,
    }


def tool_search_knowledge(action: dict):
    return search_knowledge(action.get("query", "") or action.get("goal", ""))


def tool_search_code(action: dict):
    return search_code(action.get("query", ""))


def tool_run_task_loop(action: dict):
    goal = action.get("goal", "")
    max_tasks = int(action.get("max_tasks", 10))
    queue = load_tasks()
    if not queue:
        queue = create_task_queue(goal)

    def _ensure_task_fields(task_item: dict) -> dict:
        task_item.setdefault("priority", 1)
        task_item.setdefault("status", "pending")
        task_item.setdefault("retry_count", 0)
        return task_item

    queue = [_ensure_task_fields(item) for item in queue if isinstance(item, dict)]
    save_tasks(queue)

    log_dir = safe_path("logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = safe_path("logs/task_loop.log")

    log = []

    def _append_log(line: str):
        log.append(line)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    _append_log(f"task_queue created: {queue}")

    tasks_run = 0
    while queue and tasks_run < max_tasks:
        queue.sort(
            key=lambda item: (
                0 if item.get("status") == "pending" else 1,
                item.get("priority", 1),
                item.get("retry_count", 0),
            )
        )
        next_index = None
        for idx, item in enumerate(queue):
            if item.get("status") == "pending":
                next_index = idx
                break
        if next_index is None:
            break

        task_entry = queue[next_index]
        task_name = task_entry.get("task", "")
        task_entry["status"] = "running"
        save_tasks(queue)
        _append_log(f"task status: {task_name} -> running")
        _append_log(f"task executed: {task_name}")

        res = search_web(task_name, top_k=5)
        if not res:
            message = "search failed"
            _append_log(f"task search failed: {message}")
            record_error(task_name, message)
            _append_log(f"error recorded: {message}")
            if task_entry.get("retry_count", 0) < 2:
                task_entry["retry_count"] = task_entry.get("retry_count", 0) + 1
                task_entry["status"] = "pending"
                _append_log(f"task retry scheduled: {task_name} -> {task_entry['retry_count']}")
            else:
                task_entry["status"] = "failed"
                _append_log(f"task status: {task_name} -> failed")
            save_tasks(queue)
            tasks_run += 1
            continue

        urls = [r.get("url") for r in res if isinstance(r, dict) and r.get("url")]
        notes = []
        if urls:
            html_doc = fetch_page(urls[0])
            if not html_doc:
                message = "fetch failed"
                _append_log(f"task fetch failed: {message}")
                record_error(task_name, message)
                _append_log(f"error recorded: {message}")
                if task_entry.get("retry_count", 0) < 2:
                    task_entry["retry_count"] = task_entry.get("retry_count", 0) + 1
                    task_entry["status"] = "pending"
                    _append_log(f"task retry scheduled: {task_name} -> {task_entry['retry_count']}")
                else:
                    task_entry["status"] = "failed"
                    _append_log(f"task status: {task_name} -> failed")
                save_tasks(queue)
                tasks_run += 1
                continue
            else:
                content = ""
                if html_doc:
                    extracted = extract_text(html_doc)
                    if isinstance(extracted, dict):
                        content = extracted.get("data", "") or ""
                    else:
                        content = extracted or ""
                title = ""
                if res and isinstance(res[0], dict):
                    title = res[0].get("title", "")
                page_data = {
                    "url": urls[0],
                    "title": title,
                    "content": content,
                }
                note = research_notes.extract_research_notes(page_data)

                if note:
                    research_notes.save_note(note)
                    store_knowledge(note)
                    _append_log(
                        f"knowledge stored: {note.get('title') or note.get('url', '')}"
                    )
                    notes.append(note)

        new_tasks = discover_subgoals(notes)
        if new_tasks:
            for nt in new_tasks:
                priority = 1 if "PEP" in nt else 2
                add_task(
                    queue,
                    {
                        "task": nt,
                        "priority": priority,
                        "source": "subgoal",
                        "status": "pending",
                        "retry_count": 0,
                    },
                )
                _append_log(f"subgoal discovered: {nt}")
                _append_log(f"task added: {nt}")

        task_entry["status"] = "completed"
        save_tasks(queue)
        _append_log(f"task status: {task_name} -> completed")
        tasks_run += 1

    report = generate_report(goal)
    data = {
        "status": "ok",
        "log": log,
        "report": report,
    }
    output = "\n".join(log)
    if report:
        output += f"\n\nREPORT:\n{report}"
    return ToolResult(ok=True, output=output, data=data)


def tool_self_improve_agent(action: dict):
    summary = analyze_errors()
    prompts = generate_patch_prompt(summary)
    log = []

    if summary:
        for item in summary:
            log.append(
                f"error analyzer detected {item.get('type')} (count={item.get('count')})"
            )
    else:
        log.append("error analyzer detected no errors")

    patch_suggestions = []
    if prompts:
        for item in prompts:
            file_name = item.get("file")
            prompt = item.get("prompt", "")
            full_prompt = (
                "Suggest a concise patch plan for the following file. "
                "Return plain text steps.\n\n"
                f"File: {file_name}\n"
                f"Task: {prompt}"
            )
            suggestion_text = llm_code(full_prompt)
            patch_suggestions.append(
                {
                    "file": file_name,
                    "prompt": prompt,
                    "suggestion": suggestion_text,
                }
            )
            log.append(
                "patch suggested: "
                f"{file_name} -> {suggestion_text or prompt}"
            )
    else:
        log.append("patch suggested: none")

    data = {
        "status": "ok",
        "error_summary": summary,
        "patch_suggestions": patch_suggestions,
        "log": log,
    }
    output = "\n".join(log)
    return ToolResult(ok=True, output=output, data=data)
