"""
Failure Generator。
意図的なエラーシナリオを生成し、エージェントに修復させて
repair_patterns.json を充実させる。

設計方針:
- エージェントが実際に遭遇するエラーパターンを網羅する
- 各シナリオは独立して実行可能
- 修復成功後に signature が自動学習される
"""
import json
import shutil
import time
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent
WORKSPACE  = AGENT_ROOT / "workspace"

# =====================================================
# エラーシナリオ定義
# =====================================================

FAILURE_SCENARIOS = [
    # --- SyntaxError 系 ---
    {
        "id": "FG01",
        "signature_target": "syntax_error::unexpected_indent",
        "task": (
            "workspace/fg01.py を作成して実行せよ。\n"
            "ファイルの内容:\n"
            "def greet(name):\n"
            "print(f'Hello {name}')  # インデントなし（バグ）\n"
            "greet('World')\n"
            "エラーを自分で修正してexit code 0にすること"
        ),
        "expect_contains": "Hello",
        "max_steps": 15,
    },
    {
        "id": "FG02",
        "signature_target": "syntax_error::missing_colon",
        "task": (
            "workspace/fg02.py を作成して実行せよ。\n"
            "ファイルの内容:\n"
            "def add(a, b)  # コロンなし（バグ）\n"
            "    return a + b\n"
            "print(add(3, 4))\n"
            "エラーを自分で修正してexit code 0にすること"
        ),
        "expect_contains": "7",
        "max_steps": 15,
    },
    # --- ImportError 系 ---
    {
        "id": "FG03",
        "signature_target": "import_error::requests",
        "task": (
            "workspace/fg03.py を作成して実行せよ。\n"
            "ファイルの内容:\n"
            "import requests\n"
            "r = requests.get('https://httpbin.org/json')\n"
            "print(r.status_code)\n"
            "requestsがない場合はインストールしてから実行すること"
        ),
        "expect_contains": "200",
        "max_steps": 15,
    },
    {
        "id": "FG04",
        "signature_target": "import_error::openpyxl",
        "task": (
            "workspace/fg04.py を作成して実行せよ。\n"
            "ファイルの内容:\n"
            "import openpyxl\n"
            "wb = openpyxl.Workbook()\n"
            "ws = wb.active\n"
            "ws['A1'] = 'Test'\n"
            "wb.save('workspace/test.xlsx')\n"
            "print('saved')\n"
            "openpyxlがない場合はインストールしてから実行すること"
        ),
        "expect_contains": "saved",
        "max_steps": 15,
    },
    # --- RuntimeError 系 ---
    {
        "id": "FG05",
        "signature_target": "runtime_error::keyerror",
        "task": (
            "workspace/fg05.py を作成して実行せよ。\n"
            "ファイルの内容:\n"
            "data = {'name': 'Alice'}\n"
            "print(data['age'])  # KeyError（バグ）\n"
            "エラーを修正して name と age(デフォルト0) を表示させること"
        ),
        "expect_contains": "Alice",
        "max_steps": 15,
    },
    {
        "id": "FG06",
        "signature_target": "runtime_error::typeerror",
        "task": (
            "workspace/fg06.py を作成して実行せよ。\n"
            "ファイルの内容:\n"
            "def double(x):\n"
            "    return x * 2\n"
            "result = double('5') + 10  # TypeError（バグ）\n"
            "print(result)\n"
            "エラーを修正して結果20を出力させること"
        ),
        "expect_contains": "20",
        "max_steps": 15,
    },
    # --- LoopDetected 系 ---
    {
        "id": "FG07",
        "signature_target": "loop_detected::process",
        "task": (
            "workspace/process.py を作成して実行せよ。\n"
            "以下の仕様で実装すること:\n"
            "- リスト[1,2,3,4,5]の各要素を2倍にして出力\n"
            "- forループを使うこと\n"
            "- 実行して全結果が表示されること"
        ),
        "expect_contains": "exit code 0",
        "max_steps": 15,
    },
    # --- WrongOutput 系 ---
    {
        "id": "FG08",
        "signature_target": "wrong_output::calculation",
        "task": (
            "workspace/calc.py を作成して実行せよ。\n"
            "1から100までの合計を計算して出力すること。\n"
            "期待される出力: 5050\n"
            "この値が出力されない場合は修正すること"
        ),
        "expect_contains": "5050",
        "max_steps": 15,
    },
]


# =====================================================
# 実行エンジン
# =====================================================

