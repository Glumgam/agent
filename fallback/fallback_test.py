"""
fallback/fallback_test.py — テスト実行系フォールバックハンドラー
pytest 作成・実行・修正ループを処理する
"""

import os
from typing import Dict, List

from fallback.fallback_helpers import (
    _extract_all_paths,
    _extract_filename,
    _history_success,
    _history_has_tool,
    _is_bank_task,
    _extract_function_name,
    _last_result_for_tool,
    _last_index,
    _last_read_content,
    _last_run_command_index,
    _needs_pytest_install,
)


def _diff_edit_attempted_for(
    history: List[Dict], code_path: str, old_text: str, new_text: str
) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "diff_edit":
            continue
        if action.get("path") != code_path:
            continue
        if action.get("old") == old_text and action.get("new") == new_text:
            return True
    return False


def _last_diff_edit_index_for(
    history: List[Dict], code_path: str, old_text: str, new_text: str
) -> int:
    for i in range(len(history) - 1, -1, -1):
        action = history[i].get("action", {})
        if action.get("tool") != "diff_edit":
            continue
        if action.get("path") != code_path:
            continue
        if action.get("old") == old_text and action.get("new") == new_text:
            return i
    return -1


def handle_test(task: str, history: List[Dict]) -> Dict:
    task_lower = task.lower()

    paths = _extract_all_paths(task)
    filename = _extract_filename(task)

    code_path = None
    test_path = None

    for p in paths:
        base = os.path.basename(p)
        if p.startswith("tests/") or base.startswith("test_") or base.endswith("_test.py") or "test" in base:
            if not test_path:
                test_path = p
        else:
            if not code_path:
                code_path = p

    if not code_path and filename:
        code_path = filename

    if code_path and not test_path:
        module = os.path.splitext(os.path.basename(code_path))[0]
        test_path = f"tests/test_{module}.py"

    if not code_path:
        code_path = "math_utils.py"

    if not test_path:
        module = os.path.splitext(os.path.basename(code_path))[0]
        test_path = f"tests/test_{module}.py"

    bank_task = _is_bank_task(task_lower) or (code_path and "bank" in code_path.lower())

    if bank_task:
        if not code_path:
            code_path = "bank.py"
        if not test_path:
            test_path = "tests/test_bank.py"
        code_content = (
            "class BankAccount:\n"
            "    def __init__(self, balance=0):\n"
            "        self.balance = balance\n\n"
            "    def deposit(self, amount):\n"
            "        self.balance += amount\n\n"
            "    def withdraw(self, amount):\n"
            "        if amount > self.balance:\n"
            "            raise ValueError(\"Insufficient funds\")\n"
            "        self.balance -= amount\n\n"
            "    def get_balance(self):\n"
            "        return self.balance\n"
        )
        test_content = (
            "import pytest\n"
            "from bank import BankAccount\n\n\n"
            "def test_deposit_and_balance():\n"
            "    acct = BankAccount()\n"
            "    acct.deposit(100)\n"
            "    assert acct.get_balance() == 100\n\n\n"
            "def test_withdraw():\n"
            "    acct = BankAccount(100)\n"
            "    acct.withdraw(40)\n"
            "    assert acct.get_balance() == 60\n\n\n"
            "def test_withdraw_insufficient():\n"
            "    acct = BankAccount(10)\n"
            "    with pytest.raises(ValueError):\n"
            "        acct.withdraw(20)\n"
        )
    else:
        func_name = _extract_function_name(task)
        code_content = f"def {func_name}(a, b):\n    return a + b\n"
        module_name = os.path.splitext(os.path.basename(code_path))[0]
        test_content = (
            f"from {module_name} import {func_name}\n\n\n"
            f"def test_{func_name}():\n"
            f"    assert {func_name}(1, 2) == 3\n"
        )

    wants_create = any(
        k in task_lower
        for k in ["作成", "create", "write", "make", "新規", "追加"]
    )
    wants_check = any(
        k in task_lower
        for k in ["開き", "確認", "check", "inspect", "open"]
    )

    last_read_code = _last_result_for_tool(history, "read_file", code_path)
    last_read_test = _last_result_for_tool(history, "read_file", test_path)

    code_missing = bool(last_read_code and last_read_code.startswith("Error"))
    test_missing = bool(last_read_test and last_read_test.startswith("Error"))

    if wants_check and not _history_has_tool(history, "read_file", code_path):
        return {
            "thought": "実装ファイルを確認する",
            "tool": "read_file",
            "path": code_path
        }

    if wants_create or code_missing:
        if not (_history_success(history, "create_file", code_path) or _history_success(history, "edit_file", code_path)):
            last_create = _last_result_for_tool(history, "create_file", code_path).lower()
            if "already exists" in last_create or "exists" in last_create:
                return {
                    "thought": "関数ファイルを上書きで作成する",
                    "tool": "edit_file",
                    "path": code_path,
                    "content": code_content
                }
            return {
                "thought": "関数ファイルを作成する",
                "tool": "create_file",
                "path": code_path,
                "content": code_content
            }

    if wants_create or test_missing:
        if not (_history_success(history, "create_file", test_path) or _history_success(history, "edit_file", test_path)):
            last_create = _last_result_for_tool(history, "create_file", test_path).lower()
            if "already exists" in last_create or "exists" in last_create:
                return {
                    "thought": "テストファイルを上書きで作成する",
                    "tool": "edit_file",
                    "path": test_path,
                    "content": test_content
                }
            return {
                "thought": "テストファイルを作成する",
                "tool": "create_file",
                "path": test_path,
                "content": test_content
            }

    last_run_test_idx = _last_index(history, "run_test")
    last_run_test_result = _last_result_for_tool(history, "run_test")

    pip_idx = _last_run_command_index(history, "pip install pytest")
    pip_python_idx = _last_run_command_index(history, "python -m pip install pytest")
    last_pip_idx = max(pip_idx, pip_python_idx)

    pip_succeeded = False
    if last_pip_idx != -1:
        pip_result = str(history[last_pip_idx].get("result", ""))
        pip_succeeded = "[exit code 0]" in pip_result

    if last_run_test_idx == -1:
        return {
            "thought": "pytest を実行する",
            "tool": "run_test",
            "path": test_path
        }

    if "[exit code 0]" in last_run_test_result:
        return {
            "thought": "テストが成功したため終了する",
            "tool": "done"
        }

    if _needs_pytest_install(history):
        return {
            "thought": "pytest が不足しているためインストールする",
            "tool": "run",
            "command": "pip install pytest"
        }

    if pip_succeeded and last_pip_idx > last_run_test_idx:
        return {
            "thought": "pytest を再実行する",
            "tool": "run_test",
            "path": test_path
        }

    if _last_index(history, "read_file", test_path) < last_run_test_idx:
        return {
            "thought": "テスト失敗のため内容を確認する",
            "tool": "read_file",
            "path": test_path
        }

    if _last_index(history, "read_file", code_path) < last_run_test_idx:
        return {
            "thought": "実装を確認する",
            "tool": "read_file",
            "path": code_path
        }

    code_read = _last_read_content(history, code_path)
    test_read = _last_read_content(history, test_path)

    if "AssertionError" in last_run_test_result or "assert" in last_run_test_result:
        if "return a - b" in code_read and ("assert add" in test_read or "test_add" in test_read):
            if not _diff_edit_attempted_for(history, code_path, "a - b", "a + b"):
                return {
                    "thought": "加算の実装ミスを修正する",
                    "tool": "diff_edit",
                    "path": code_path,
                    "old": "a - b",
                    "new": "a + b"
                }
        if "def withdraw" in code_read and "pytest.raises" in test_read:
            if "raise ValueError" not in code_read and "return False" in code_read:
                if not _diff_edit_attempted_for(history, code_path, "return False", "raise ValueError(\"Insufficient funds\")"):
                    return {
                        "thought": "残高不足時の例外処理を追加する",
                        "tool": "diff_edit",
                        "path": code_path,
                        "old": "return False",
                        "new": "raise ValueError(\"Insufficient funds\")"
                    }

    last_fix_idx = _last_diff_edit_index_for(history, code_path, "a - b", "a + b")
    if last_fix_idx != -1 and last_fix_idx > last_run_test_idx:
        return {
            "thought": "修正後のテストを再実行する",
            "tool": "run_test",
            "path": test_path
        }

    return {
        "thought": "テストが失敗したため終了する",
        "tool": "done"
    }
