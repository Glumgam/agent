"""
自動生成ツール: tool_cli_encryptor
目的: CLIアプリケーションでファイルの暗号化と復号化を簡単に実行できるツール。
情報源: スキル発展
生成日: 2026-03-26
テスト: ✅ 通過済み
"""
import os
from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

def save_key(key, key_filename):
    with open(key_filename, 'wb') as key_file:
        key_file.write(key)

def load_key(key_filename):
    try:
        with open(key_filename, 'rb') as key_file:
            return key_file.read()
    except FileNotFoundError:
        return None

def encrypt_file(file_path, key):
    fernet = Fernet(key)
    try:
        with open(file_path, 'rb') as file:
            original = file.read()
        
        encrypted = fernet.encrypt(original)
        
        with open(file_path, 'wb') as encrypted_file:
            encrypted_file.write(encrypted)
        return "File encrypted successfully."
    except Exception as e:
        return f"ERROR: {str(e)}"

def decrypt_file(file_path, key):
    fernet = Fernet(key)
    try:
        with open(file_path, 'rb') as encrypted_file:
            encrypted = encrypted_file.read()
        
        decrypted = fernet.decrypt(encrypted)
        
        with open(file_path, 'wb') as decrypted_file:
            decrypted_file.write(decrypted)
        return "File decrypted successfully."
    except Exception as e:
        return f"ERROR: {str(e)}"

def tool_cli_encryptor(action, file_path, key_filename):
    if action == 'generate_key':
        key = generate_key()
        save_key(key, key_filename)
        return f"Key generated and saved to {key_filename}."
    
    key = load_key(key_filename)
    if not key:
        return "ERROR: Key file not found."
    
    if action == 'encrypt':
        return encrypt_file(file_path, key)
    elif action == 'decrypt':
        return decrypt_file(file_path, key)
    else:
        return "ERROR: Invalid action. Use 'generate_key', 'encrypt', or 'decrypt'."

if __name__ == "__main__":
    # Example usage:
    print(tool_cli_encryptor('generate_key', '', 'secret.key'))
    print(tool_cli_encryptor('encrypt', 'sample.txt', 'secret.key'))
    print(tool_cli_encryptor('decrypt', 'sample.txt', 'secret.key'))