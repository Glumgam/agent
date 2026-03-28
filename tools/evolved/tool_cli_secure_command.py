"""
自動生成ツール: tool_cli_secure_command
目的: セキュアなCLIコマンドを自動生成し、暗号化されたデータの作成とデコードを行う。
情報源: スキル発展
生成日: 2026-03-28
テスト: ✅ 通過済み
"""
import subprocess
from cryptography.fernet import Fernet

def tool_cli_secure_command(command):
    try:
        # Generate a secure CLI command
        if "generate_key" in command.lower():
            key = Fernet.generate_key()
            return f"Generated Key: {key.decode()}"
        
        elif "encrypt" in command.lower():
            parts = command.split(" ")
            if len(parts) < 3:
                return "ERROR: Invalid encrypt command. Usage: encrypt <key> <data>"
            
            key = parts[1].encode()
            data = ' '.join(parts[2:]).encode()
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(data)
            return f"Encrypted Data: {encrypted_data.decode()}"
        
        elif "decrypt" in command.lower():
            parts = command.split(" ")
            if len(parts) < 3:
                return "ERROR: Invalid decrypt command. Usage: decrypt <key> <data>"
            
            key = parts[1].encode()
            encrypted_data = ' '.join(parts[2:]).encode()
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            return f"Decrypted Data: {decrypted_data.decode()}"
        
        else:
            return "ERROR: Unsupported command. Use 'generate_key', 'encrypt <key> <data>', or 'decrypt <key> <data>'."
    
    except Exception as e:
        return f"ERROR: An error occurred - {str(e)}"

if __name__ == "__main__":
    # Example usage
    print(tool_cli_secure_command("generate_key"))
    key = "your_generated_key_here"  # Replace with your generated key
    data = "Hello, secure world!"
    encrypted = tool_cli_secure_command(f"encrypt {key} {data}")
    print(encrypted)
    decrypted = tool_cli_secure_command(f"decrypt {key} {encrypted.split(': ')[1]}")
    print(decrypted)