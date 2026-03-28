"""
自動生成ツール: tool_cli_encrypt_data
目的: CLIから直接データを暗号化および復号化する機能を提供します。
情報源: スキル発展
生成日: 2026-03-27
テスト: ✅ 通過済み
"""
import os
from cryptography.fernet import Fernet

def tool_cli_encrypt_data(data, key=None):
    try:
        if not key:
            key = Fernet.generate_key()
            cipher_suite = Fernet(key)
        else:
            cipher_suite = Fernet(key.encode())
        
        encrypted_data = cipher_suite.encrypt(data.encode()).decode()
        return f"ENCRYPTED_DATA: {encrypted_data}\nKEY: {key.decode()}"
    except Exception as e:
        return f"ERROR: {str(e)}"

def tool_cli_decrypt_data(encrypted_data, key):
    try:
        cipher_suite = Fernet(key.encode())
        decrypted_data = cipher_suite.decrypt(encrypted_data.encode()).decode()
        return f"DECRYPTED_DATA: {decrypted_data}"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Example usage
    data_to_encrypt = "Hello, World!"
    encrypted_result = tool_cli_encrypt_data(data_to_encrypt)
    print(encrypted_result)

    key_from_encrypted = encrypted_result.split("KEY: ")[1]
    encrypted_data_from_result = encrypted_result.split("ENCRYPTED_DATA: ")[1].split("\nKEY")[0]

    decrypted_result = tool_cli_decrypt_data(encrypted_data_from_result, key_from_encrypted)
    print(decrypted_result)