def run_failure_scenarios(
    scenario_ids: list = None,
    max_improve: int = 2,
) -> dict:
    """
    エラーシナリオを順番に実行する。
    run_with_self_improve(tc, task_str, loop_round, max_improve) を正しく呼ぶ。
    """
    from tester import run_with_self_improve

    scenarios = FAILURE_SCENARIOS
    if scenario_ids:
        scenarios = [s for s in scenarios if s["id"] in scenario_ids]

    results = []
    print(f"\n{'='*60}")
    print(f"  Failure Generator: {len(scenarios)}シナリオ実行")
    print(f"{'='*60}")

    for scenario in scenarios:
        # ワークスペースをクリア
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        WORKSPACE.mkdir(parents=True, exist_ok=True)

        print(f"\n[{scenario['id']}] {scenario['signature_target']}")

        test_def = {
            "id":              scenario["id"],
            "label":           scenario["signature_target"],
            "task":            scenario["task"],
            "expect_contains": scenario["expect_contains"],
            "max_steps":       scenario["max_steps"],
            "category":        "failure_gen",
            "use_agent":       True,
        }

        t0 = time.time()
        # --- 正しいシグネチャで呼び出す ---
        run_result, eval_result, retry, last_analysis = run_with_self_improve(
            test_def,
            test_def["task"],
            loop_round=1,
            max_improve=max_improve,
        )
        elapsed = time.time() - t0

        success  = eval_result.success if eval_result else False
        improved = run_result.get("self_improved", False)
        steps    = run_result.get("steps", "?")

        status = "✅" if success else "❌"
        imp_label = "🔧 自己改善" if improved else ""
        print(f"  {status} {scenario['id']} {imp_label} | steps={steps} | {elapsed:.0f}s")

        results.append({
            "scenario_id":      scenario["id"],
            "signature_target": scenario["signature_target"],
            "success":          success,
            "self_improved":    improved,
            "steps":            steps,
            "elapsed":          round(elapsed, 1),
        })

    _print_summary(results)
    _save_report(results)

    return {
        "results":  results,
        "passed":   sum(1 for r in results if r["success"]),
        "total":    len(results),
        "improved": sum(1 for r in results if r["self_improved"]),
    }


def _print_summary(results: list):
    print(f"\n{'='*60}")
    print("  Failure Generator サマリー")
    print(f"{'='*60}")
    passed   = sum(1 for r in results if r["success"])
    improved = sum(1 for r in results if r["self_improved"])
    print(f"成功率: {passed}/{len(results)}")
    print(f"自己改善発動: {improved}件")
    print()
    _show_pattern_db()


def _show_pattern_db():
    """現在のパターンDB状態を表示"""
    db_path = AGENT_ROOT / "memory" / "repair_patterns.json"
    if not db_path.exists():
        print("パターンDB: 未作成")
        return
    data = json.loads(db_path.read_text())
    sigs = data.get("signatures", {})
    print(f"=== repair_patterns.json ===")
    print(f"signatures: {len(sigs)}種")
    for sig, pats in sorted(sigs.items()):
        for p in pats:
            print(f"  {sig} → {p['strategy']} (×{p.get('count', 1)})")


def _save_report(results: list):
    """実行レポートを保存"""
    report_path = AGENT_ROOT / "failure_gen_report.md"
    lines = [
        "# Failure Generator Report",
        f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| ID | Signature Target | 結果 | 自己改善 | 時間 |",
        "|----|-----------------|------|---------|------|",
    ]
    for r in results:
        status   = "✅" if r["success"] else "❌"
        improved = "🔧" if r["self_improved"] else "-"
        elapsed  = f"{r['elapsed']:.0f}s"
        lines.append(
            f"| {r['scenario_id']} "
            f"| {r['signature_target']} "
            f"| {status} "
            f"| {improved} "
            f"| {elapsed} |"
        )
    lines += ["", "## Pattern DB 更新後", ""]
    db_path = AGENT_ROOT / "memory" / "repair_patterns.json"
    if db_path.exists():
        data = json.loads(db_path.read_text())
        sigs = data.get("signatures", {})
        lines.append(f"signatures: {len(sigs)}種")
        for sig, pats in sorted(sigs.items()):
            for p in pats:
                lines.append(
                    f"- `{sig}` → `{p['strategy']}` (×{p.get('count', 1)})"
                )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 レポート保存: {report_path}")


if __name__ == "__main__":
    import sys
    ids = sys.argv[1:] if len(sys.argv) > 1 else None
    run_failure_scenarios(scenario_ids=ids)
