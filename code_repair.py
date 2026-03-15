"""
Auto Code Repair モジュール。
失敗したPythonスクリプトをLLMが分析し、修正して適用する。

フロー:
  失敗コード + エラーログ
       ↓
  LLMが修正コードを生成（patch → rewrite の2段階）
       ↓
  構文チェック
       ↓
  バックアップ作成
       ↓
  ファイルに適用
       ↓
  実行して確認（失敗なら復元）
"""

# --- AUTO REPAIR START ---
import re
import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

AGENT_ROOT = Path(__file__).parent
BACKUP_DIR = AGENT_ROOT / "repair_backups"
REPAIR_LOG = AGENT_ROOT / "repair_log.md"


@dataclass
class RepairResult:
    success: bool
    strategy: str          # "patch" / "rewrite" / "failed"
    file_repaired: str
    backup_path: str
    description: str
    error: str = ""


# =====================================================
# メインエントリ
# =====================================================

def repair_file(
    file_path: str,
    error_log: str,
    task_description: str = "",
    max_attempts: int = 2,
) -> RepairResult:
    """
    失敗したファイルをLLMで修復する。
    patch（最小修正）→ rewrite（完全書き直し）の順で試みる。
    """
    path = AGENT_ROOT / "workspace" / file_path
    if not path.exists():
        path = AGENT_ROOT / file_path
    if not path.exists():
        return RepairResult(
            success=False, strategy="failed",
            file_repaired=file_path, backup_path="",
            description="ファイルが見つからない",
            error=f"Not found: {file_path}"
        )

    original_code = path.read_text(encoding="utf-8")

    for attempt in range(1, max_attempts + 1):
        print(f"    🔨 修復試行 {attempt}/{max_attempts}: {file_path}")
        strategy = "patch" if attempt == 1 else "rewrite"
        result = _attempt_repair(
            path=path,
            original_code=original_code,
            error_log=error_log,
            task_description=task_description,
            strategy=strategy,
        )
        if result.success:
            _log_repair(result, original_code, error_log)
            return result
        print(f"      ⚠️ 修復失敗: {result.error}")

    return RepairResult(
        success=False, strategy="failed",
        file_repaired=str(file_path), backup_path="",
        description="全修復試行が失敗",
        error="max_attempts exceeded"
    )


def _attempt_repair(
    path: Path,
    original_code: str,
    error_log: str,
    task_description: str,
    strategy: str,
) -> RepairResult:
    """1回の修復試行"""
    if strategy == "patch":
        repaired_code = _llm_generate_patch(original_code, error_log, task_description)
    else:
        repaired_code = _llm_rewrite(original_code, error_log, task_description)

    if not repaired_code:
        return RepairResult(
            success=False, strategy=strategy,
            file_repaired=str(path), backup_path="",
            description="LLMが空のコードを返した",
            error="empty response"
        )

    # 構文チェック
    syntax_ok, syntax_error = _check_syntax(repaired_code)
    if not syntax_ok:
        return RepairResult(
            success=False, strategy=strategy,
            file_repaired=str(path), backup_path="",
            description=f"構文エラー: {syntax_error}",
            error=syntax_error
        )

    # バックアップ作成
    backup_path = create_backup(path)

    # ファイルに適用
    path.write_text(repaired_code, encoding="utf-8")
    print(f"      📝 適用完了: {path.name}")

    # 実行して確認
    run_ok, run_output = _verify_repair(path)
    if run_ok:
        return RepairResult(
            success=True, strategy=strategy,
            file_repaired=str(path.name),
            backup_path=str(backup_path),
            description=f"{strategy}による修復成功",
        )

    # 失敗 → バックアップから復元
    shutil.copy2(backup_path, path)
    print(f"      🔙 復元: {path.name}")
    return RepairResult(
        success=False, strategy=strategy,
        file_repaired=str(path.name),
        backup_path=str(backup_path),
        description="修復後の実行失敗・復元済み",
        error=run_output[-200:]
    )


# =====================================================
# LLMコード生成
# =====================================================

def _llm_generate_patch(
    original_code: str,
    error_log: str,
    task_description: str,
) -> str:
    """最小限の修正で修復する（patch戦略）"""
    from llm import ask_plain
    prompt = (
        "You are a Python code repair expert. Fix the following Python code that has an error.\n\n"
        f"TASK: {task_description}\n\n"
        "ORIGINAL CODE:\n"
        "```python\n"
        f"{original_code}\n"
        "```\n\n"
        "ERROR:\n"
        "```\n"
        f"{error_log[-800:]}\n"
        "```\n\n"
        "Rules:\n"
        "1. Return ONLY the complete fixed Python code\n"
        "2. No explanations, no markdown, no code fences\n"
        "3. Fix only what is necessary - minimal changes\n"
        "4. Ensure the code runs without errors\n"
        "5. Keep the original logic and structure\n"
        "FIXED CODE:"
    )
    return _extract_code(ask_plain(prompt))


def _llm_rewrite(
    original_code: str,
    error_log: str,
    task_description: str,
) -> str:
    """コードを完全に書き直す（rewrite戦略・最終手段）"""
    from llm import ask_plain
    prompt = (
        "You are a Python expert. The following code has a persistent error. Rewrite it completely.\n\n"
        f"TASK: {task_description}\n\n"
        "BROKEN CODE (for reference):\n"
        "```python\n"
        f"{original_code}\n"
        "```\n\n"
        "ERROR:\n"
        "```\n"
        f"{error_log[-600:]}\n"
        "```\n\n"
        "Rules:\n"
        "1. Return ONLY complete, working Python code\n"
        "2. No explanations, no markdown, no code fences\n"
        "3. The code must run without errors\n"
        "4. Accomplish the same task as the original\n"
        "REWRITTEN CODE:"
    )
    return _extract_code(ask_plain(prompt))


def _extract_code(response: str) -> str:
    """LLMレスポンスからコード部分を抽出"""
    match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\n?(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # バッククォートなし: 先頭の "python\n" だけ取り除く
    text = response.strip()
    if text.startswith("python\n"):
        text = text[len("python\n"):]
    return text


# =====================================================
# 検証・ユーティリティ
# =====================================================

def _check_syntax(code: str) -> tuple:
    """Pythonの構文チェック"""
    try:
        compile(code, "<string>", "exec")
        return True, ""
    except SyntaxError as e:
        return False, str(e)


def _verify_repair(path: Path) -> tuple:
    """修復後のファイルを実行して確認"""
    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True, text=True,
            cwd=str(path.parent), timeout=30
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def create_backup(path: Path) -> Path:
    """バックアップを作成して返す"""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{path.stem}_{timestamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    return backup_path


def _log_repair(result: RepairResult, original_code: str, error_log: str):
    """修復ログをMarkdownに記録"""
    with open(REPAIR_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — {result.file_repaired}\n")
        f.write(f"**戦略:** {result.strategy}\n")
        f.write(f"**結果:** {'✅ 成功' if result.success else '❌ 失敗'}\n")
        f.write(f"**説明:** {result.description}\n")
        f.write(f"**エラーログ（抜粋）:**\n```\n{error_log[-300:]}\n```\n")
# --- AUTO REPAIR END ---
