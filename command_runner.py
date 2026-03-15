"""
command_runner.py — カテゴリB: コマンド実行

- _diagnose_python_error()
- run_command()
"""

import subprocess
import shlex
import re

from project_map import WORKSPACE
from security import ALLOWED_COMMANDS, VENV_PYTHON, _validate_pip_install


# -------------------------
# PYTHON ERROR DIAGNOSTICS
# -------------------------

def _diagnose_python_error(stderr: str) -> str:
    if not stderr:
        return ""

    hints = []

    if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
        module_name = re.findall(r"No module named '([^']+)'", stderr)
        if module_name:
            hints.append(
                f"💡 Hint: module '{module_name[0]}' missing → try: pip install {module_name[0]}"
            )

    if "SyntaxError" in stderr:
        hints.append("💡 Hint: SyntaxError → check parentheses or quotes")

    if "IndentationError" in stderr:
        hints.append("💡 Hint: indentation issue detected")

    if "FileNotFoundError" in stderr:
        hints.append("💡 Hint: file not found")

    if "PermissionError" in stderr:
        hints.append("💡 Hint: permission denied")

    return "\n".join(hints)


# -------------------------
# TIMEOUT CONFIGURATION
# -------------------------

DEFAULT_TIMEOUT = 30
COMMAND_TIMEOUTS = {
    "pip":    120,
    "pytest": 90,
    "python": 60,
    "npm":    120,
    "curl":   30,
    "wget":   60,
}


def _get_timeout(cmd: str) -> int:
    return COMMAND_TIMEOUTS.get(cmd, DEFAULT_TIMEOUT)


# -------------------------
# RUN COMMAND
# -------------------------

def run_command(command: str) -> str:
    if not command or not command.strip():
        return "Error: empty command"

    command = command.replace("workspace/", "")

    try:
        parts = shlex.split(command)
    except ValueError as e:
        return f"Error: invalid command syntax: {e}"

    if not parts:
        return "Error: empty command"

    cmd = parts[0]

    if cmd not in ALLOWED_COMMANDS:
        return (
            f"Error: command '{cmd}' not allowed\n"
            f"Allowed: {sorted(ALLOWED_COMMANDS)}"
        )

    if cmd in ("python", "python3"):
        parts[0] = VENV_PYTHON
    # --- LOOP FIX START ---
    elif cmd == "pip":
        # pip → venv の pip に置換（PATH に pip がない環境でも動作）
        import os
        venv_pip = os.path.join(os.path.dirname(VENV_PYTHON), "pip")
        if os.path.exists(venv_pip):
            parts[0] = venv_pip
        else:
            # pip バイナリがなければ python -m pip で代替
            parts = [VENV_PYTHON, "-m", "pip"] + parts[1:]
    # --- LOOP FIX END ---

    pip_error = _validate_pip_install(parts)
    if pip_error:
        return pip_error

    timeout = _get_timeout(cmd)

    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            cwd=WORKSPACE,
            timeout=timeout,
            shell=False,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        diag = _diagnose_python_error(stderr)

        output = [f"[exit code {result.returncode}]"]
        if stdout:
            output.append(stdout)
        if stderr:
            output.append("[stderr]")
            output.append(stderr)
        if diag:
            output.append(diag)

        final = "\n".join(output)
        if len(final) > 4000:
            final = final[:2000] + "\n\n...[truncated]...\n\n" + final[-2000:]

        return final

    except subprocess.TimeoutExpired:
        return f"Error: command timeout ({timeout}s)"

    except Exception as e:
        return f"Error running command: {e}"
