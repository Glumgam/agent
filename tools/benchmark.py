#!/usr/bin/env python3
"""
tools/benchmark.py — エージェントベンチマーク

5タスクを順番に実行して品質を計測し benchmark_result.md に出力する。
"""

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

AGENT_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = AGENT_DIR / "workspace"
VENV_PYTHON = str(AGENT_DIR / "venv" / "bin" / "python")
MAIN_PY = str(AGENT_DIR / "main.py")

TASKS = [
    {
        "id": "T1",
        "label": "Hello World",
        "input": "hello.pyを作成してHello, World!を出力せよ",
        "expect_output": "Hello, World!",
        "max_steps": 5,
    },
    {
        "id": "T2",
        "label": "FizzBuzz",
        "input": "1から15までのFizzBuzzをPythonで実装して実行せよ",
        "expect_output": "FizzBuzz",
        "max_steps": 8,
    },
    {
        "id": "T3",
        "label": "複数ファイル",
        "input": "utils.pyにadd(a,b)関数を実装し、main.pyからimportして add(3,4) の結果を出力せよ",
        "expect_output": "7",
        "max_steps": 10,
    },
    {
        "id": "T4",
        "label": "自己修復",
        "input": "わざと構文エラーを含むbuggy.pyを作成してから自分で修正し、python buggy.pyが成功するようにせよ",
        "expect_output": "exit code 0",
        "max_steps": 15,
    },
    {
        "id": "T5",
        "label": "TODO CLI",
        "input": "todo.py/storage.py/cli.pyを作成し、python cli.py add '買い物' → list → done 1 → list を全て成功させよ",
        "expect_output": "買い物",
        "max_steps": 30,
    },
]


# -------------------------
# UTILITIES
# -------------------------

def _check_success(stdout: str, expect: str) -> bool:
    """
    expect が実際のコマンド実行結果に含まれるか検証する。
    PLAN行や[CONTEXT]行などでの誤検出を防ぐため、
    '結果:' プレフィックスの行か '[exit code 0]' 直後のブロックのみを対象にする。
    """
    lines = stdout.splitlines()
    # 1. '結果:' 行に含まれるか
    for ln in lines:
        if ln.startswith("結果:") and expect in ln:
            return True
    # 2. '[exit code 0]' の後ろのテキストブロック (最大20行) に含まれるか
    for i, ln in enumerate(lines):
        if "[exit code 0]" in ln:
            block = "\n".join(lines[i:i + 20])
            if expect in block:
                return True
    return False


def _extract_pct(line: str) -> int:
    m = re.search(r"\((\d+)%\)", line)
    return int(m.group(1)) if m else 0


def clean_workspace():
    """ワークスペースをクリアして空ディレクトリを再作成する。"""
    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def check_ollama() -> bool:
    """Ollama が起動しているか確認する。"""
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


# -------------------------
# TASK RUNNER
# -------------------------

def run_task(task: dict) -> dict:
    """タスクを実行して計測結果を返す。"""
    max_steps = task["max_steps"]
    timeout_sec = max_steps * 40 + 90  # ステップ数に比例した余裕タイムアウト

    clean_workspace()

    start = time.time()
    timed_out = False
    stdout = ""
    stderr = ""

    try:
        proc = subprocess.run(
            [VENV_PYTHON, MAIN_PY],
            input=task["input"],
            capture_output=True,
            text=True,
            cwd=str(AGENT_DIR),
            timeout=timeout_sec,
            env={**os.environ, "PYTHONPATH": str(AGENT_DIR)},
        )
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        timed_out = True

    elapsed = round(time.time() - start, 1)

    # --- 計測 ---
    steps_used = len(re.findall(r"===== STEP \d+ =====", stdout))
    done_declared = bool(re.search(r"^完了$", stdout, re.MULTILINE))
    json_repairs = stdout.count("JSON parse failed")
    tot_activations = len(re.findall(r"\[ToT\] step=\d+ — 候補", stdout))
    context_overflow_lines = [
        ln for ln in stdout.splitlines()
        if ln.startswith("[CONTEXT]") and "%" in ln
    ]
    context_overflows = sum(1 for ln in context_overflow_lines if _extract_pct(ln) > 100)

    # 成功判定: expect_output が実行結果行 (結果: …) に含まれるか
    # PLAN出力やログ行での誤検出を防ぐため、結果行かつ exit code 0 ブロックで確認
    success = _check_success(stdout, task["expect_output"])

    # 失敗時: 最後の STEP 以降のログを抽出 (最大40行)
    last_log = ""
    if not success:
        lines = stdout.splitlines()
        step_indices = [i for i, ln in enumerate(lines) if re.match(r"===== STEP \d+ =====", ln)]
        start_idx = step_indices[-1] if step_indices else max(0, len(lines) - 40)
        last_log = "\n".join(lines[start_idx:start_idx + 40])

    return {
        "id": task["id"],
        "label": task["label"],
        "success": success,
        "steps_used": steps_used,
        "max_steps": max_steps,
        "done_declared": done_declared,
        "json_repairs": json_repairs,
        "tot_activations": tot_activations,
        "context_overflows": context_overflows,
        "elapsed_sec": elapsed,
        "timed_out": timed_out,
        "last_log": last_log,
    }


