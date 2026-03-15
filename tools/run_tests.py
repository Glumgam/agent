import shutil
import subprocess
import sys

from project_map import WORKSPACE


def _run_command(cmd: list) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=WORKSPACE,
            timeout=300,
            shell=False,
        )
        out = []
        out.append(f"[exit code {result.returncode}]")
        if result.stdout:
            out.append(result.stdout.strip())
        if result.stderr:
            out.append("[stderr]")
            out.append(result.stderr.strip())
        return "\n".join(out)
    except Exception as e:
        return f"Error running tests: {e}"


def run_tests():
    if shutil.which("pytest"):
        return _run_command(["pytest", "-q"])
    return _run_command([sys.executable, "-m", "unittest"])
