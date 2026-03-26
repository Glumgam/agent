"""
自動生成ツール: tool_cli_encrypt_decrypt
目的: CLIで暗号化と復号化を行う。
情報源: スキル発展
生成日: 2026-03-26
テスト: ✅ 通過済み
"""
import base64
from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

def encrypt_message(key, message):
    f = Fernet(key)
    encrypted = f.encrypt(message.encode())
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_message(key, token):
    try:
        decoded_token = base64.urlsafe_b64decode(token)
        f = Fernet(key)
        decrypted = f.decrypt(decoded_token).decode()
        return decrypted
    except Exception as e:
        return "ERROR: Decryption failed"

def tool_cli_encrypt_decrypt(action, key=None, message=None, token=None):
    if action == "generate_key":
        return generate_key().decode()
    elif action == "encrypt" and key and message:
        return encrypt_message(key.encode(), message)
    elif action == "decrypt" and key and token:
        return decrypt_message(key.encode(), token)
    else:
        return "ERROR: Invalid arguments"

if __name__ == "__main__":
    # 例1: キー生成
    print(tool_cli_encrypt_decrypt("generate_key"))
    
    # 例2: 暗号化
    key = tool_cli_encrypt_decrypt("generate_key")
    message = "Hello, World!"
    encrypted_message = tool_cli_encrypt_decrypt("encrypt", key=key, message=message)
    print(f"Encrypted: {encrypted_message}")
    
    # 例3: 復号化
    decrypted_message = tool_cli_encrypt_decrypt("decrypt", key=key, token=encrypted_message)
    print(f"Decrypted: {decrypted_message}")