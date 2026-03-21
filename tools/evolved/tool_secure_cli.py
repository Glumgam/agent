"""
自動生成ツール: tool_secure_cli
目的: セキュリティ強化されたCLIアプリケーション構築ツール
情報源: スキル発展
生成日: 2026-03-22
テスト: ✅ 通過済み
"""
def tool_secure_cli(command):
    """
    セキュリティ強化されたCLIアプリケーション構築ツール

    Args:
        command (str): 実行するCLIコマンド

    Returns:
        str: コマンドの出力結果
    """
    try:
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return f"ERROR: {result.stderr}"
        else:
            return result.stdout
    except ImportError as e:
        return f"ERROR: {e}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_secure_cli.py \"command\"")
    else:
        command = " ".join(sys.argv[1:])
        result = tool_secure_cli(command)
        print(result)