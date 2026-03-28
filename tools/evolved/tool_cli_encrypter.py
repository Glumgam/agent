"""
自動生成ツール: tool_cli_encrypter
目的: CLIアプリケーションを構築し、ユーザー入力データを暗号化する機能を提供します。
情報源: スキル発展
生成日: 2026-03-27
テスト: ✅ 通過済み
"""
from cryptography.fernet import Fernet

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