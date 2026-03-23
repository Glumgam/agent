"""
自動生成ツール: tool_batch_cli_command
目的: 複数のCLIコマンドを一括して実行する機能提供
情報源: スキル発展
生成日: 2026-03-24
テスト: ✅ 通過済み
"""
import subprocess

def tool_batch_cli_command(commands):
    """
    Executes multiple CLI commands in batch.

    Args:
        commands (str): A string containing the CLI commands separated by newlines.

    Returns:
        str: Output of all commands or an error message.
    """
    try:
        output = ""
        for command in commands.split("\n"):
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            output += result.stdout
        return output.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: Command failed with exit code {e.returncode}: {e.stderr}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    commands = """
    echo Hello, World!
    date
    ls -la
    """
    print(tool_batch_cli_command(commands))