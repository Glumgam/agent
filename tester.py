#!/usr/bin/env python3
"""
tester.py — Auto QA Loop オーケストレーター (ラウンドループ対応版)

ラウンドループ:
  Round 1: 全カテゴリをテスト → 失敗タスクを自動修正
  Round 2: 再テスト → 失敗タスクを自動修正
  Round 3: 再テスト → 最終レポート生成
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AGENT_DIR = Path(__file__).parent
WORKSPACE_DIR = AGENT_DIR / "workspace"
VENV_PYTHON = str(AGENT_DIR / "venv" / "bin" / "python")
MAIN_PY = str(AGENT_DIR / "main.py")
TESTCASES_DIR = AGENT_DIR / "testcases"

MAX_RETRIES = 1   # 1タスクあたりのリトライ上限（ラウンド内）
LOOP_MAX = 3      # 全体ラウンドの最大繰り返し回数

# --- SELF IMPROVE START ---
from self_evaluator import evaluate_run, FailureType
from self_improver import improve
# --- SELF IMPROVE END ---

REQUIRED_PACKAGES = {
    "pypdf":      "pypdf",
    "pdfplumber": "pdfplumber",
    "reportlab":  "reportlab",
    "pandas":     "pandas",
    "openpyxl":   "openpyxl",
    "bs4":        "beautifulsoup4",
    "requests":   "requests",
}

CATEGORY_FILES = {
    "coding": "coding_tests.json",
    "file":   "file_tests.json",
    "pdf":    "pdf_tests.json",
    "excel":  "excel_tests.json",
    "web":    "web_tests.json",
}

ALL_CATEGORIES = list(CATEGORY_FILES.keys())


# -------------------------
# DEPENDENCY CHECK
# -------------------------

def check_and_install_dependencies() -> bool:
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        print("✅ 全依存パッケージ確認済み")
        return True

    print(f"Missing packages: {', '.join(missing)}")

    if not sys.stdin.isatty():
        print("非インタラクティブモード: venv にインストールします...")
        result = subprocess.run(
            [VENV_PYTHON, "-m", "pip", "install"] + missing,
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            print("✅ インストール完了")
        else:
            print("⚠️ インストール失敗 — 一部テストが失敗する可能性あり")
        return result.returncode == 0

    ans = input("Install these packages in venv? (y/n): ").strip().lower()
    if ans != "y":
        print("スキップ。一部テストが失敗する可能性あり。")
        return False

    result = subprocess.run(
        [VENV_PYTHON, "-m", "pip", "install"] + missing,
        check=False,
    )
    return result.returncode == 0


# -------------------------
# TESTCASE LOADER
# -------------------------

def load_testcases(categories: list | None = None) -> list[dict]:
    all_cases: list[dict] = []
    for cat, fname in CATEGORY_FILES.items():
        if categories and cat not in categories:
            continue
        path = TESTCASES_DIR / fname
        if path.exists():
            cases = json.loads(path.read_text(encoding="utf-8"))
            all_cases.extend(cases)
    return all_cases


# -------------------------
# WORKSPACE
# -------------------------

def clean_workspace():
    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# SINGLE TASK RUNNER
# -------------------------

def run_single_task(task_def: dict, task_str: str, loop_round: int = 1) -> dict:
    max_steps = task_def.get("max_steps", 10)
    timeout_sec = max_steps * 45 + 120

    clean_workspace()

    print(f"    [Round {loop_round}] [{task_def['id']}] {task_def['label']} 実行中...")

    start = time.time()
    timed_out = False
    stdout = ""

    try:
        proc = subprocess.run(
            [VENV_PYTHON, MAIN_PY],
            input=task_str,
            capture_output=True,
            text=True,
            cwd=str(AGENT_DIR),
            timeout=timeout_sec,
            env={**os.environ, "PYTHONPATH": str(AGENT_DIR)},
        )
        stdout = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as e:
        raw_out = e.stdout or b""
        raw_err = e.stderr or b""
        stdout = (
            (raw_out.decode("utf-8", errors="replace") if isinstance(raw_out, bytes) else raw_out)
            + (raw_err.decode("utf-8", errors="replace") if isinstance(raw_err, bytes) else raw_err)
        )
        timed_out = True

    elapsed = round(time.time() - start, 1)
    steps_used = len(re.findall(r"===== STEP \d+ =====", stdout))

    return {
        "output": stdout,
        "elapsed": elapsed,
        "timed_out": timed_out,
        "steps_used": steps_used,
    }


# -------------------------
# SELF-IMPROVE RUNNER
# -------------------------

# --- SELF IMPROVE START ---
def run_with_self_improve(
    tc: dict,
    task_str: str,
    loop_round: int = 1,
    max_improve: int = 1,
) -> tuple:
    """
    タスク実行 → 評価 → 自己改善 → 再実行 のサイクル。
    Stage-1: 既存リトライ（タスク文字列修正、MAX_RETRIES回）
    Stage-2: 自己改善（エージェントコード修正、max_improve回）
    Returns: (run_result, eval_result, retry_count, last_analysis)
    """
    from evaluator import evaluate
    from self_fix import analyze_failure, build_retry_task

    run_result: dict | None = None
    eval_result = None
    retry = 0
    last_analysis: dict = {}
    current_task_str = task_str

    # Stage 1: 既存リトライ（タスク文字列修正）
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            last_analysis = analyze_failure(tc, run_result["output"])
            current_task_str = build_retry_task(tc, last_analysis)
            print(f"    リトライ {attempt}/{MAX_RETRIES}: {last_analysis.get('cause_label', '?')}")

        run_result = run_single_task(tc, current_task_str, loop_round=loop_round)
        eval_result = evaluate(tc, run_result["output"])
        retry = attempt

        if eval_result.success:
            run_result["self_improved"] = False
            run_result["improve_attempts"] = 0
            return run_result, eval_result, retry, last_analysis

    # Stage 2: 自己改善（エージェントコード修正）
    if max_improve > 0:
        se_result = evaluate_run(
            task_def=tc,
            agent_log=run_result["output"],
            agent_output=run_result["output"],
        )
        print(f"    📊 失敗分類: {se_result.failure_type.value}")
        print(f"    💬 理由: {se_result.reason}")

        improve_result = improve(se_result)
        if improve_result["applied"]:
            print(f"    ✅ 修正適用: {improve_result['description']}")
            print(f"    🔄 自己改善後リトライ")
            run_result2 = run_single_task(tc, task_str, loop_round=loop_round)
            eval_result2 = evaluate(tc, run_result2["output"])
            run_result2["self_improved"] = True
            run_result2["improve_attempts"] = 1
            if eval_result2.success:
                if not last_analysis:
                    last_analysis = analyze_failure(tc, run_result["output"])
                return run_result2, eval_result2, retry + 1, last_analysis
            # 改善後も失敗した場合は改善後の結果を使う
            run_result = run_result2
            eval_result = eval_result2
        else:
            print(f"    ⚠️ 自動修正不可: {improve_result['description']}")

    # 最終的に失敗
    if not last_analysis:
        from self_fix import analyze_failure as _af
        last_analysis = _af(tc, run_result["output"])
    run_result["self_improved"] = False
    run_result["improve_attempts"] = 0
    return run_result, eval_result, retry, last_analysis
# --- SELF IMPROVE END ---


# -------------------------
# SUITE RUNNER (ONE ROUND)
# -------------------------

def run_test_suite(
    categories: list | None = None,
    loop_round: int = 1,
    prev_results: dict | None = None,   # 前ラウンドの結果（失敗分のみ再実行用）
) -> dict:
    """1ラウンド分のテストを実行して結果を返す。"""
    from evaluator import evaluate
    from self_fix import analyze_failure, build_retry_task

    clean_workspace()  # Fix-A: ラウンド開始時にワークスペースをクリア

    test_cases = load_testcases(categories)
    if not test_cases:
        print("テストケースが見つかりません。")
        return {"results": [], "summary": {}}

    # 前ラウンド成功済みのタスクはスキップして前回結果を引き継ぐ
    prev_ok: dict[str, dict] = {}
    if prev_results:
        for r in prev_results.get("results", []):
            if r["success"]:
                prev_ok[r["id"]] = r

    results: list[dict] = []
    total_start = time.time()
    completed_ids: set[str] = set(prev_ok.keys())

    for tc in test_cases:
        # 前ラウンドで成功済み → スキップ
        if tc["id"] in prev_ok:
            entry = dict(prev_ok[tc["id"]])
            entry["skipped"] = True
            results.append(entry)
            completed_ids.add(tc["id"])
            print(f"  [{tc['id']}] ✅ 前ラウンド成功 — スキップ")
            continue

        # 依存タスクが未完了 → スキップ
        dep = tc.get("depends_on")
        if dep and dep not in completed_ids:
            print(f"  [{tc['id']}] — 依存 {dep} 未完了のためスキップ")
            results.append({
                "id": tc["id"],
                "label": tc["label"],
                "category": tc.get("category", ""),
                "task_def": tc,
                "success": False,
                "reason": f"依存タスク {dep} が未完了",
                "score": 0.0,
                "steps_used": 0,
                "retry_count": 0,
                "elapsed": 0.0,
                "timed_out": False,
                "last_output": "",
                "analysis": {},
            })
            continue

        task_str = tc["task"]

        # --- SELF IMPROVE START ---
        # run_with_self_improve: 既存リトライ(Stage-1) + 自己改善リトライ(Stage-2)
        run_result, eval_result, retry, last_analysis = run_with_self_improve(
            tc, task_str, loop_round=loop_round
        )
        # --- SELF IMPROVE END ---

        if eval_result.success:
            completed_ids.add(tc["id"])

        ok_str = "✅" if eval_result.success else "❌"
        tout_str = " [タイムアウト]" if run_result["timed_out"] else ""
        print(f"    {ok_str} [{tc['id']}] steps={run_result['steps_used']} "
              f"elapsed={run_result['elapsed']}s{tout_str}")
        print(f"       reason: {eval_result.reason}")

        results.append({
            "id": tc["id"],
            "label": tc["label"],
            "category": tc.get("category", ""),
            "task_def": tc,
            "success": eval_result.success,
            "reason": eval_result.reason,
            "score": eval_result.score,
            "steps_used": run_result["steps_used"],
            "retry_count": retry,
            "elapsed": run_result["elapsed"],
            "timed_out": run_result["timed_out"],
            "last_output": run_result["output"][-3000:] if not eval_result.success else "",
            "analysis": last_analysis,
            # --- SELF IMPROVE START ---
            "self_improved": run_result.get("self_improved", False),
            "improve_attempts": run_result.get("improve_attempts", 0),
            # --- SELF IMPROVE END ---
        })

    total_elapsed = round(time.time() - total_start, 1)
    n = len(results)
    n_passed = sum(1 for r in results if r["success"])
    n_retry_success = sum(1 for r in results if r["success"] and r.get("retry_count", 0) > 0)

    return {
        "results": results,
        "summary": {
            "total": n,
            "passed": n_passed,
            "failed": n - n_passed,
            "retry_success": n_retry_success,
            "pass_rate": round(n_passed / n, 2) if n else 0.0,
            "total_elapsed": total_elapsed,
        },
    }


# -------------------------
# APPLY FIXES BETWEEN ROUNDS
# -------------------------

def apply_round_fixes(suite_result: dict) -> list[str]:
    """失敗タスクを分析してエージェント自身を修正。修正ログを返す。"""
    from self_fix import apply_fix

    failures = [r for r in suite_result["results"] if not r["success"] and not r.get("skipped")]
    fix_log: list[str] = []

    # 根本原因ごとに1回だけ修正（重複しない）
    applied_causes: set[str] = set()
    for r in failures:
        analysis = r.get("analysis", {})
        cause = analysis.get("root_cause", "unknown")
        if cause in applied_causes:
            continue
        applied_causes.add(cause)
        label = analysis.get("cause_label", cause)
        print(f"  [{r['id']}] 根本原因: {label}")
        apply_fix(analysis)
        fix_log.append(f"[{cause}] {label}: {analysis.get('fix_strategy', '—')}")

    return fix_log


# -------------------------
# REPORT GENERATOR
# -------------------------

def _get_model() -> str:
    try:
        sys.path.insert(0, str(AGENT_DIR))
        import llm
        return getattr(llm, "CODER_MODEL", "unknown")
    except Exception:
        return "unknown"


def _category_score(results: list[dict], cat: str) -> str:
    cat_r = [r for r in results if r["category"] == cat]
    if not cat_r:
        return "—"
    n_ok = sum(1 for r in cat_r if r["success"])
    icon = "✅" if n_ok == len(cat_r) else ("⚠️" if n_ok > 0 else "❌")
    return f"{n_ok}/{len(cat_r)} {icon}"


def save_round_report(suite_result: dict, loop_round: int) -> str:
    results = suite_result["results"]
    summary = suite_result["summary"]
    model = _get_model()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    cat_order = ["coding", "file", "pdf", "excel", "web"]
    cat_labels = {
        "coding": "Coding", "file": "File Operations",
        "pdf": "PDF", "excel": "Excel", "web": "Web",
    }

    lines = [
        f"# QA Report — Round {loop_round}",
        "",
        f"Run: {now}",
        f"Model: {model}",
        "",
        "## Summary",
        "",
        "| 指標 | 値 |",
        "|------|-----|",
        f"| 総テスト数 | {summary['total']} |",
        f"| 成功 | {summary['passed']} ({int(summary['pass_rate']*100)}%) |",
        f"| 失敗 | {summary['failed']} |",
        f"| リトライで成功 | {summary['retry_success']} |",
        f"| 総実行時間 | {summary['total_elapsed']}s |",
        "",
    ]

    for cat in cat_order:
        cat_results = [r for r in results if r["category"] == cat]
        if not cat_results:
            continue
        n_ok = sum(1 for r in cat_results if r["success"])
        lines += [
            f"## {cat_labels.get(cat, cat)} ({n_ok}/{len(cat_results)})",
            "",
            "| ID | Label | 結果 | Steps | Retry | 時間 | 理由 |",
            "|----|-------|------|-------|-------|------|------|",
        ]
        for r in cat_results:
            ok = "✅" if r["success"] else ("⏭️" if r.get("skipped") else "❌")
            tout = "⏱" if r.get("timed_out") else ""
            # ✨ = 自己改善で成功したケース
            si_mark = "✨" if r.get("self_improved") else ""
            reason_short = (r.get("reason") or "")[:40]
            lines.append(
                f"| {r['id']} | {r['label']} | {ok}{tout}{si_mark} | {r['steps_used']} "
                f"| {r.get('retry_count', 0)} | {r['elapsed']}s | {reason_short} |"
            )
        lines.append("")

    failures = [r for r in results if not r["success"] and not r.get("skipped")]
    if failures:
        lines += ["## Failed Tests", ""]
        for r in failures:
            analysis = r.get("analysis", {})
            lines += [
                f"### {r['id']}: {r['label']}",
                "",
                f"**根本原因:** {analysis.get('cause_label', analysis.get('root_cause', '不明'))}",
                f"**修正方針:** {analysis.get('fix_strategy', '—')}",
                "",
                "**最終ログ抜粋:**",
                "```",
            ]
            log = r.get("last_output", "")
            log_lines = log.splitlines()
            step_idx = [i for i, ln in enumerate(log_lines) if re.match(r"===== STEP \d+ =====", ln)]
            if step_idx:
                excerpt = "\n".join(log_lines[step_idx[-1]: step_idx[-1] + 30])
            else:
                excerpt = "\n".join(log_lines[-30:]) if log_lines else "(ログなし)"
            lines += [excerpt, "```", ""]
    else:
        lines += ["## Failed Tests", "", "すべて成功しました。", ""]

    md = "\n".join(lines)
    out_path = AGENT_DIR / f"qa_report_round{loop_round}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"  📄 {out_path.name} を保存")
    return md


def save_final_report(
    all_rounds: list[dict],
    fix_logs: list[list[str]],
    categories: list | None,
) -> str:
    """qa_report_final.md に全ラウンド比較を出力。"""
    model = _get_model()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cat_order = ["coding", "file", "pdf", "excel", "web"]
    cat_labels = {
        "coding": "Coding", "file": "File", "pdf": "PDF", "excel": "Excel", "web": "Web",
    }

    lines = [
        "# Final QA Report — 全ラウンド比較",
        "",
        f"Run: {now}",
        f"Model: {model}",
        "",
    ]

    # ---- ラウンド別サマリー ----
    lines += ["## ラウンド別サマリー", ""]
    header = "| カテゴリ |" + "".join(f" Round {i+1} |" for i in range(len(all_rounds)))
    sep = "|---------|" + "".join("---------|" for _ in all_rounds)
    lines += [header, sep]

    for cat in cat_order:
        row = f"| {cat_labels.get(cat, cat)} |"
        for suite in all_rounds:
            row += " " + _category_score(suite["results"], cat) + " |"
        lines.append(row)

    # 合計行
    total_row = "| **合計** |"
    for suite in all_rounds:
        s = suite["summary"]
        total_row += f" {s['passed']}/{s['total']} |"
    lines += [total_row, ""]

    # ---- ラウンド別詳細サマリー ----
    lines += ["## ラウンド別実行統計", ""]
    lines += ["| ラウンド | 成功 | 失敗 | 成功率 | 実行時間 |"]
    lines += ["|---------|------|------|-------|--------|"]
    for i, suite in enumerate(all_rounds):
        s = suite["summary"]
        lines.append(
            f"| Round {i+1} | {s['passed']} | {s['failed']} "
            f"| {int(s['pass_rate']*100)}% | {s['total_elapsed']}s |"
        )
    lines.append("")

    # ---- 修正履歴 ----
    lines += ["## 修正履歴", ""]
    for i, flog in enumerate(fix_logs):
        if not flog:
            continue
        lines += [f"### Round {i+1}→{i+2} の修正", ""]
        for entry in flog:
            lines.append(f"- {entry}")
        lines.append("")

    # ---- 最終失敗一覧 ----
    last_suite = all_rounds[-1]
    final_failures = [r for r in last_suite["results"] if not r["success"] and not r.get("skipped")]
    if final_failures:
        lines += ["## 最終ラウンド残存失敗 (要手動対応)", ""]
        for r in final_failures:
            analysis = r.get("analysis", {})
            lines += [
                f"- **{r['id']} {r['label']}**: {analysis.get('cause_label', '不明')}",
                f"  → {analysis.get('fix_strategy', '—')}",
            ]
        lines.append("")
    else:
        lines += ["## 最終ラウンド結果", "", "✅ 全テスト成功", ""]

    # ---- 成功率推移 ----
    lines += ["## 成功率推移", ""]
    for i, suite in enumerate(all_rounds):
        s = suite["summary"]
        bar_len = int(s["pass_rate"] * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"Round {i+1}: [{bar}] {int(s['pass_rate']*100)}% ({s['passed']}/{s['total']})")
    lines.append("")

    md = "\n".join(lines)
    out_path = AGENT_DIR / "qa_report_final.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"📄 {out_path.name} を保存")
    return md


# -------------------------
# MAIN LOOP
# -------------------------

def warmup_ollama() -> None:
    """Ollama を起動してモデルをメモリに乗せる（全カテゴリ共通）"""
    import requests as _req
    print("[WARMUP] Ollama ウォームアップ中...", end=" ", flush=True)
    try:
        resp = _req.post(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5-coder:7b",
                  "prompt": "reply ok", "stream": False,
                  "options": {"num_predict": 3}},
            timeout=600,  # 初回モデルロードは最大10分
        )
        if resp.status_code == 200:
            print("✅")
        else:
            print(f"⚠️ HTTP {resp.status_code}")
    except Exception as e:
        print(f"⚠️ {e}")


def main_loop(categories: list | None = None) -> None:
    check_and_install_dependencies()
    warmup_ollama()
    print()

    cats = categories or ALL_CATEGORIES
    all_rounds: list[dict] = []
    fix_logs: list[list[str]] = []
    prev_suite: dict | None = None

    for loop_round in range(1, LOOP_MAX + 1):
        print(f"\n{'='*60}")
        print(f"  ラウンド {loop_round}/{LOOP_MAX}")
        print(f"{'='*60}")

        suite = run_test_suite(
            categories=cats,
            loop_round=loop_round,
            prev_results=prev_suite,
        )
        all_rounds.append(suite)

        s = suite["summary"]
        print(f"\n  ラウンド {loop_round} 結果: {s['passed']}/{s['total']} ({int(s['pass_rate']*100)}%)")

        save_round_report(suite, loop_round)

        if s["pass_rate"] >= 1.0:
            print(f"\n✅ 全テスト成功 — ラウンド {loop_round} で終了")
            fix_logs.append([])  # このラウンドの修正なし
            break

        if loop_round < LOOP_MAX:
            print(f"\n  失敗タスクを分析・修正中...")
            flog = apply_round_fixes(suite)
            fix_logs.append(flog)
            if flog:
                print(f"  修正 {len(flog)} 件適用")
            else:
                print("  適用可能な自動修正なし")
        else:
            fix_logs.append([])

        prev_suite = suite

    print("\n" + "=" * 60)
    print("  最終レポート生成")
    print("=" * 60)
    final_md = save_final_report(all_rounds, fix_logs, cats)
    print("\n" + final_md)


# -------------------------
# ENTRYPOINT
# -------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto QA Loop with round iterations")
    parser.add_argument(
        "--categories", "-c",
        nargs="*",
        choices=list(CATEGORY_FILES.keys()),
        default=None,
        help="実行するカテゴリ (省略時=全て)",
    )
    parser.add_argument(
        "--rounds", "-r",
        type=int,
        default=LOOP_MAX,
        help=f"最大ラウンド数 (デフォルト={LOOP_MAX})",
    )
    args = parser.parse_args()

    # LOOP_MAXを上書き可能に（モジュールレベル変数を直接再代入）
    LOOP_MAX = args.rounds

    print("=== Auto QA Loop 開始 ===")
    main_loop(categories=args.categories)
