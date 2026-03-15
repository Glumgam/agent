"""
self_fix.py — 失敗タスクの原因分析、修正案生成、エージェント自己修正
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR))


# -------------------------
# ROOT CAUSE CATEGORIES
# -------------------------

# ログシグナル → 根本原因キー (apply_fix のキーと合わせる)
_SIGNAL_TO_CAUSE: list[tuple[str, str]] = [
    ("JSON parse failed",        "json_parse_error"),
    ("ループ検出",                "loop_detected"),
    ("loop guard",               "loop_detected"),
    ("repeated action",          "loop_detected"),
    ("ModuleNotFoundError",      "import_error"),
    ("ImportError",              "import_error"),
    ("No module named",          "import_error"),
    ("SyntaxError",              "syntax_error"),
    ("タイムアウト",              "timeout"),
    ("TimeoutExpired",           "timeout"),
    ("Error: command timeout",   "timeout"),
    ("Ollama",                   "ollama_error"),
    ("exit code 1",              "runtime_error"),
    ("Traceback",                "runtime_error"),
    ("invalid tool",             "invalid_tool"),
]

# 根本原因キー → 人間向け日本語ラベル
_CAUSE_LABELS: dict[str, str] = {
    "json_parse_error": "JSONパース失敗",
    "loop_detected":    "ループ検出による強制終了",
    "import_error":     "importエラー（モジュール未インストール）",
    "syntax_error":     "構文エラー",
    "timeout":          "タイムアウト",
    "ollama_error":     "Ollama接続エラー",
    "runtime_error":    "実行時エラー",
    "invalid_tool":     "無効ツール名",
    "done_not_declared": "done宣言なし（MAX_STEPS消費）",
}


def _detect_root_cause(agent_output: str) -> str:
    for signal, cause in _SIGNAL_TO_CAUSE:
        if signal in agent_output:
            return cause
    if not agent_output.strip():
        return "timeout"
    # 30ステップ使い切ったが done なし
    if agent_output.count("===== STEP") >= 28:
        return "done_not_declared"
    return "runtime_error"


# -------------------------
# ANALYZE
# -------------------------

def analyze_failure(task_def: dict, agent_output: str) -> dict:
    """
    失敗内容を分析し、根本原因・修正方針・タスク補足指示を返す。

    Returns:
        {
            "root_cause": str,       # 根本原因キー
            "cause_label": str,      # 人間向けラベル
            "fix_strategy": str,
            "prompt_injection": str,
        }
    """
    cause = _detect_root_cause(agent_output)
    label = _CAUSE_LABELS.get(cause, cause)

    # ---- ループ検出 ----
    if cause == "loop_detected":
        return {
            "root_cause": cause,
            "cause_label": label,
            "fix_strategy": "タスク文に「同じコマンドを繰り返さず、前の結果をよく読め」と追記",
            "prompt_injection": (
                "\n\n[RETRY HINT] 前の試行ではループ検出により強制終了した。"
                "同じコマンドを2回以上繰り返さないこと。"
                "前のステップの結果を必ず確認してから次のアクションを選べ。"
                "タスクが完了したら即座に {\"tool\": \"done\"} を返せ。"
            ),
        }

    # ---- importエラー ----
    if cause == "import_error":
        # どのモジュールか推定
        m = re.search(r"No module named '?([a-zA-Z0-9_]+)'?", agent_output)
        pkg = m.group(1) if m else "unknown"
        return {
            "root_cause": cause,
            "cause_label": label,
            "fix_strategy": f"pip install {pkg} で必要なパッケージをインストールしてから再実行",
            "prompt_injection": (
                f"\n\n[RETRY HINT] 前の試行でimportエラーが発生した（{pkg}）。"
                f"まず {{\"tool\": \"run\", \"command\": \"pip install {pkg}\"}} でインストールせよ。"
                "インストール後に再度スクリプトを実行せよ。"
            ),
        }

    # ---- 構文エラー ----
    if cause == "syntax_error":
        return {
            "root_cause": cause,
            "cause_label": label,
            "fix_strategy": "構文エラーを read_file で確認してから修正・再実行",
            "prompt_injection": (
                "\n\n[RETRY HINT] 前の試行でSyntaxErrorが発生した。"
                "ファイルを read_file で読み込み、構文エラーを修正してから再実行せよ。"
            ),
        }

    # ---- タイムアウト ----
    if cause == "timeout":
        return {
            "root_cause": cause,
            "cause_label": label,
            "fix_strategy": "処理をより小さなステップに分割するか、タイムアウト値を増やす",
            "prompt_injection": (
                "\n\n[RETRY HINT] 前の試行でタイムアウトが発生した。"
                "処理をより小さなステップに分け、一つ一つ確認しながら進めよ。"
            ),
        }

    # ---- done宣言なし ----
    if cause == "done_not_declared":
        return {
            "root_cause": cause,
            "cause_label": label,
            "fix_strategy": "SYSTEM_PROMPT の done条件を強化済み。リトライで改善されるはず。",
            "prompt_injection": (
                "\n\n[RETRY HINT] タスクが完了したら即座に {\"tool\": \"done\"} を返すこと。"
                "成功を確認したらすぐ done を宣言せよ。余分なステップを追加するな。"
            ),
        }

    # ---- LLM フォールバック ----
    try:
        from llm import ask_planner
        snippet = agent_output[-2000:] if len(agent_output) > 2000 else agent_output
        prompt = (
            "あなたはソフトウェアエンジニアリングエージェントのデバッガーです。\n\n"
            f"タスク: {task_def.get('task', '')}\n"
            f"期待する出力: {task_def.get('expect_contains', '')}\n\n"
            f"エージェントのログ（末尾）:\n{snippet}\n\n"
            "以下の3項目を日本語で回答せよ。各項目を指定のプレフィックスで始めること。\n"
            "ROOT_CAUSE: 失敗の根本原因を一文で\n"
            "FIX_STRATEGY: 修正方針を一文で\n"
            "PROMPT_INJECTION: 次のリトライでタスク文末に追記する補足指示（2〜3文）\n"
        )
        resp = ask_planner(prompt)
        result = {
            "root_cause": cause,
            "cause_label": label,
            "fix_strategy": "LLM分析による修正",
            "prompt_injection": (
                "\n\n[RETRY HINT] 前回の試行に失敗した。"
                "別のアプローチを試み、完了したら {\"tool\": \"done\"} を返せ。"
            ),
        }
        for ln in resp.splitlines():
            if ln.startswith("ROOT_CAUSE:"):
                result["cause_label"] = ln[len("ROOT_CAUSE:"):].strip()
            elif ln.startswith("FIX_STRATEGY:"):
                result["fix_strategy"] = ln[len("FIX_STRATEGY:"):].strip()
            elif ln.startswith("PROMPT_INJECTION:"):
                result["prompt_injection"] = "\n\n[RETRY HINT] " + ln[len("PROMPT_INJECTION:"):].strip()
        return result
    except Exception as e:
        return {
            "root_cause": cause,
            "cause_label": label,
            "fix_strategy": f"自動分析失敗: {e}",
            "prompt_injection": (
                "\n\n[RETRY HINT] 前回の試行に失敗した。"
                "別のアプローチを試み、完了したら {\"tool\": \"done\"} を返せ。"
            ),
        }


def build_retry_task(task_def: dict, analysis: dict) -> str:
    base = task_def.get("task", "")
    injection = analysis.get("prompt_injection", "")
    return base + injection


# -------------------------
# APPLY FIX — エージェント自己修正
# -------------------------

def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _fix_done_prompt(_analysis: dict) -> None:
    """llm.py の SYSTEM_PROMPT に done宣言強化パッチを追加（未適用なら）。"""
    llm_path = AGENT_DIR / "llm.py"
    content = _read_file(llm_path)
    marker = "DONE DECLARATION — MANDATORY"
    if marker in content:
        print("  (SYSTEM_PROMPT done宣言はすでに適用済み — スキップ)")
        return
    patch = (
        "\n\n[DONE DECLARATION — MANDATORY]\n"
        "Output {\"tool\": \"done\"} IMMEDIATELY when the expected output is confirmed.\n"
        "DO NOT add extra steps after a successful verification run.\n"
    )
    # SYSTEM_PROMPT 文字列の閉じ三重クオートの直前に挿入
    new_content = content.replace('"""\n\n\n# -------------------------\n# CLEAN LLM OUTPUT', patch + '"""\n\n\n# -------------------------\n# CLEAN LLM OUTPUT')
    if new_content != content:
        _write_file(llm_path, new_content)
        print("  → llm.py SYSTEM_PROMPT に done宣言を追記しました")
    else:
        print("  (SYSTEM_PROMPT 挿入ポイントが見つからず — スキップ)")


