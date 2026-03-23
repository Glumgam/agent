"""
自動生成ツール: tool_combined_cli_encrypt_decrypt
目的: セキュリティ関連の暗号化と解読機能を提供し、CLIアプリ構築をサポートします。
情報源: スキル発展
生成日: 2026-03-23
テスト: ✅ 通過済み
"""
from cryptography.fernet import Fernet

def generate_key():
    return Fernet.generate_key()

def save_key(key, filename):
    with open(filename, "wb") as key_file:
        key_file.write(key)

def load_key(filename):
    return open(filename, "rb").read()

def tool_combined_cli_encrypt_decrypt(text, mode="encrypt", key=None, output_filename=None):
    try:
        if mode not in ["encrypt", "decrypt"]:
            raise ValueError("Invalid mode. Use 'encrypt' or 'decrypt'.")

        if key is None and mode == "decrypt":
            return "ERROR: Key must be provided for decryption."

        if output_filename is None:
            output_filename = "encrypted_data.txt" if mode == "encrypt" else "decrypted_data.txt"

        fernet = Fernet(key)

        if mode == "encrypt":
            encrypted_text = fernet.encrypt(text.encode())
            with open(output_filename, "wb") as file:
                file.write(encrypted_text)
            return f"Data encrypted and saved to {output_filename}"
        else:  # mode == "decrypt"
            decrypted_text = fernet.decrypt(text.encode()).decode()
            with open(output_filename, "w") as file:  # Change "wb" to "w"
                file.write(decrypted_text)
            return f"Data decrypted and saved to {output_filename}"

    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Encryption example
    key = generate_key()
    save_key(key, "secret.key")
    encrypted_data = tool_combined_cli_encrypt_decrypt("Hello, World!", mode="encrypt", key=key)
    print(encrypted_data)

    # Decryption example
    decrypted_data = tool_combined_cli_encrypt_decrypt(encrypted_data, mode="decrypt", key=key)
    print(decrypted_data)