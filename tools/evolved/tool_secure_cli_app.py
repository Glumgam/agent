"""
自動生成ツール: tool_secure_cli_app
目的: CLIアプリケーションをセキュアかつ効率的に構築し、暗号化機能を統合する
情報源: スキル発展
生成日: 2026-03-25
テスト: ✅ 通過済み
"""
import sys

def tool_secure_cli_app(command: str) -> str:
    try:
        from cryptography.fernet import Fernet
        
        if command == "generate_key":
            key = Fernet.generate_key()
            return f"Generated Key: {key.decode()}"
        
        elif command.startswith("encrypt "):
            _, message = command.split(" ", 1)
            key = Fernet.generate_key()
            cipher_suite = Fernet(key)
            encrypted_message = cipher_suite.encrypt(message.encode())
            return f"Encrypted Message: {encrypted_message.decode()}, Key: {key.decode()}"
        
        elif command.startswith("decrypt "):
            _, encrypted_message_with_key = command.split(" ", 1)
            try:
                encrypted_message, key = encrypted_message_with_key.rsplit(", Key: ", 1)
                cipher_suite = Fernet(key.encode())
                decrypted_message = cipher_suite.decrypt(encrypted_message.encode()).decode()
                return f"Decrypted Message: {decrypted_message}"
            except Exception as e:
                return f"ERROR: Decryption failed - {str(e)}"
        
        else:
            return "ERROR: Invalid command. Use 'generate_key', 'encrypt <message>', or 'decrypt <encrypted_message>, Key: <key>'."
    
    except ImportError:
        return "ERROR: cryptography library is not installed. Please run 'pip install cryptography'."

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py '<command>'")
    else:
        command = sys.argv[1]
        result = tool_secure_cli_app(command)
        print(result)