def _fix_pythonpath(_analysis: dict) -> None:
    """tools_run.py の subprocess.run に PYTHONPATH を追加。"""
    path = AGENT_DIR / "tools_run.py"
    content = _read_file(path)
    if "PYTHONPATH" in content:
        print("  (PYTHONPATH はすでに設定済み — スキップ)")
        return
    # run_command に env= を追加するのは command_runner.py
    cr_path = AGENT_DIR / "command_runner.py"
    cr = _read_file(cr_path)
    if "PYTHONPATH" in cr:
        print("  (command_runner.py PYTHONPATH はすでに設定済み — スキップ)")
        return
    old = "        result = subprocess.run(\n            parts,\n            capture_output=True,\n            text=True,\n            cwd=WORKSPACE,"
    new = (
        "        _env = {**__import__('os').environ, 'PYTHONPATH': str(WORKSPACE)}\n"
        "        result = subprocess.run(\n            parts,\n            capture_output=True,\n            text=True,\n            cwd=WORKSPACE,\n            env=_env,"
    )
    new_cr = cr.replace(old, new)
    if new_cr != cr:
        _write_file(cr_path, new_cr)
        print("  → command_runner.py に PYTHONPATH を追加しました")
    else:
        print("  (command_runner.py 挿入ポイントが見つからず — スキップ)")


