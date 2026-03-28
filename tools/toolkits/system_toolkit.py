"""
SYSTEM Toolkit
自動生成・統合ツール集。
カテゴリ: system
作成日: 2026-03-22
収録ツール:
- tool_secure_backup: Deep Research により獲得。分野: スキル発展
- tool_cli_encrypter: Deep Research により獲得。分野: スキル発展
- tool_cli_encryptor: Deep Research により獲得。分野: スキル発展
- tool_encrypt_data_with_metadata: Deep Research により獲得。分野: スキル発展
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


# ==================================================
# tool_encrypt_data_with_metadata
# ==================================================

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


# ==================================================
# tool_cli_encryptor
# ==================================================

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


# ==================================================
# tool_cli_encrypter
# ==================================================

def tool_cli_encrypter(input_data):
    try:
        # 既存のキーファイルがあれば読み込む、なければ生成する
        key_file = 'secret.key'
        try:
            with open(key_file, 'rb') as file:
                key = file.read()
        except FileNotFoundError:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as file:
                file.write(key)
        
        # 暗号化オブジェクトを生成
        cipher_suite = Fernet(key)
        
        # ユーザー入力データをバイト型に変換して暗号化
        encrypted_data = cipher_suite.encrypt(input_data.encode('utf-8'))
        
        return encrypted_data.decode('utf-8')
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # 動作確認用の入力データ
    input_data = "Sensitive information"
    result = tool_cli_encrypter(input_data)
    print("Encrypted:", result)


# ==================================================
# tool_secure_backup
# ==================================================

def tool_secure_backup(action, file_path, key=None):
    try:
        if action == "backup":
            if not key:
                return "ERROR: Key is required for backup"
            with open(file_path, 'rb') as file:
                original = file.read()
            fernet = Fernet(key)
            encrypted = fernet.encrypt(original)
            backup_file_path = file_path + ".bak"
            with open(backup_file_path, 'wb') as backup_file:
                backup_file.write(encrypted)
            return f"Backup created successfully: {backup_file_path}"
        
        elif action == "restore":
            if not key:
                return "ERROR: Key is required for restore"
            backup_file_path = file_path + ".bak"
            if not os.path.exists(backup_file_path):
                return "ERROR: Backup file does not exist"
            with open(backup_file_path, 'rb') as backup_file:
                encrypted = backup_file.read()
            fernet = Fernet(key)
            decrypted = fernet.decrypt(encrypted)
            with open(file_path, 'wb') as file:
                file.write(decrypted)
            return "File restored successfully"
        
        else:
            return "ERROR: Invalid action. Use 'backup' or 'restore'"
    
    except FileNotFoundError:
        return "ERROR: File not found"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Example usage
    key = Fernet.generate_key()
    print("Generated Key:", key.decode())
    
    # Backup example
    result = tool_secure_backup("backup", "example.txt", key)
    print(result)
    
    # Restore example
    result = tool_secure_backup("restore", "example.txt", key)
    print(result)
