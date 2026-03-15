from tools.research_planner import create_research_plan


def _task_name(task) -> str:
    if isinstance(task, dict):
        return (task.get("task") or "").strip()
    return str(task or "").strip()


def _normalize_task(task, default_priority: int = 2, source: str = "subgoal") -> dict:
    name = _task_name(task)
    if not name:
        return {}
    if isinstance(task, dict):
        return {
            "task": name,
            "priority": int(task.get("priority", default_priority)),
            "source": task.get("source", source),
            "status": task.get("status", "pending"),
        }
    return {
        "task": name,
        "priority": default_priority,
        "source": source,
        "status": "pending",
    }


def create_task_queue(goal: str) -> list:
    if not goal:
        return []
    plan = create_research_plan(goal)
    queue = []
    for item in plan:
        queue.append(
            {
                "task": item,
                "priority": 1,
                "source": "goal",
                "status": "pending",
            }
        )
    return queue


def add_task(queue: list, task):
    normalized = _normalize_task(task)
    if not normalized:
        return
    name = normalized["task"]
    for existing in queue:
        if _task_name(existing) == name:
            return
    queue.append(normalized)
