"""
improvement_loop.py — 自律改善ループ
テスト → 結果分析 → コード修正 → テスト を繰り返す。
"""

import json
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import re

AGENT_ROOT = Path("/Volumes/ESD-EHA/agent")
PYTHON = sys.executable
MAX_ROUNDS = 10
SUCCESS_THRESHOLD = 0.90  # 90%以上で終了
LOG_FILE = AGENT_ROOT / "improvement_loop.log"


# =====================================================
# ラウンド実行
# =====================================================

def run_test_round(round_num: int) -> dict:
    """tester.py を1ラウンド実行してresultsを返す"""
    print(f"\n{'='*60}")
    print(f"  ラウンド {round_num} — テスト実行中...")
    print(f"{'='*60}")

    start = time.time()
    result = subprocess.run(
        [PYTHON, "tester.py", "--rounds", "1"],
        cwd=AGENT_ROOT,
        capture_output=False,  # stdout をリアルタイム表示
        text=True,
        timeout=7200,          # 2時間上限
    )
    elapsed = time.time() - start

    # qa_report_round1.md を読む (tester.py は常に round1 で保存)
    report_path = AGENT_ROOT / "qa_report_round1.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""

    summary = _parse_report(report_text)

    print(f"\n[Round {round_num}] {summary['passed']}/{summary['total']}"
          f" ({summary['pass_rate']*100:.0f}%) — {elapsed:.0f}s")

    return {
        "round": round_num,
        "summary": summary,
        "report": report_text,
        "elapsed": elapsed,
    }


def _parse_report(report_text: str) -> dict:
    """レポートからサマリーを抽出"""
    passed = total = 0

    # "成功 | N (N%)" パターン
    m = re.search(r"成功.*?(\d+)\s*\((\d+)%\)", report_text)
    if m:
        passed = int(m.group(1))

    m2 = re.search(r"総テスト数.*?(\d+)", report_text)
    if m2:
        total = int(m2.group(1))

    # カテゴリ別スコア
    categories = {}
    for cat in ["Coding", "File Operations", "PDF", "Excel", "Web"]:
        key = cat.replace(" Operations", "")
        m3 = re.search(rf"{re.escape(cat)}\s*\((\d+)/(\d+)\)", report_text)
        if m3:
            categories[key] = {"passed": int(m3.group(1)), "total": int(m3.group(2))}

    # 失敗テストと理由
    failures = []
    for line in report_text.split("\n"):
        if "❌" in line or "LOOP DETECTED" in line:
            failures.append(line.strip())

    # LOOP DETECTED ログ
    loop_logs = [ln for ln in report_text.split("\n") if "LOOP DETECTED" in ln]

    # MAX_STEPS 消費カウント
    max_steps_reached = report_text.count("done宣言なし") + report_text.count("MAX_STEPS消費")

    return {
        "passed": passed,
        "total": total or 18,
        "pass_rate": passed / (total or 18),
        "categories": categories,
        "failures": failures[:30],
        "loop_logs": loop_logs,
        "max_steps_reached": max_steps_reached,
    }


# =====================================================
# 問題分析
# =====================================================

KNOWN_PATTERNS = [
    {
        "id": "workspace_pollution",
        "detect": lambda r: any("already exists" in f for f in r["failures"]),
        "description": "前テストのファイルが残りcreate_fileが失敗",
        "fix": "fix_workspace_pollution",
    },
    {
        "id": "ollama_timeout",
        "detect": lambda r: r.get("total", 18) > r.get("passed", 0) and
                            any("⏱" in f or "0ステップ" in f for f in r["failures"]),
        "description": "Ollamaコールドスタートによるタイムアウト",
        "fix": "fix_ollama_timeout",
    },
    {
        "id": "false_loop_detection",
        "detect": lambda r: len(r.get("loop_logs", [])) > 4,
        "description": "detect_loop()の誤検知が多い",
        "fix": "fix_loop_threshold",
    },
    {
        "id": "done_not_declared",
        "detect": lambda r: r.get("max_steps_reached", 0) >= 2,
        "description": "MAX_STEPSを使い切ってdone宣言しない",
        "fix": "fix_done_prompt",
    },
    {
        "id": "library_missing",
        "detect": lambda r: any("ImportError" in f or "ModuleNotFound" in f for f in r["failures"]),
        "description": "必要なライブラリがインストールされていない",
        "fix": "fix_install_libraries",
    },
    {
        "id": "no_run_after_create",
        "detect": lambda r: any("作成するが" in f or "実行しない" in f for f in r["failures"]),
        "description": "ファイルを作成するが実行しない",
        "fix": "fix_execution_prompt",
    },
    {
        "id": "context_overflow",
        "detect": lambda r: any("context" in f.lower() and "budget" in f.lower()
                                for f in r["failures"]),
        "description": "コンテキスト予算超過",
        "fix": "fix_context_budget",
    },
]


