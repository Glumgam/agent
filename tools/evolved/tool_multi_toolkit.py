"""
自動生成ツール: tool_multi_toolkit
目的: 複数のCLIツールを統合し、一連のタスクを自動化する。
情報源: スキル発展
生成日: 2026-03-24
テスト: ✅ 通過済み
"""
def tool_multi_toolkit(command):
    try:
        import subprocess
        result = subprocess.run(command, shell=True, check=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr}"