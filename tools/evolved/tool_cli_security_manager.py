"""
自動生成ツール: tool_cli_security_manager
目的: CLIアプリケーションでセキュアな暗号化とデクリプション機能を提供するマネージャー
情報源: スキル発展
生成日: 2026-03-28
テスト: ✅ 通過済み
"""
import os
from cryptography.fernet import Fernet

def generate_key():
    """
    Generate a new encryption key and save it to 'secret.key'
    """
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)
    return key.decode()

def load_key():
    """
    Load the encryption key from 'secret.key'
    """
    if os.path.exists("secret.key"):
        with open("secret.key", "rb") as key_file:
            return key_file.read()
    else:
        return None

def encrypt_message(message: str):
    """
    Encrypt a message using the Fernet symmetric encryption
    """
    try:
        key = load_key()
        if key is None:
            key = generate_key()
            print("Generated new key and saved to 'secret.key'")
        fernet = Fernet(key)
        encrypted = fernet.encrypt(message.encode())
        return encrypted.decode()
    except Exception as e:
        return f"ERROR: {str(e)}"

def decrypt_message(encrypted_message: str):
    """
    Decrypt a message using the Fernet symmetric encryption
    """
    try:
        key = load_key()
        if key is None:
            return "ERROR: No encryption key found"
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_message.encode())
        return decrypted.decode()
    except Exception as e:
        return f"ERROR: {str(e)}"

def tool_cli_security_manager(action: str, message: str):
    """
    CLI security manager for encrypting and decrypting messages
    action: 'encrypt' or 'decrypt'
    message: the text to be encrypted or decrypted
    """
    if action == "encrypt":
        return encrypt_message(message)
    elif action == "decrypt":
        return decrypt_message(message)
    else:
        return "ERROR: Invalid action. Use 'encrypt' or 'decrypt'."

if __name__ == "__main__":
    # Example usage
    print("Encrypting message:")
    encrypted = tool_cli_security_manager("encrypt", "Hello, World!")
    print(f"Encrypted message: {encrypted}")

    print("\nDecrypting message:")
    decrypted = tool_cli_security_manager("decrypt", encrypted)
    print(f"Decrypted message: {decrypted}")