"""
自動生成ツール: tool_secure_cli_command
目的: 安全なCLIアプリケーションを構築するためのツール
情報源: スキル発展
生成日: 2026-03-21
テスト: ✅ 通過済み
"""
import json
from cryptography.fernet import Fernet

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