def analyze_failures(round_result: dict) -> list:
    """失敗原因を特定してfixリストを返す"""
    summary = round_result["summary"]
    detected = []

    for pattern in KNOWN_PATTERNS:
        try:
            if pattern["detect"](summary):
                detected.append(pattern)
                print(f"  🔍 検出: [{pattern['id']}] {pattern['description']}")
        except Exception:
            pass

    if not detected:
        detected.append({
            "id": "unknown",
            "description": "未知の問題",
            "fix": "fix_with_llm_analysis",
        })

    return detected


# =====================================================
# 自動修正
# =====================================================

def apply_fixes(problems: list, round_result: dict):
    """検出した問題を修正する"""
    for problem in problems:
        fix_fn_name = problem.get("fix", "")
        fix_fn = globals().get(fix_fn_name)
        if fix_fn:
            print(f"\n  🔧 修正中: {problem['description']}")
            try:
                fix_fn(round_result)
                print(f"  ✅ 修正完了: {fix_fn_name}")
            except Exception as e:
                print(f"  ⚠️ 修正失敗: {e}")
        else:
            print(f"  ⚠️ 修正関数なし: {fix_fn_name}")


def fix_workspace_pollution(round_result):
    """create_file がファイル存在エラーを返したとき edit_file にフォールバックする hint を SYSTEM_PROMPT に追加"""
    llm_path = AGENT_ROOT / "llm.py"
    content = llm_path.read_text(encoding="utf-8")
    if "FILE_EXISTS_FALLBACK" in content:
        print("    (already patched)")
        return
    injection = (
        "\n[FILE_EXISTS_FALLBACK]\n"
        "If create_file returns 'Error: File already exists', "
        "use edit_file with the same path and content instead.\n"
    )
    last_triple = content.rfind('"""')
    content = content[:last_triple] + injection + content[last_triple:]
    llm_path.write_text(content, encoding="utf-8")


def fix_ollama_timeout(round_result):
    """タイムアウトを延長"""
    runner_path = AGENT_ROOT / "command_runner.py"
    if not runner_path.exists():
        return
    content = runner_path.read_text(encoding="utf-8")
    changed = False
    for old, new in [
        ('"pip":    120,', '"pip":    180,'),
        ('"pip": 120',    '"pip": 180'),
        ('"python": 120', '"python": 180'),
    ]:
        if old in content:
            content = content.replace(old, new)
            changed = True
    if changed:
        runner_path.write_text(content, encoding="utf-8")
        print("    タイムアウト延長済み")
    else:
        print("    (タイムアウト定数が見つからず — スキップ)")


def fix_loop_threshold(round_result):
    """ループ検出の閾値を緩和"""
    main_path = AGENT_ROOT / "main.py"
    content = main_path.read_text(encoding="utf-8")
    changed = False
    for old, new in [
        ("REPEAT_THRESHOLD = 3", "REPEAT_THRESHOLD = 4"),
        ("REPEAT_THRESHOLD = 4", "REPEAT_THRESHOLD = 5"),
        ("WINDOW = 6", "WINDOW = 8"),
        ("WINDOW = 8", "WINDOW = 10"),
    ]:
        if old in content and new not in content:
            content = content.replace(old, new)
            changed = True
            break
    if changed:
        main_path.write_text(content, encoding="utf-8")
        print("    ループ閾値を緩和した")
    else:
        print("    (変更なし)")


