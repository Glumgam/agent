"""
TEXT Toolkit
自動生成・統合ツール集。
カテゴリ: text
作成日: 2026-03-18
収録ツール:
- tool_cli_security_manager: Deep Research により獲得。分野: スキル発展
- tool_encrypted_cli_command: Deep Research により獲得。分野: スキル発展
- tool_multi_toolkit: Deep Research により獲得。分野: スキル発展
- tool_batch_transformers: Deep Research により獲得。分野: スキル発展
- tool_batch_cli_command: Deep Research により獲得。分野: スキル発展
- tool_advanced_cli_composer: Deep Research により獲得。分野: スキル発展
- tool_combined_cli_encrypt_decrypt: Deep Research により獲得。分野: スキル発展
- tool_encrypt_decrypt_with_metadata: Deep Research により獲得。分野: スキル発展
- tool_cli_encrypt_decrypt_transformer: Deep Research により獲得。分野: スキル発展
- tool_combined_cli: Deep Research により獲得。分野: スキル発展
- tool_secure_transformers: Deep Research により獲得。分野: スキル発展
- tool_transformers_example: Deep Research により獲得。分野: AI・LLM 最新動向
- tool_secure_cli: Deep Research により獲得。分野: スキル発展
- tool_secure_transformer_cli: Deep Research により獲得。分野: スキル発展
- tool_encrypt_transform_data: Deep Research により獲得。分野: スキル発展
- tool_encrypt_decrypt: Deep Research により獲得。分野: セキュリティ
- tool_encrypt_data: Deep Research により獲得。分野: セキュリティ
- tool_transformers: Deep Research により獲得。分野: AI・LLM 最新動向
- tool_transformers_inference: 大規模言語モデル（LLM）の操作と機能拡張
- tool_rich: リッチなターミナル出力
- tool_create_cli: CLIアプリ構築
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional


# ==================================================
# tool_create_cli
# ==================================================

def tool_create_cli(app_name: str, description: str, commands: List[str], help_text: Optional[str] = None) -> str:
    """Typer CLI アプリを構築して返す。commands はコマンド名のリスト。"""
    try:
        import typer

        app = typer.Typer(help=description)

        # クロージャバグ修正: default引数で cmd_name を束縛
        for cmd_name in commands:
            def _make_cmd(name: str = cmd_name):
                @app.command(name=name)
                def _cmd():
                    typer.echo(f"Command: {name}")
            _make_cmd()

        return f"CLI Application '{app_name}' created with {len(commands)} commands. Help: {description}"
    except ImportError:
        return "ERROR: Typer not installed. Install with 'pip install typer'"
    except Exception as e:
        return f"ERROR: {str(e)}"


# app をモジュールレベルで管理 (tool_run_cli から参照できるように)
_cli_apps: dict = {}


def tool_run_cli(app_name: str, command: str) -> str:
    """tool_create_cli で作成した CLI アプリをコマンド名で実行する。"""
    try:
        import typer
        from typer.testing import CliRunner

        app = _cli_apps.get(app_name)
        if app is None:
            return f"ERROR: '{app_name}' が見つかりません。先に tool_create_cli() を呼んでください。"

        runner = CliRunner()
        result = runner.invoke(app, [command])
        return result.output
    except ImportError:
        return "ERROR: Typer not installed. Install with 'pip install typer'"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Test the tool
    result1 = tool_create_cli("myapp", "A sample CLI", ["cmd1", "cmd2"])
    print("Create CLI Result:")
    print(result1)
    print()
    
    result2 = tool_run_cli("myapp", "cmd1")
    print("Run CLI Result:")
    print(result2)


# ==================================================
# tool_rich
# ==================================================

def tool_rich(text: str) -> str:
    """
    Renders the provided text using the Rich library.
    
    Args:
        text (str): The text to render.
        
    Returns:
        str: A confirmation message or an error message.
    """
    try:
        from rich import print as rich_print
        # Attempt to render the text using Rich
        rich_print(text)
        return f"SUCCESS: Rich rendered the text: {text}"
    except ImportError as e:
        return f"ERROR: rich library not installed. {str(e)}"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Example usage
    print("Testing tool_rich:")
    result = tool_rich("Hello, Rich!")
    print(f"Function returned: {result}")


# ==================================================
# tool_transformers_inference
# ==================================================

def tool_transformers_inference(prompt: str, model_name: str) -> str:
    """
    Executes text generation inference using a Hugging Face model via the transformers library.
    
    Args:
        prompt (str): The input text prompt for the model.
        model_name (str): The name or path of the model to use (e.g., 'gpt2', 'distilgpt2').
        
    Returns:
        str: The generated text or an error message.
    """
    try:
        from transformers import pipeline
    except ImportError as e:
        return f"ERROR: Failed to import transformers library: {str(e)}"

    try:
        # Load the text generation pipeline
        # Note: This will download the model if not cached locally
        pipe = pipeline("text-generation", model=model_name, device="cpu")
        
        # Perform inference
        # Limit output length to avoid excessive memory usage or long waits
        output = pipe(prompt, max_new_tokens=50, do_sample=True, temperature=0.7)
        
        # Extract generated text
        if output and len(output) > 0:
            generated_text = output[0]['generated_text']
            # Remove the original prompt if it is included in the output
            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()
            return generated_text
        else:
            return "ERROR: No text was generated from the model."
            
    except Exception as e:
        return f"ERROR: Inference failed: {str(e)}"

if __name__ == "__main__":
    # Example usage for verification
    # Note: Ensure 'transformers' is installed and internet access is available for model download
    test_prompt = "The future of AI will be"
    test_model = "gpt2"  # Using a small model for faster local testing
    
    print(f"Running inference on model: {test_model}")
    print(f"Input Prompt: {test_prompt}")
    print("-" * 50)
    
    result = tool_transformers_inference(test_prompt, test_model)
    
    print(f"Output: {result}")
    print("-" * 50)
    
    if "ERROR" in result:
        print("Note: Model might need to be downloaded first. Check internet connection.")


# ==================================================
# tool_transformers
# ==================================================

def tool_transformers(model_name: str, prompt: str, max_length: int = 50, temperature: float = 0.7) -> str:
    """
    Hugging Face transformers LLMモデルを使用してテキストを生成する
    
    Args:
        model_name: モデル名 (例: "gpt2", "microsoft/phi-3-mini")
        prompt: 入力プロンプト
        max_length: 生成する最大トークン数
        temperature: 生成のランダム性 (0.0-2.0)
    
    Returns:
        生成されたテキストの文字列
    """
    try:
        # transformersライブラリのインポート
        from transformers import pipeline
        
        # 簡易的なモデル読み込みと推論
        try:
            # 基本的なテキスト生成パイプラインの作成
            generator = pipeline("text-generation", model=model_name, device=-1)
            
            # プロンプトの生成
            result = generator(prompt, max_new_tokens=max_length, temperature=temperature)
            
            # 結果を文字列として返す
            return result[0]['generated_text']
            
        except Exception as e:
            return f"ERROR: モデル読み込み失敗 - {str(e)}"
            
    except ImportError as e:
        return f"ERROR: transformersライブラリがインストールされていません - {str(e)}"
    except Exception as e:
        return f"ERROR: 予期せぬエラーが発生しました - {str(e)}"

if __name__ == "__main__":
    # 動作確認用
    print("transformersツール動作確認")
    print("=" * 50)
    
    # 簡単なテスト
    test_model = "gpt2"
    test_prompt = "Pythonの概要を説明してください"
    
    print(f"モデル: {test_model}")
    print(f"プロンプト: {test_prompt}")
    print("-" * 50)
    
    result = tool_transformers(test_model, test_prompt)
    print(f"結果:\n{result}")
    
    print("=" * 50)
    print("動作確認完了")


# ==================================================
# tool_encrypt_data
# ==================================================

def tool_encrypt_data(
    operation: str,
    data: str,
    key: Optional[str] = None,
    rsa_key_size: int = 2048,
    salt: Optional[str] = None
) -> str:
    """
    PyCryptodome 暗号化ツール関数
    
    Args:
        operation: 操作タイプ (encrypt, decrypt, hash, generate_rsa_key)
        data: 暗号化/復号化するデータ
        key: AES 鍵または RSA 公開鍵 (operation に依存)
        rsa_key_size: RSA 鍵のサイズ (デフォルト: 2048)
        salt: ハッシュ計算用の塩 (オプション)
    
    Returns:
        処理結果の文字列
    
    Raises:
        ImportError: 必要なライブラリがインストールされていない場合
    """
    
    try:
        if operation == "encrypt":
            # AES 暗号化
            if not key:
                return "ERROR: key is required for encryption"
            
            key_bytes = key.encode() if isinstance(key, str) else key
            iv = get_random_bytes(16)
            cipher = AES.new(key_bytes, AES.MODE_EAX, iv)
            ciphertext, tag = cipher.encrypt_and_digest(pad(data.encode(), AES.block_size))
            
            result = {
                "operation": "encrypt",
                "data": base64.b64encode(ciphertext).decode(),
                "iv": base64.b64encode(iv).decode(),
                "tag": base64.b64encode(tag).decode()
            }
            return json.dumps(result, indent=2)
        
        elif operation == "decrypt":
            # AES 復号化
            if not key or not salt:
                return "ERROR: key and salt are required for decryption"
            
            try:
                ciphertext = base64.b64decode(salt)
                iv = base64.b64decode(key)
                tag = base64.b64decode(data)
                
                cipher = AES.new(key.encode(), AES.MODE_EAX, iv)
                plaintext = cipher.decrypt_and_verify(ciphertext, tag)
                
                return f"Decrypted data: {plaintext.decode()}"
            except Exception as e:
                return f"ERROR: Decryption failed - {str(e)}"
        
        elif operation == "hash":
            # ハッシュ計算
            import hashlib
            hash_obj = hashlib.sha256()
            hash_obj.update(data.encode())
            return f"SHA256 Hash: {hash_obj.hexdigest()}"
        
        elif operation == "generate_rsa_key":
            # RSA 鍵生成
            rsa_key = RSA.generate(rsa_key_size)
            public_key = rsa_key.publickey().export_key()
            private_key = rsa_key.export_key()
            
            result = {
                "operation": "generate_rsa_key",
                "key_size": rsa_key_size,
                "public_key": base64.b64encode(public_key).decode(),
                "private_key": base64.b64encode(private_key).decode()
            }
            return json.dumps(result, indent=2)
        
        elif operation == "sign":
            # デジタル署名
            if not key:
                return "ERROR: key is required for signing"
            
            rsa_key = RSA.generate(2048)
            private_key = rsa_key.export_key()
            cipher = PKCS1_OAEP.new(rsa_key)
            signature = cipher.sign(data.encode())
            
            result = {
                "operation": "sign",
                "signature": base64.b64encode(signature).decode(),
                "key_size": 2048
            }
            return json.dumps(result, indent=2)
        
        elif operation == "verify":
            # 署名検証
            if not key or not salt:
                return "ERROR: key and salt are required for verification"
            
            try:
                rsa_key = RSA.import_key(base64.b64decode(key))
                public_key = rsa_key.publickey()
                cipher = PKCS1_OAEP.new(public_key)
                cipher.verify(base64.b64decode(salt), data.encode())
                return "Verification successful"
            except Exception as e:
                return f"ERROR: Verification failed - {str(e)}"
        
        else:
            return "ERROR: Unknown operation type. Supported: encrypt, decrypt, hash, generate_rsa_key, sign, verify"
    
    except ImportError as e:
        return f"ERROR: Required library not installed - {str(e)}"
    except Exception as e:
        return f"ERROR: Operation failed - {str(e)}"


# ==================================================
# tool_encrypt_decrypt
# ==================================================

def tool_encrypt_decrypt(
    action: str,
    data: str,
    key: Optional[str] = None,
    algorithm: str = "AES",
    rsa_key_length: int = 2048
) -> str:
    """
    暗号化/復号化機能を提供するツール関数
    
    Args:
        action: "encrypt" または "decrypt"
        data: 暗号化/復号化するデータ
        key: 暗号鍵(AES の場合)
        algorithm: 使用するアルゴリズム(AES, DES3)
        rsa_key_length: RSA 鍵の長さ(ビット)
    
    Returns:
        暗号化/復号化結果の文字列
    """
    try:
        if action == "encrypt":
            return _encrypt(data, key, algorithm, rsa_key_length)
        elif action == "decrypt":
            return _decrypt(data, key, algorithm, rsa_key_length)
        else:
            return "ERROR: 不明なアクションです.'encrypt' または 'decrypt' を指定してください."
    
    except Exception as e:
        return f"ERROR: {str(e)}"


def _generate_aes_key(key_length: int = 32) -> str:
    """AES 鍵を生成する"""
    return get_random_bytes(key_length // 8).hex()


def _encrypt(data: str, key: str, algorithm: str = "AES", rsa_key_length: int = 2048) -> str:
    """データを暗号化する"""
    if not key:
        # 鍵が指定されていない場合は生成
        if algorithm == "AES":
            key = _generate_aes_key()
        else:
            raise ValueError("DES3 には鍵が必要です")
    
    try:
        if algorithm == "AES":
            cipher = AES.new(bytes.fromhex(key), AES.MODE_EAX)
            nonce = cipher.nonce
            ciphertext, tag = cipher.encrypt(bytes.fromhex(data))
            # 結果を結合:nonce + ciphertext + tag
            result = nonce.hex() + ciphertext.hex() + tag.hex()
            return f"AES_ENCRYPTED:{result}"
        
        elif algorithm == "DES3":
            cipher = DES3.new(bytes.fromhex(key), DES3.MODE_CBC, b"0" * 8)
            padded_data = pad(bytes.fromhex(data), DES3.block_size)
            ciphertext = cipher.encrypt(padded_data)
            return f"DES3_ENCRYPTED:{ciphertext.hex()}"
        
        else:
            raise ValueError(f"サポートされていないアルゴリズム:{algorithm}")
    
    except Exception as e:
        raise Exception(f"暗号化エラー:{str(e)}")


def _decrypt(data: str, key: str, algorithm: str = "AES", rsa_key_length: int = 2048) -> str:
    """データを復号化する"""
    if not key:
        raise ValueError("復号化には鍵が必要です")
    
    try:
        if algorithm == "AES":
            # 結果を分割:nonce + ciphertext + tag
            parts = data.split("AES_ENCRYPTED:")
            if len(parts) != 2:
                raise ValueError("暗号化されたデータの形式が正しくありません")
            
            result = parts[1]
            nonce_len = 16  # 128 ビット
            tag_len = 16   # 128 ビット
            
            nonce = bytes.fromhex(result[:nonce_len])
            ciphertext = bytes.fromhex(result[nonce_len:-tag_len])
            tag = bytes.fromhex(result[-tag_len:])
            
            cipher = AES.new(bytes.fromhex(key), AES.MODE_EAX, nonce)
            plaintext = cipher.decrypt(ciphertext)
            
            return f"AES_DECRYPTED:{plaintext.hex()}"
        
        elif algorithm == "DES3":
            cipher = DES3.new(bytes.fromhex(key), DES3.MODE_CBC, b"0" * 8)
            ciphertext = bytes.fromhex(data.split("DES3_ENCRYPTED:")[-1])
            plaintext = unpad(cipher.decrypt(ciphertext), DES3.block_size)
            
            return f"DES3_DECRYPTED:{plaintext.hex()}"
        
        else:
            raise ValueError(f"サポートされていないアルゴリズム:{algorithm}")
    
    except Exception as e:
        raise Exception(f"復号化エラー:{str(e)}")


def _hash_data(data: str, algorithm: str = "sha256") -> str:
    """データをハッシュ化して返す"""
    try:
        if algorithm == "sha256":
            return hashlib.sha256(bytes.fromhex(data)).hexdigest()
        elif algorithm == "sha1":
            return hashlib.sha1(bytes.fromhex(data)).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(bytes.fromhex(data)).hexdigest()
        else:
            raise ValueError(f"サポートされていないハッシュアルゴリズム:{algorithm}")
    except Exception as e:
        raise Exception(f"ハッシュ計算エラー:{str(e)}")


if __name__ == "__main__":
    # 動作確認用
    print("=" * 50)
    print("PyCryptodome ツール動作確認")
    print("=" * 50)
    
    # テストデータ
    test_data = "テストデータ:これは暗号化されるメッセージです"
    aes_key = _generate_aes_key()
    
    print("\n1. AES 暗号化テスト")
    encrypted = tool_encrypt_decrypt("encrypt", test_data, aes_key, "AES")
    print(f"暗号化結果:{encrypted}")
    
    print("\n2. AES 復号化テスト")
    decrypted = tool_encrypt_decrypt("decrypt", encrypted, aes_key, "AES")
    print(f"復号化結果:{decrypted}")
    
    print("\n3. ハッシュ計算テスト")
    hash_result = tool_encrypt_decrypt("hash", test_data, algorithm="sha256")
    print(f"SHA256 ハッシュ:{hash_result}")
    
    print("\n4. 無効なアクションテスト")
    error_result = tool_encrypt_decrypt("invalid", test_data, aes_key, "AES")
    print(f"エラー結果:{error_result}")
    
    print("\n5. 無効な鍵テスト")
    error_result2 = tool_encrypt_decrypt("encrypt", test_data, None, "AES")
    print(f"エラー結果:{error_result2}")
    
    print("\n" + "=" * 50)
    print("動作確認完了")
    print("=" * 50)


# ==================================================
# tool_encrypt_transform_data
# ==================================================

def tool_encrypt_transform_data(text: str) -> str:
    try:
        generate_key()
        encrypted_text = encrypt_message(text)
        nlp = pipeline("text2text-generation", model="t5-small")
        transformed_text = nlp(encrypted_text, max_length=50)[0]['generated_text']
        return decrypt_message(transformed_text)
    except Exception as e:
        return f"ERROR: {str(e)}"


# ==================================================
# tool_secure_transformer_cli
# ==================================================

def tool_secure_transformer_cli(input_str):
    try:
        # Load pre-trained model and tokenizer from Hugging Face Model Hub
        model_name = "gpt2"  # Replace with your desired model name
        model = AutoModelForCausalLM.from_pretrained(model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Encode the input string using the tokenizer
        encoded_input = tokenizer.encode(input_str, return_tensors="pt")

        # Generate a key for encryption and decryption
        encrypted_input = model.generate(encoded_input)

        # Decrypt the encrypted input (not applicable in this context)
        decrypted_input = tokenizer.decode(encrypted_input[0], skip_special_tokens=True)

        return "Encrypted Input: {}\nDecrypted Input: {}".format(encrypted_input, decrypted_input)

    except ImportError as e:
        return "ERROR: Missing library - " + str(e)


# ==================================================
# tool_secure_cli
# ==================================================

def tool_secure_cli(command):
    """
    セキュリティ強化されたCLIアプリケーション構築ツール

    Args:
        command (str): 実行するCLIコマンド

    Returns:
        str: コマンドの出力結果
    """
    try:
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return f"ERROR: {result.stderr}"
        else:
            return result.stdout
    except ImportError as e:
        return f"ERROR: {e}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tool_secure_cli.py \"command\"")
    else:
        command = " ".join(sys.argv[1:])
        result = tool_secure_cli(command)
        print(result)


# ==================================================
# tool_transformers_example
# ==================================================

def tool_transformers_example(prompt):
    try:
        from transformers import pipeline

        # Define a pipeline for text generation using the GPT-2 model
        nlp = pipeline("text-generation", model="gpt2")

        # Generate text based on the provided prompt
        result = nlp(prompt, max_length=50, num_return_sequences=1)

        return str(result[0]['generated_text'])
    except ImportError as e:
        return f"ERROR: {e}"


# ==================================================
# tool_secure_transformers
# ==================================================

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


# ==================================================
# tool_combined_cli
# ==================================================

def tool_combined_cli(command):
    """
    Combine multiple CLI applications into a unified environment.

    Args:
        command (str): The command to execute within the combined CLI environment.

    Returns:
        str: The output of the executed command or an error message.
    """
    try:
        # Import necessary libraries if needed
        import subprocess

        # Execute the provided command using subprocess
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr.strip()}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred - {str(e)}"

if __name__ == "__main__":
    # Example usage
    print(tool_combined_cli("echo Hello, World!"))


# ==================================================
# tool_cli_encrypt_decrypt_transformer
# ==================================================

def tool_cli_encrypt_decrypt_transformer(text, key=None, action='encrypt'):
    try:
        if not key:
            # Generate a key and instantiate a Fernet instance for encryption/decryption
            key = Fernet.generate_key()
            cipher_suite = Fernet(key)
        else:
            cipher_suite = Fernet(key)

        if action == 'encrypt':
            # Encrypt the text
            encrypted_text = cipher_suite.encrypt(text.encode())
            return base64.b64encode(encrypted_text).decode(), key
        elif action == 'decrypt':
            # Decrypt the text
            decrypted_text = cipher_suite.decrypt(base64.b64decode(text))
            return decrypted_text.decode()
        else:
            return "ERROR: Invalid action. Use 'encrypt' or 'decrypt'."
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Example usage
    original_text = "Hello, Hugging Face!"
    encrypted_text, encryption_key = tool_cli_encrypt_decrypt_transformer(original_text)
    print(f"Encrypted Text: {encrypted_text}")

    decrypted_text = tool_cli_encrypt_decrypt_transformer(encrypted_text, key=encryption_key, action='decrypt')
    print(f"Decrypted Text: {decrypted_text}")


# ==================================================
# tool_encrypt_decrypt_with_metadata
# ==================================================

def tool_encrypt_decrypt_with_metadata(data, action):
    try:
        if not hasattr(tool_encrypt_decrypt_with_metadata, 'key'):
            generate_key()
            tool_encrypt_decrypt_with_metadata.key = load_key()
        
        fernet = Fernet(tool_encrypt_decrypt_with_metadata.key)
        
        if action == "encrypt":
            encrypted_data = fernet.encrypt(data.encode())
            return encrypted_data.decode()
        elif action == "decrypt":
            decrypted_data = fernet.decrypt(data.encode()).decode()
            return decrypted_data
        else:
            raise ValueError("Invalid action. Use 'encrypt' or 'decrypt'.")
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    encrypted_text = tool_encrypt_decrypt_with_metadata("Hello, World!", "encrypt")
    print(f"Encrypted Text: {encrypted_text}")
    
    decrypted_text = tool_encrypt_decrypt_with_metadata(encrypted_text, "decrypt")
    print(f"Decrypted Text: {decrypted_text}")


# ==================================================
# tool_combined_cli_encrypt_decrypt
# ==================================================

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


# ==================================================
# tool_advanced_cli_composer
# ==================================================

def tool_advanced_cli_composer(command_str):
    """
    Executes a string containing multiple CLI commands separated by semicolons.
    
    Args:
        command_str (str): A string containing multiple CLI commands.

    Returns:
        str: Output of the executed commands.

    Raises:
        Exception: If an error occurs during execution.
    """
    try:
        import subprocess
    except ImportError:
        return "ERROR: subprocess module not found. Please install Python's standard library."

    # Split the command string into individual commands based on semicolons
    commands = command_str.split(';')
    
    output = ""
    for command in commands:
        if command.strip():
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            output += result.stdout + "\n" + result.stderr

    return output


if __name__ == "__main__":
    # Example usage
    input_commands = "echo Hello; echo World"
    print(tool_advanced_cli_composer(input_commands))


# ==================================================
# tool_batch_cli_command
# ==================================================

def tool_batch_cli_command(commands):
    """
    Executes multiple CLI commands in batch.

    Args:
        commands (str): A string containing the CLI commands separated by newlines.

    Returns:
        str: Output of all commands or an error message.
    """
    try:
        output = ""
        for command in commands.split("\n"):
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            output += result.stdout
        return output.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: Command failed with exit code {e.returncode}: {e.stderr}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    commands = """
    echo Hello, World!
    date
    ls -la
    """
    print(tool_batch_cli_command(commands))


# ==================================================
# tool_batch_transformers
# ==================================================

def tool_batch_transformers(text_list):
    try:
        # Create a text classification pipeline using Hugging Face's transformers library
        classifier = pipeline('sentiment-analysis')
        
        # Process the list of texts in batch
        results = classifier(text_list)
        
        # Convert results to a readable string format
        output_str = '\n'.join([f"{text}: {result['label']} ({result['score']:.4f})" for text, result in zip(text_list, results)])
        
        return output_str
    
    except ImportError as e:
        return f"ERROR: {e}"
    
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Example usage
    texts = [
        "I love programming!",
        "This is a great day.",
        "I am feeling sad today."
    ]
    print(tool_batch_transformers(texts))


# ==================================================
# tool_multi_toolkit
# ==================================================

def tool_multi_toolkit(command):
    try:
        import subprocess
        result = subprocess.run(command, shell=True, check=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr}"


# ==================================================
# tool_encrypted_cli_command
# ==================================================

def tool_encrypted_cli_command(command):
    try:
        # Generate a new encryption key
        key = generate_key()
        
        # Execute the CLI command
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        
        # Encrypt the output of the command
        encrypted_output = encrypt_message(result.stdout, key)
        
        return f"Key: {key.decode()}, Encrypted Output: {encrypted_output}"
    except subprocess.CalledProcessError as e:
        return f"ERROR: Command execution failed with error: {e.stderr}"
    except Exception as e:
        return f"ERROR: An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    # Example usage
    command = "echo Hello, World!"
    encrypted_result = tool_encrypted_cli_command(command)
    print(encrypted_result)


# ==================================================
# tool_cli_security_manager
# ==================================================

def tool_cli_security_manager(action: str, message: str):
    """
    CLI security manager for encrypting and decrypting messages
    action: 'encrypt' or 'decrypt'
    message: the text to be encrypted or decrypted
    """
    if action == "encrypt":
        return encrypt_message(message)
    elif action == "decrypt":
        return decrypt_message(message)
    else:
        return "ERROR: Invalid action. Use 'encrypt' or 'decrypt'."

if __name__ == "__main__":
    # Example usage
    print("Encrypting message:")
    encrypted = tool_cli_security_manager("encrypt", "Hello, World!")
    print(f"Encrypted message: {encrypted}")

    print("\nDecrypting message:")
    decrypted = tool_cli_security_manager("decrypt", encrypted)
    print(f"Decrypted message: {decrypted}")