def _fix_json_parser(_analysis: dict) -> None:
    """parser.py の JSON修復ヒントをコメントに追記（情報のみ）。"""
    path = AGENT_DIR / "parser.py"
    if not path.exists():
        print("  (parser.py が見つからず — スキップ)")
        return
    content = _read_file(path)
    if "# [AUTO-FIX] escape hint" in content:
        print("  (parser.py はすでにパッチ済み — スキップ)")
        return
    # ファイル先頭にコメント追加
    _write_file(path, "# [AUTO-FIX] escape hint: watch for literal newlines in content field\n" + content)
    print("  → parser.py にエスケープヒントを追記しました")


def _fix_timeout(_analysis: dict) -> None:
    """command_runner.py の pdf/pip タイムアウトを延長。"""
    path = AGENT_DIR / "command_runner.py"
    content = _read_file(path)
    if '"pip":    180' in content:
        print("  (タイムアウトはすでに延長済み — スキップ)")
        return
    old = '"pip":    120,'
    new = '"pip":    180,'
    new_content = content.replace(old, new)
    if new_content == content:
        # 別のフォーマット
        old = '"pip": 120'
        new = '"pip": 180'
        new_content = content.replace(old, new)
    if new_content != content:
        _write_file(path, new_content)
        print("  → command_runner.py pip タイムアウトを 120→180秒に変更しました")
    else:
        print("  (command_runner.py のタイムアウト定数が見つからず — スキップ)")


def _fix_loop_threshold(_analysis: dict) -> None:
    """security.py の MAX_REPEAT を緩和。"""
    path = AGENT_DIR / "security.py"
    content = _read_file(path)
    # 現在値を確認
    m = re.search(r"MAX_REPEAT\s*=\s*(\d+)", content)
    if not m:
        print("  (security.py の MAX_REPEAT が見つからず — スキップ)")
        return
    current = int(m.group(1))
    if current >= 4:
        print(f"  (MAX_REPEAT={current} はすでに十分 — スキップ)")
        return
    new_val = current + 1
    new_content = re.sub(r"MAX_REPEAT\s*=\s*\d+", f"MAX_REPEAT = {new_val}", content)
    _write_file(path, new_content)
    print(f"  → security.py MAX_REPEAT を {current}→{new_val} に変更しました")


def _fix_context_budget(_analysis: dict) -> None:
    """main.py の CONTEXT_CHAR_BUDGET を若干増やす。"""
    path = AGENT_DIR / "main.py"
    content = _read_file(path)
    m = re.search(r"CONTEXT_CHAR_BUDGET\s*=\s*(\d+)", content)
    if not m:
        print("  (main.py の CONTEXT_CHAR_BUDGET が見つからず — スキップ)")
        return
    current = int(m.group(1))
    if current >= 8000:
        print(f"  (CONTEXT_CHAR_BUDGET={current} はすでに十分 — スキップ)")
        return
    new_val = min(current + 1000, 8000)
    new_content = re.sub(r"CONTEXT_CHAR_BUDGET\s*=\s*\d+", f"CONTEXT_CHAR_BUDGET = {new_val}", content)
    _write_file(path, new_content)
    print(f"  → main.py CONTEXT_CHAR_BUDGET を {current}→{new_val} に変更しました")


# 根本原因キー → 修正関数
_FIX_MAP: dict[str, object] = {
    "done_not_declared": _fix_done_prompt,
    "import_error":      _fix_pythonpath,
    "json_parse_error":  _fix_json_parser,
    "timeout":           _fix_timeout,
    "loop_detected":     _fix_loop_threshold,
    "context_overflow":  _fix_context_budget,
}


def apply_fix(analysis: dict) -> None:
    """
    根本原因に応じてエージェント自身を修正する。

    根本原因 → 修正対象:
      done_not_declared  → llm.py の SYSTEM_PROMPT
      import_error       → command_runner.py の PYTHONPATH 設定
      json_parse_error   → parser.py のエスケープヒント
      timeout            → command_runner.py の COMMAND_TIMEOUTS
      loop_detected      → security.py の MAX_REPEAT
      context_overflow   → main.py の CONTEXT_CHAR_BUDGET
    """
    cause = analysis.get("root_cause", "unknown")
    label = analysis.get("cause_label", cause)
    fixer = _FIX_MAP.get(cause)

    if fixer:
        print(f"  🔧 自動修正: {cause} ({label})")
        fixer(analysis)
    else:
        print(f"  ⚠️  手動対応が必要: {cause} ({label})")
        print(f"     提案: {analysis.get('fix_strategy', '不明')}")
