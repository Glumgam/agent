import shlex
import subprocess


def run(cmd):
    try:
        parts = shlex.split(cmd)
    except ValueError as e:
        return f"Error: invalid command syntax: {e}"

    if not parts:
        return "Error: empty command"

    result = subprocess.run(
        parts,
        shell=False,
        capture_output=True,
        text=True,
    )

    return result.stdout + result.stderr
