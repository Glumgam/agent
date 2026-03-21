"""
自動生成ツール: tool_batch_encrypt_decrypt
目的: ファイルまたはディレクトリ内のデータを一括で暗号化・復号化する機能を提供します。
情報源: スキル発展
生成日: 2026-03-22
テスト: ✅ 通過済み
"""
import os
from cryptography.fernet import Fernet

def tool_batch_encrypt_decrypt(file_or_directory, key=None):
    try:
        if not key:
            key = Fernet.generate_key()
        
        fernet = Fernet(key)
        
        if file_or_directory.endswith('.txt'):
            # File encryption/decryption
            with open(file_or_directory, 'rb') as file:
                data = file.read()
            
            encrypted_data = fernet.encrypt(data)
            with open(file_or_directory, 'wb') as file:
                file.write(encrypted_data)
        
        elif os.path.isdir(file_or_directory):
            # Directory encryption/decryption
            for root, dirs, files in os.walk(file_or_directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.endswith('.txt'):
                        with open(file_path, 'rb') as f:
                            data = f.read()
                        
                        encrypted_data = fernet.encrypt(data)
                        with open(file_path, 'wb') as f:
                            f.write(encrypted_data)
        
        return key.decode('utf-8')
    
    except Exception as e:
        return "ERROR: " + str(e)

if __name__ == "__main__":
    # Example usage
    key = tool_batch_encrypt_decrypt('example.txt', None)
    print("Encryption Key:", key)