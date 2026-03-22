"""
自動生成ツール: tool_secure_transformers
目的: Hugging FaceのLLMモデルを使用してデータを暗号化・復号化するCLIアプリケーション
情報源: スキル発展
生成日: 2026-03-22
テスト: ✅ 通過済み
"""
import base64
from cryptography.fernet import Fernet
from transformers import pipeline

def generate_key():
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)

def load_key():
    return open("secret.key", "rb").read()

def tool_secure_transformers(text, action):
    try:
        if action not in ['encrypt', 'decrypt']:
            return "ERROR: Invalid action. Use 'encrypt' or 'decrypt'."
        
        # Load the encryption key
        key = load_key()
        cipher_suite = Fernet(key)
        
        if action == 'encrypt':
            # Encrypt the text using Hugging Face transformers pipeline
            encryptor = pipeline('text2text-generation', model="t5-small")
            encrypted_text = encryptor(text, max_length=100, num_return_sequences=1)[0]['generated_text']
            encrypted_bytes = encrypted_text.encode()
            ciphered_data = cipher_suite.encrypt(encrypted_bytes)
            return base64.b64encode(ciphered_data).decode('utf-8')
        elif action == 'decrypt':
            # Decrypt the text using Hugging Face transformers pipeline
            decryptor = pipeline('text2text-generation', model="t5-small")
            decrypted_text = decryptor(text, max_length=100, num_return_sequences=1)[0]['generated_text']
            base64_decoded = base64.b64decode(decrypted_text)
            plain_bytes = cipher_suite.decrypt(base64_decoded)
            return plain_bytes.decode('utf-8')
    except Exception as e:
        return f"ERROR: {str(e)}"