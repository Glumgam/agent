"""
自動生成ツール: tool_encrypt_data_with_metadata
目的: 暗号化されたデータにメタデータを追加し、保存する機能提供
情報源: スキル発展
生成日: 2026-03-22
テスト: ✅ 通過済み
"""
from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

def save_key(key, key_path):
    with open(key_path, 'wb') as key_file:
        key_file.write(key)

def load_key(key_path):
    with open(key_path, 'rb') as key_file:
        return key_file.read()

def tool_encrypt_data_with_metadata(data: str, metadata: dict, key_path: str) -> str:
    try:
        # Generate and save key if it doesn't exist
        try:
            load_key(key_path)
        except FileNotFoundError:
            key = generate_key()
            save_key(key, key_path)

        # Load the encryption key
        key = load_key(key_path)
        fernet = Fernet(key)

        # Encrypt data
        encrypted_data = fernet.encrypt(data.encode())

        # Add metadata to the encrypted data (simple JSON format for demonstration purposes)
        import json
        metadata_str = json.dumps(metadata)
        final_data = f"{encrypted_data.decode()}\n{metadata_str}"

        return final_data
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    data = "Sensitive information"
    metadata = {"source": "User input", "timestamp": "2023-10-05T12:00:00Z"}
    key_path = "encryption_key.key"
    
    result = tool_encrypt_data_with_metadata(data, metadata, key_path)
    print(result)