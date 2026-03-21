"""
SYSTEM Toolkit
自動生成・統合ツール集。
カテゴリ: system
作成日: 2026-03-22
収録ツール:
- tool_batch_cli_encrypt_decrypt: Deep Research により獲得。分野: スキル発展
- tool_batch_encrypt_decrypt: Deep Research により獲得。分野: スキル発展
"""
from pathlib import Path


# ==================================================
# tool_batch_encrypt_decrypt
# ==================================================

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


# ==================================================
# tool_batch_cli_encrypt_decrypt
# ==================================================

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
