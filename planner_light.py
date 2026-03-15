from llm import ask_planner


def plan(task):
    prompt = f"""
Break this task into 3-6 steps.

Task:
{task}

Return bullet points.
"""

    return ask_planner(prompt)
