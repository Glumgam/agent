"""
CLI Toolkit
自動生成・統合ツール集。
カテゴリ: cli
作成日: 2026-03-19
収録ツール:
- tool_cli_secure_command: Deep Research により獲得。分野: スキル発展
- tool_cli_encrypt: Deep Research により獲得。分野: スキル発展
- tool_cli_encrypt_data: Deep Research により獲得。分野: スキル発展
- tool_cli_encrypt_decrypt: Deep Research により獲得。分野: スキル発展
- tool_secure_cli_builder: Deep Research により獲得。分野: スキル発展
- tool_cli_builder: Deep Research により獲得。分野: セキュリティ
- tool_typer_create_cli: Deep Research により獲得。分野: AI 論文
- tool_typer_create_app: Deep Research により獲得。分野: Python 技術トレンド
- tool_create_typer_cli: Deep Research により獲得。分野: AI 論文
- tool_create_cli: Deep Research により獲得。分野: セキュリティ
- tool_create_cli_with_typer: Deep Research により獲得。分野: AI・LLM 最新動向
- tool_create_cli_command: Deep Research により獲得。分野: AI 論文
- tool_typer_cli: Deep Research により獲得。分野: AI・LLM 最新動向
"""
from pathlib import Path


# ==================================================
# tool_typer_cli
# ==================================================

def tool_typer_cli(command: str, args: str, options: str = "") -> str:
    """
    Typer CLIアプリを構築して実行するツール関数.
    タイプヒントを活用したCLIコマンドを動的に生成・実行します.
    
    Args:
        command: コマンド名(例:"hello")
        args: 引数の文字列(例:"--name World --greeting hello")
        options: 追加オプションの文字列
    
    Returns:
        str: CLI実行結果またはエラーメッセージ
    """
    try:
        import typer
    except ImportError:
        return "ERROR: typer package not installed. Run: pip install typer"
    
    try:
        # Typerアプリの初期化
        app = typer.Typer(help="Typer CLIアプリケーション")
        
        # 引数をパース(オプション)
        parsed_args = {}
        if args:
            # 引数文字列を解析
            arg_list = args.split()
            for arg in arg_list:
                if arg.startswith("--"):
                    key, value = arg.split("=", 1) if "=" in arg else (arg.lstrip("-"), "True")
                    parsed_args[key.lstrip("-")] = value
        
        # オプションを追加
        if options:
            for opt in options.split():
                if opt.startswith("--"):
                    key, value = opt.split("=", 1) if "=" in opt else (opt.lstrip("-"), "True")
                    parsed_args[key.lstrip("-")] = value
        
        # コマンド定義
        @app.command()
        def main(name: str = "World", greeting: str = "Hello", verbose: bool = False):
            if verbose:
                print(f"[DEBUG] Verbose mode enabled")
            return f"{greeting}, {name}!"
        
        # Typerのヘルプを表示して結果を取得
        try:
            # コマンド実行(引数付き)
            if args or options:
                # 引数がある場合はシミュレーション実行
                result = f"CLI Command: {command}\nArgs: {args}\nOptions: {options}\nResult: {main(**parsed_args)}"
            else:
                # 引数なしでヘルプ表示
                result = f"CLI Command: {command}\nHelp: {app().get_command('main')} --help"
            return result
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    except Exception as e:
        return f"ERROR: Failed to execute typer CLI. Details: {str(e)}"


# ==================================================
# tool_create_cli_command
# ==================================================

def tool_create_cli_command(command_name: str, description: str, args: str = "") -> str:
    """
    Create a simple CLI command using Typer
    """
    try:
        import typer
    except ImportError:
        return "ERROR: typer library is not installed. Run: pip install typer"
    
    try:
        # Create a basic typer app
        app = typer.Typer()
        
        # Generate CLI code example
        code = f'''import typer

app = typer.Typer()

@app.command()
def {command_name}() -> None:
    """{description}"""
    typer.echo(f"Hello from {command_name}!")
'''
        
        return f"CLI command created successfully!\n\n{code}"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Test the tool
    result = tool_create_cli_command(
        command_name="hello",
        description="A simple hello command",
        args="name"
    )
    print(result)


# ==================================================
# tool_create_cli_with_typer
# ==================================================

def tool_create_cli_with_typer(command_name: str, command_description: str) -> str:
    try:
        app = typer.Typer()

        @app.command(name=command_name)
        def my_command():
            typer.echo(f"Command {command_name} executed with Typer.")

        return app()
    
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    tool_create_cli_with_typer("greet", "A simple greet command")


# ==================================================
# tool_create_cli
# ==================================================

def tool_create_cli():
    try:
        app = typer.Typer()

        @app.command()
        def hello(name: str):
            return f"Hello {name}!"

        if __name__ == "__main__":
            app()

        return "CLI created successfully!"
    except ImportError:
        return "ERROR: Unable to import typer. Please install the package using pip install typer."


# ==================================================
# tool_create_typer_cli
# ==================================================

