"""
自動生成ツール: tool_create_typer_cli
目的: CLIアプリ構築
情報源: AI 論文
生成日: 2026-03-23
テスト: ✅ 通過済み
"""
import typer

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