# -------------------------
# MARKDOWN FORMATTER
# -------------------------

def format_md(results: list, model: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Benchmark Results",
        "",
        f"Run: {now}",
        f"Model: {model}",
        "",
        "| Task | Label | Success | Steps | Done宣言 | JSON修復 | ToT発動 | CTX溢れ | 時間(s) |",
        "|------|-------|---------|-------|---------|---------|--------|--------|--------|",
    ]

    for r in results:
        ok = "✅" if r["success"] else "❌"
        done = "✅" if r["done_declared"] else "❌"
        steps = f"{r['steps_used']}/{r['max_steps']}"
        lines.append(
            f"| {r['id']} | {r['label']} | {ok} | {steps} | {done} | "
            f"{r['json_repairs']} | {r['tot_activations']} | {r['context_overflows']} | {r['elapsed_sec']}s |"
        )

    n = len(results)
    n_success = sum(1 for r in results if r["success"])
    n_done = sum(1 for r in results if r["done_declared"])
    avg_steps = round(sum(r["steps_used"] for r in results) / n, 1) if n else 0
    total_repairs = sum(r["json_repairs"] for r in results)
    total_time = round(sum(r["elapsed_sec"] for r in results), 1)
    pct = round(n_success / n * 100) if n else 0

    lines += [
        "",
        "## Summary",
        "",
        f"- 成功率: {n_success}/{n} ({pct}%)",
        f"- 平均ステップ数: {avg_steps}",
        f"- done自発宣言率: {n_done}/{n}",
        f"- JSON修復合計: {total_repairs}回",
        f"- 総実行時間: {total_time}s",
        "",
    ]

    failures = [r for r in results if not r["success"]]
    if failures:
        lines += ["## 問題が見つかったタスク", ""]
        for r in failures:
            status = "タイムアウト" if r.get("timed_out") else "失敗"
            lines += [
                f"### {r['id']} — {r['label']} ({status})",
                "",
                "最終ステップのログ:",
                "```",
                r["last_log"] or "(ログなし)",
                "```",
                "",
            ]
    else:
        lines += ["## 問題が見つかったタスク", "", "すべてのタスクが成功しました。", ""]

    return "\n".join(lines)


# -------------------------
# MAIN
# -------------------------

def get_model() -> str:
    try:
        sys.path.insert(0, str(AGENT_DIR))
        import llm
        return getattr(llm, "CODER_MODEL", getattr(llm, "MODEL", "unknown"))
    except Exception:
        return "unknown"


def main():
    print(f"=== Benchmark 開始 ({len(TASKS)}タスク) ===")
    print(f"AGENT_DIR:    {AGENT_DIR}")
    print(f"WORKSPACE:    {WORKSPACE_DIR}")
    print(f"VENV_PYTHON:  {VENV_PYTHON}")
    print()

    if not check_ollama():
        print("❌ Ollama が起動していません。localhost:11434 を確認してください。")
        sys.exit(1)
    print("✅ Ollama 起動確認")
    print()

    model = get_model()
    results = []

    for task in TASKS:
        print(f"[{task['id']}] {task['label']} (max_steps={task['max_steps']}) 開始...")
        r = run_task(task)
        results.append(r)
        ok_str = "✅" if r["success"] else "❌"
        tout = " (タイムアウト)" if r["timed_out"] else ""
        print(f"[{task['id']}] {ok_str} steps={r['steps_used']}/{r['max_steps']}"
              f"  done={r['done_declared']}  repairs={r['json_repairs']}"
              f"  elapsed={r['elapsed_sec']}s{tout}")
        print()

    md = format_md(results, model)
    out_path = AGENT_DIR / "benchmark_result.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"📄 {out_path} に保存しました")
    print()
    print(md)


if __name__ == "__main__":
    main()