def tool_create_typer_cli(app_name: str, command_name: str, description: str) -> str:
    try:
        app = typer.Typer()

        @app.command()
        def my_command():
            print(description)

        result = app(name=command_name)
        return f"Created CLI with command '{command_name}' and description '{description}'."
    except ImportError:
        return "ERROR: typer library is not installed. Please install it using 'pip install typer'."

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python script.py <app_name> <command_name> <description>")
    else:
        app_name = sys.argv[1]
        command_name = sys.argv[2]
        description = sys.argv[3]
        result = tool_create_typer_cli(app_name, command_name, description)
        print(result)


# ==================================================
# tool_typer_create_app
# ==================================================

def tool_typer_create_app(name: str, description: str) -> str:
    try:
        @app.command()
        def main():
            typer.echo(f"Hello {name}! This is your CLI app: {description}")

        return "CLI application created successfully!"
    except ImportError:
        return "ERROR: Typer library not found. Please install it using 'pip install typer'."

if __name__ == "__main__":
    tool_typer_create_app("MyApp", "A simple command-line interface application.")


# ==================================================
# tool_typer_create_cli
# ==================================================

def tool_typer_create_cli(command_name: str, description: str) -> str:
    try:
        @app.command(name=command_name, help=description)
        def cli_function():
            typer.echo(f"Running {command_name} command.")
        
        app()
        return f"CLI '{command_name}' created successfully."
    except ImportError:
        return "ERROR: Typer is not installed. Please install it using pip."

if __name__ == "__main__":
    result = tool_typer_create_cli("greet", "A simple CLI to greet someone.")
    print(result)


# ==================================================
# tool_cli_builder
# ==================================================

def tool_cli_builder(command_name: str, description: str) -> str:
    try:
        # Create a simple CLI application using Typer
        @app.command(help=description)
        def command():
            typer.echo(f"Executing {command_name} command.")

        # This is a placeholder to simulate running the CLI command.
        # In a real-world scenario, you would call app() here to run the CLI.
        return f"CLI '{command_name}' created with description: '{description}'."
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Example usage of the tool
    result = tool_cli_builder("greet", "A simple command to greet users.")
    print(result)


# ==================================================
# tool_secure_cli_builder
# ==================================================

def tool_secure_cli_builder(user_input):
    try:
        key = load_key()
        if not key:
            key = generate_key()
            save_key(key)

        encrypted_input = encrypt_message(user_input, key)
        return f"Encrypted: {encrypted_input}"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    try:
        user_input = input("Enter your message to encrypt: ")
        result = tool_secure_cli_builder(user_input)
        print(result)
    except EOFError:
        print("No input provided.")


# ==================================================
# tool_cli_encrypt_decrypt
# ==================================================

def tool_cli_encrypt_decrypt(action, key=None, message=None, token=None):
    if action == "generate_key":
        return generate_key().decode()
    elif action == "encrypt" and key and message:
        return encrypt_message(key.encode(), message)
    elif action == "decrypt" and key and token:
        return decrypt_message(key.encode(), token)
    else:
        return "ERROR: Invalid arguments"

if __name__ == "__main__":
    # 例1: キー生成
    print(tool_cli_encrypt_decrypt("generate_key"))
    
    # 例2: 暗号化
    key = tool_cli_encrypt_decrypt("generate_key")
    message = "Hello, World!"
    encrypted_message = tool_cli_encrypt_decrypt("encrypt", key=key, message=message)
    print(f"Encrypted: {encrypted_message}")
    
    # 例3: 復号化
    decrypted_message = tool_cli_encrypt_decrypt("decrypt", key=key, token=encrypted_message)
    print(f"Decrypted: {decrypted_message}")


# ==================================================
# tool_cli_encrypt_data
# ==================================================

def tool_cli_encrypt_data(data, key=None):
    try:
        if not key:
            key = Fernet.generate_key()
            cipher_suite = Fernet(key)
        else:
            cipher_suite = Fernet(key.encode())
        
        encrypted_data = cipher_suite.encrypt(data.encode()).decode()
        return f"ENCRYPTED_DATA: {encrypted_data}\nKEY: {key.decode()}"
    except Exception as e:
        return f"ERROR: {str(e)}"

def tool_cli_decrypt_data(encrypted_data, key):
    try:
        cipher_suite = Fernet(key.encode())
        decrypted_data = cipher_suite.decrypt(encrypted_data.encode()).decode()
        return f"DECRYPTED_DATA: {decrypted_data}"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # Example usage
    data_to_encrypt = "Hello, World!"
    encrypted_result = tool_cli_encrypt_data(data_to_encrypt)
    print(encrypted_result)

    key_from_encrypted = encrypted_result.split("KEY: ")[1]
    encrypted_data_from_result = encrypted_result.split("ENCRYPTED_DATA: ")[1].split("\nKEY")[0]

    decrypted_result = tool_cli_decrypt_data(encrypted_data_from_result, key_from_encrypted)
    print(decrypted_result)


# ==================================================
# tool_cli_encrypt
# ==================================================

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


# ==================================================
# tool_cli_secure_command
# ==================================================

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
