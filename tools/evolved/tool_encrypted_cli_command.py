"""
自動生成ツール: tool_encrypted_cli_command
目的: CLIアプリケーションを構築し、そのコマンド入出力を暗号化する。
情報源: スキル発展
生成日: 2026-03-27
テスト: ✅ 通過済み
"""
import subprocess
from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

def encrypt_message(message, key):
    f = Fernet(key)
    encrypted_message = f.encrypt(message.encode())
    return encrypted_message.decode()

def decrypt_message(encrypted_message, key):
    f = Fernet(key)
    decrypted_message = f.decrypt(encrypted_message.encode()).decode()
    return decrypted_message

def tool_encrypted_cli_command(command):
    try:
        # Generate a new encryption key
        key = generate_key()
        
        # Execute the CLI command
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        
        # Encrypt the output of the command
        encrypted_output = encrypt_message(result.stdout, key)
        
        return f"Key: {key.decode()}, Encrypted Output: {encrypted_output}"
    except subprocess.CalledProcessError as e:
        return f"ERROR: Command execution failed with error: {e.stderr}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    # Example usage
    command = "echo Hello, World!"
    encrypted_result = tool_encrypted_cli_command(command)
    print(encrypted_result)