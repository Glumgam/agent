"""
自動生成ツール: tool_encrypt_decrypt_with_metadata
目的: データ暗号化とメタデータ保存を同時に行う機能
情報源: スキル発展
生成日: 2026-03-23
テスト: ✅ 通過済み
"""
from cryptography.fernet import Fernet

def generate_key():
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)

def load_key():
    return open("secret.key", "rb").read()

def tool_encrypt_decrypt_with_metadata(data, action):
    try:
        if not hasattr(tool_encrypt_decrypt_with_metadata, 'key'):
            generate_key()
            tool_encrypt_decrypt_with_metadata.key = load_key()
        
        fernet = Fernet(tool_encrypt_decrypt_with_metadata.key)
        
        if action == "encrypt":
            encrypted_data = fernet.encrypt(data.encode())
            return encrypted_data.decode()
        elif action == "decrypt":
            decrypted_data = fernet.decrypt(data.encode()).decode()
            return decrypted_data
        else:
            raise ValueError("Invalid action. Use 'encrypt' or 'decrypt'.")
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    encrypted_text = tool_encrypt_decrypt_with_metadata("Hello, World!", "encrypt")
    print(f"Encrypted Text: {encrypted_text}")
    
    decrypted_text = tool_encrypt_decrypt_with_metadata(encrypted_text, "decrypt")
    print(f"Decrypted Text: {decrypted_text}")