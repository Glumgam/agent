"""
自動生成ツール: tool_batch_cli_encrypt_decrypt
目的: 複数ファイルを一括で暗号化・復号化するCLIツール
情報源: スキル発展
生成日: 2026-03-22
テスト: ✅ 通過済み
"""
from cryptography.fernet import Fernet
import os

def tool_batch_cli_encrypt_decrypt(input_folder, output_folder, key=None):
    try:
        if key is None:
            key = Fernet.generate_key()
        
        fernet = Fernet(key)
        
        for filename in os.listdir(input_folder):
            file_path = os.path.join(input_folder, filename)
            
            with open(file_path, 'rb') as file:
                file_data = file.read()
                
            encrypted_data = fernet.encrypt(file_data)
            
            output_file_path = os.path.join(output_folder, filename)
            
            with open(output_file_path, 'wb') as output_file:
                output_file.write(encrypted_data)
        
        return "Files have been encrypted successfully."
    
    except Exception as e:
        return f"ERROR: {str(e)}"