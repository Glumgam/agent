"""
自動生成ツール: tool_cli_encrypt
目的: CLIから直接データを暗号化・復号化できるツール
情報源: スキル発展
生成日: 2026-03-28
テスト: ✅ 通過済み
"""
import base64

from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

def encrypt_data(key, data):
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted_data).decode()

def decrypt_data(key, encrypted_data):
    try:
        fernet = Fernet(key)
        decoded_data = base64.urlsafe_b64decode(encrypted_data)
        decrypted_data = fernet.decrypt(decoded_data).decode()
        return decrypted_data
    except Exception as e:
        return "ERROR: Decryption failed"

def tool_cli_encrypt(command, data):
    if command == 'generate_key':
        return generate_key().decode()
    elif command == 'encrypt':
        key, *data_to_encrypt = data.split(',')
        return encrypt_data(key.encode(), ','.join(data_to_encrypt))
    elif command == 'decrypt':
        key, encrypted_data = data.split(',')
        return decrypt_data(key.encode(), encrypted_data)
    else:
        return "ERROR: Invalid command"

if __name__ == "__main__":
    # Example usage
    print("Generating a new encryption key:")
    key = tool_cli_encrypt('generate_key', '')
    print(f"Key: {key}")

    print("\nEncrypting data 'Hello, World!' with the generated key:")
    encrypted_data = tool_cli_encrypt('encrypt', f"{key},Hello, World!")
    print(f"Encrypted Data: {encrypted_data}")

    print("\nDecrypting the encrypted data:")
    decrypted_data = tool_cli_encrypt('decrypt', f"{key},{encrypted_data}")
    print(f"Decrypted Data: {decrypted_data}")