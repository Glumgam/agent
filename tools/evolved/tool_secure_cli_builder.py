"""
自動生成ツール: tool_secure_cli_builder
目的: セキュアなCLIアプリケーションを構築し、ユーザー入力データを暗号化する。
情報源: スキル発展
生成日: 2026-03-26
テスト: ✅ 通過済み
"""
import os
from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

def save_key(key, key_path='secret.key'):
    with open(key_path, 'wb') as key_file:
        key_file.write(key)

def load_key(key_path='secret.key'):
    if not os.path.exists(key_path):
        return None
    with open(key_path, 'rb') as key_file:
        return key_file.read()

def encrypt_message(message, key):
    fernet = Fernet(key)
    encrypted_message = fernet.encrypt(message.encode())
    return encrypted_message.decode()

def decrypt_message(encrypted_message, key):
    fernet = Fernet(key)
    decrypted_message = fernet.decrypt(encrypted_message.encode()).decode()
    return decrypted_message

def tool_secure_cli_builder(user_input):
    try:
        key = load_key()
        if not key:
            key = generate_key()
            save_key(key)

        encrypted_input = encrypt_message(user_input, key)
        return f"Encrypted: {encrypted_input}"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    try:
        user_input = input("Enter your message to encrypt: ")
        result = tool_secure_cli_builder(user_input)
        print(result)
    except EOFError:
        print("No input provided.")