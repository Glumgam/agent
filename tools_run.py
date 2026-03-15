"""
tools_run.py — カテゴリD: 実行系ツール

- tool_run / tool_run_test / tool_run_tests
- tool_generate_test / tool_done / tool_ask_user
"""

from command_runner import run_command
from tool_result import ToolResult

try:
    from tools.run_tests import run_tests
except ImportError:
    def run_tests():
        return "Error: run_tests not implemented"

try:
    from test_generator import generate_test
except ImportError:
    def generate_test(path, code):
        return "Error: generate_test not implemented"

try:
    from llm_router import code as llm_code
except ImportError:
    def llm_code(prompt: str) -> str:
        return ""


def _run_ok(output: str) -> bool:
    return "exit code 0" in output


def tool_run(action: dict):
    raw = run_command(action.get("command", ""))
    return ToolResult(ok=_run_ok(raw), output=raw)


def tool_run_test(action: dict):
    command = action.get("command")
    if not command:
        path = action.get("path", "").strip()
        if path:
            command = f"python -m pytest -q {path}"
        else:
            command = "python -m pytest -q"
    raw = run_command(command)
    return ToolResult(ok=_run_ok(raw), output=raw)


def tool_run_tests(action: dict):
    raw = run_tests()
    ok = not (isinstance(raw, str) and raw.lower().startswith("error"))
    return ToolResult(ok=ok, output=str(raw))


def tool_generate_test(action: dict):
    code = action.get("content") or action.get("code", "")
    file_name = action["path"]
    prompt = f"""
次のPythonコードのpytestテストを書いてください。

ファイル:
{file_name}

コード:
{code}

pytest形式で出力してください。
"""
    response = llm_code(prompt)
    if response:
        return ToolResult(ok=True, output=response)
    raw = generate_test(file_name, code)
    ok = not (isinstance(raw, str) and raw.startswith("Error"))
    return ToolResult(ok=ok, output=str(raw))


def tool_done(action: dict):
    return ToolResult(ok=True, output="Task completed")


def tool_answer(action: dict):
    content = action.get("content", "").strip()
    if not content:
        return ToolResult(ok=False, output="Error: content is required")
    return ToolResult(ok=True, output=content)


def tool_ask_user(action: dict):
    question = action.get("question", "").strip()
    if not question:
        return ToolResult(ok=False, output="Error: question is required")
    print(f"\nUSER QUESTION:\n{question}\n")
    try:
        answer = input().strip()
        return ToolResult(ok=True, output=answer)
    except Exception as e:
        return ToolResult(ok=False, output=f"Error: failed to read input: {e}")
