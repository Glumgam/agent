from llm import ask_planner


# --- THINKING PLANNER START ---
def _is_complex_task(task: str) -> bool:
    """複雑タスクかどうかを判定する"""
    complexity_indicators = [
        len(task) > 200,
        task.count("\n") > 3,
        any(w in task.lower() for w in [
            "複数", "連携", "pipeline", "api",
            "flask", "database", "complex", "設計"
        ]),
    ]
    return sum(complexity_indicators) >= 2


def plan(task: str) -> str:
    """
    タスクの複雑さに応じてモデルを使い分ける。
    シンプル → qwen2.5-coder:7b（高速）
    複雑    → qwen3.5:9b（深い推論）
    """
    from llm import ask_thinking
    prompt = f"""
Break this task into 3-6 steps.

Task:
{task}

Return bullet points.
"""
    if _is_complex_task(task):
        print("  🧠 複雑タスク検出 → thinking モデルを使用")
        return ask_thinking(
            f"以下のタスクの実行計画を日本語で作成してください:\n{task}"
        )
    else:
        return ask_planner(prompt)
# --- THINKING PLANNER END ---
