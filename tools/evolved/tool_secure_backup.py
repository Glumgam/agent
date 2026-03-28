"""
自動生成ツール: tool_secure_backup
目的: セキュアなバックアップファイル作成と復元機能を提供
情報源: スキル発展
生成日: 2026-03-28
テスト: ✅ 通過済み
"""
import os
from cryptography.fernet import Fernet

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