def fix_done_prompt(round_result):
    """done宣言条件をSYSTEM_PROMPTで強化"""
    llm_path = AGENT_ROOT / "llm.py"
    content = llm_path.read_text(encoding="utf-8")
    if "DONE_STRONG" in content:
        print("    (already patched)")
        return
    injection = (
        "\n[DONE_STRONG]\n"
        "After run returns '[exit code 0]', your IMMEDIATE next action MUST be done.\n"
        "Do NOT read_file, run again, or verify again after exit code 0.\n"
        "{\"tool\": \"done\", \"thought\": \"タスク完了\"}\n"
    )
    last_triple = content.rfind('"""')
    content = content[:last_triple] + injection + content[last_triple:]
    llm_path.write_text(content, encoding="utf-8")


def fix_execution_prompt(round_result):
    """SYSTEM_PROMPT の実行ルールを強化"""
    llm_path = AGENT_ROOT / "llm.py"
    content = llm_path.read_text(encoding="utf-8")
    if "ALWAYS_RUN_AFTER_CREATE_V2" in content:
        print("    (already patched)")
        return
    injection = (
        "\n[ALWAYS_RUN_AFTER_CREATE_V2]\n"
        "Step sequence for coding tasks:\n"
        "1. create_file (write the script)\n"
        "2. run (python <script>) — MANDATORY\n"
        "3. done (only after exit code 0)\n"
        "Skipping step 2 is WRONG.\n"
    )
    last_triple = content.rfind('"""')
    content = content[:last_triple] + injection + content[last_triple:]
    llm_path.write_text(content, encoding="utf-8")


def fix_install_libraries(round_result):
    """必要ライブラリを自動インストール"""
    libs = ["pypdf", "pdfplumber", "reportlab", "pandas",
            "openpyxl", "beautifulsoup4", "requests"]
    subprocess.run(
        [PYTHON, "-m", "pip", "install"] + libs,
        cwd=AGENT_ROOT, capture_output=True
    )
    print("    ライブラリインストール完了")


def fix_context_budget(round_result):
    """コンテキスト予算を最適化"""
    main_path = AGENT_ROOT / "main.py"
    content = main_path.read_text(encoding="utf-8")
    changed = False
    for old, new in [
        ("CONTEXT_CHAR_BUDGET = 8000", "CONTEXT_CHAR_BUDGET = 5000"),
        ("CONTEXT_CHAR_BUDGET = 6000", "CONTEXT_CHAR_BUDGET = 5000"),
    ]:
        if old in content:
            content = content.replace(old, new)
            changed = True
    if changed:
        main_path.write_text(content, encoding="utf-8")
        print("    CONTEXT_CHAR_BUDGET 最適化済み")


def fix_with_llm_analysis(round_result):
    """未知の問題をLLMで分析して修正"""
    try:
        sys.path.insert(0, str(AGENT_ROOT))
        from llm import ask_planner

        report = round_result.get("report", "")
        # 失敗セクションだけ抽出
        fail_start = report.find("## Failed Tests")
        snippet = report[fail_start:fail_start + 3000] if fail_start >= 0 else report[-3000:]

        prompt = (
            "以下はAIコーディングエージェントのテスト失敗ログです。\n"
            "根本原因と修正方法を日本語で簡潔に説明してください。\n\n"
            f"失敗ログ:\n{snippet}\n\n"
            "出力形式:\n"
            "根本原因: ...\n"
            "修正内容: ...\n"
        )
        analysis = ask_planner(prompt)
        print(f"\n  🤖 LLM分析:\n{analysis[:400]}")

        (AGENT_ROOT / "unknown_failures.md").write_text(
            f"# 未知の失敗分析 — {datetime.now()}\n\n{analysis}",
            encoding="utf-8",
        )
    except Exception as e:
        print(f"    LLM分析失敗: {e}")


