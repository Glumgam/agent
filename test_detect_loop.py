"""
test_detect_loop.py — detect_loop() の単体テスト (5ケース)

使い方:
    python test_detect_loop.py
"""

import sys
from pathlib import Path

# detect_loop / _action_signature を main.py からインラインコピー
# (main.py は多くの依存を持つため直接 import しない)

def _action_signature(entry: dict) -> str:
    a = entry.get("action", {})
    tool = a.get("tool", "")
    if tool == "run":
        return f"run::{a.get('command', '')}"
    return f"{tool}::{a.get('path', '')}"


def detect_loop(history: list) -> bool:
    WINDOW = 6
    REPEAT_THRESHOLD = 3

    real_steps = [h for h in history if not h.get("action", {}).get("_auto")]

    if len(real_steps) < REPEAT_THRESHOLD:
        return False

    last_action = real_steps[-1].get("action", {})
    if last_action.get("tool") == "done":
        return False

    recent = real_steps[-WINDOW:]
    sigs = [_action_signature(e) for e in recent]

    tail_sigs = sigs[-REPEAT_THRESHOLD:]
    if len(set(tail_sigs)) != 1:
        return False

    recent_obs = [str(e.get("result", "")) for e in recent[-REPEAT_THRESHOLD:]]

    has_improvement = any("exit code 0" in obs for obs in recent_obs)
    if has_improvement:
        return False

    if len(set(recent_obs)) == 1:
        print(f"[LOOP DETECTED] sigs={tail_sigs} obs_unique=1")
        return True

    all_failing = all(
        "exit code 1" in obs or "Error" in obs or "error" in obs
        for obs in recent_obs
    )
    if all_failing:
        print(f"[LOOP DETECTED] sigs={tail_sigs} all_failing=True")
        return True

    return False


def _make_entry(tool, path="", command="", result="", auto=False):
    action = {"tool": tool}
    if path:
        action["path"] = path
    if command:
        action["command"] = command
    if auto:
        action["_auto"] = True
    return {"action": action, "result": result}


def _run(name, history, expected):
    got = detect_loop(history)
    status = "PASS" if got == expected else "FAIL"
    mark = "✅" if got == expected else "❌"
    print(f"{mark} [{status}] {name}: expected={expected} got={got}")
    return got == expected


def test_case1_self_repair_cycle():
    """
    Case 1: 自己修復サイクル → ループ検出しない
    edit → run(失敗) → edit → run(成功) → run(verify)
    run が edit 直後なので is_repeated_action 免除、かつ exit code 0 あり
    """
    history = [
        _make_entry("edit_file", path="fix.py"),
        _make_entry("run", command="python fix.py", result="exit code 1 Error"),
        _make_entry("edit_file", path="fix.py"),
        _make_entry("run", command="python fix.py", result="[exit code 0] OK"),
        _make_entry("run", command="python fix.py", result="[exit code 0] OK"),
    ]
    return _run("Case 1: self-repair cycle → NO loop", history, False)


def test_case2_true_loop_same_error():
    """
    Case 2: 真のループ（同じコマンド、同じエラー）→ ループ検出
    同じコマンドを3回、毎回同じエラーが返る
    """
    err = "exit code 1 Error: FileNotFoundError: foo.txt"
    history = [
        _make_entry("run", command="python main.py", result=err),
        _make_entry("run", command="python main.py", result=err),
        _make_entry("run", command="python main.py", result=err),
    ]
    return _run("Case 2: same command same error → LOOP", history, True)


def test_case3_multi_file_creation():
    """
    Case 3: 複数ファイル作成（パスが異なる）→ ループ検出しない
    create_file を3回でも path が違えば signature が違う
    """
    history = [
        _make_entry("create_file", path="a.py", result="OK"),
        _make_entry("create_file", path="b.py", result="OK"),
        _make_entry("create_file", path="c.py", result="OK"),
    ]
    return _run("Case 3: multi-file creation (diff paths) → NO loop", history, False)


def test_case4_different_pip_installs():
    """
    Case 4: 複数の異なる pip install → ループ検出しない
    command が異なるので signature が異なる
    """
    history = [
        _make_entry("run", command="pip install requests", result="exit code 1 already installed"),
        _make_entry("run", command="pip install pandas", result="exit code 1 already installed"),
        _make_entry("run", command="pip install openpyxl", result="exit code 1 already installed"),
    ]
    return _run("Case 4: different pip installs → NO loop", history, False)


def test_case5_stuck_same_error_varying_msg():
    """
    Case 5: 同じコマンド、エラー内容が微妙に変わっても全部失敗 → ループ検出
    all_failing=True の経路
    """
    history = [
        _make_entry("run", command="python script.py", result="exit code 1 Error: line 5"),
        _make_entry("run", command="python script.py", result="exit code 1 Error: line 7"),
        _make_entry("run", command="python script.py", result="exit code 1 Error: line 9"),
    ]
    return _run("Case 5: same cmd all failing (varying msg) → LOOP", history, True)


def main():
    print("=" * 55)
    print("detect_loop() テスト")
    print("=" * 55)

    results = [
        test_case1_self_repair_cycle(),
        test_case2_true_loop_same_error(),
        test_case3_multi_file_creation(),
        test_case4_different_pip_installs(),
        test_case5_stuck_same_error_varying_msg(),
    ]

    passed = sum(results)
    total = len(results)
    print("-" * 55)
    print(f"結果: {passed}/{total} 通過")

    if passed == total:
        print("✅ 全テスト通過")
        sys.exit(0)
    else:
        print("❌ 失敗あり")
        sys.exit(1)


if __name__ == "__main__":
    main()
