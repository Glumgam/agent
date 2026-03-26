"""
SYSTEM Toolkit
自動生成・統合ツール集。
カテゴリ: system
作成日: 2026-03-22
収録ツール:
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