# =====================================================
# ファイナルレポート生成
# =====================================================

def save_final_report(all_rounds: list) -> None:
    lines = [
        "# Improvement Loop — Final Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Total rounds: {len(all_rounds)}",
        "",
        "## Progress",
        "| Round | Passed | Total | Rate | Elapsed | Fixes Applied |",
        "|-------|--------|-------|------|---------|---------------|",
    ]
    for r in all_rounds:
        s = r["summary"]
        fixes = ", ".join(r.get("fixes_applied", ["-"]))
        lines.append(
            f"| {r['round']} | {s['passed']} | {s['total']} "
            f"| {s['pass_rate']*100:.0f}% | {r['elapsed']:.0f}s | {fixes} |"
        )

    # カテゴリ別推移
    lines += ["", "## Category Progress"]
    cats = ["Coding", "File", "PDF", "Excel", "Web"]
    header = "| Category |" + "".join(f" R{r['round']} |" for r in all_rounds)
    lines.append(header)
    lines.append("|----------|" + "--------|" * len(all_rounds))
    for cat in cats:
        row = f"| {cat} |"
        for r in all_rounds:
            c = r["summary"]["categories"].get(cat, {})
            p, t = c.get("passed", "?"), c.get("total", "?")
            row += f" {p}/{t} |"
        lines.append(row)

    lines += [
        "",
        "## Pass Rate Trend",
    ]
    for r in all_rounds:
        s = r["summary"]
        bar = "█" * int(s["pass_rate"] * 20) + "░" * (20 - int(s["pass_rate"] * 20))
        lines.append(f"Round {r['round']}: [{bar}] {s['pass_rate']*100:.0f}% ({s['passed']}/{s['total']})")

    path = AGENT_ROOT / "qa_report_final.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 最終レポート: {path}")


# =====================================================
# メインループ
# =====================================================

def main():
    log = open(LOG_FILE, "a", encoding="utf-8")
    log.write(f"\n{'='*60}\n")
    log.write(f"Loop started: {datetime.now()}\n")
    log.flush()

    all_rounds = []

    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n{'#'*60}")
        print(f"  ROUND {round_num}/{MAX_ROUNDS}")
        print(f"{'#'*60}")

        # 1. テスト実行
        round_result = run_test_round(round_num)
        all_rounds.append(round_result)

        rate = round_result["summary"]["pass_rate"]
        log.write(f"Round {round_num}: {rate*100:.0f}% ({round_result['summary']['passed']}/{round_result['summary']['total']})\n")
        log.flush()

        # 2. 終了判定
        if rate >= SUCCESS_THRESHOLD:
            print(f"\n🎉 目標達成: {rate*100:.0f}% >= {SUCCESS_THRESHOLD*100:.0f}%")
            round_result["fixes_applied"] = []
            break

        if round_num == MAX_ROUNDS:
            print(f"\n⏱️  最大ラウンド数({MAX_ROUNDS})に到達")
            round_result["fixes_applied"] = []
            break

        # 3. 失敗分析
        print(f"\n📊 失敗分析中...")
        problems = analyze_failures(round_result)

        if not problems:
            print("  分析できる問題なし — スキップ")
            round_result["fixes_applied"] = []
            continue

        # 4. 修正適用
        print(f"\n🔧 {len(problems)}件の修正を適用中...")
        apply_fixes(problems, round_result)
        fixes_applied = [p["id"] for p in problems]
        round_result["fixes_applied"] = fixes_applied

        log.write(f"  Fixes: {fixes_applied}\n")
        log.flush()

        print(f"\n⏳ 次のラウンドまで5秒待機...")
        time.sleep(5)

    # 最終レポート
    save_final_report(all_rounds)
    log.write(f"Loop ended: {datetime.now()}\n")
    log.close()

    # サマリー出力
    final = all_rounds[-1]["summary"]
    print(f"\n{'='*60}")
    print(f"  最終結果: {final['passed']}/{final['total']}"
          f" ({final['pass_rate']*100:.0f}%)")
    print(f"  総ラウンド数: {len(all_rounds)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
