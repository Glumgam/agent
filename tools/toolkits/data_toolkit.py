"""
DATA Toolkit
自動生成・統合ツール集。
カテゴリ: data
作成日: 2026-03-21
収録ツール:
- tool_secure_cli_command: Deep Research により獲得。分野: スキル発展
"""
from pathlib import Path


# ==================================================
# tool_secure_cli_command
# ==================================================

def tool_secure_cli_command(command):
    try:
        # Generate a key and instantiate a Fernet instance
        key = Fernet.generate_key()
        fernet = Fernet(key)

        # Encrypt the command
        encrypted_command = fernet.encrypt(command.encode())

        return json.dumps({'encrypted_command': encrypted_command.decode(), 'key': key.decode()})
    except Exception as e:
        return "ERROR: " + str(e)

if __name__ == "__main__":
    print(tool_secure_cli_command("ls -la"))
