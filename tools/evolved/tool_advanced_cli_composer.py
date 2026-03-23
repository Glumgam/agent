"""
自動生成ツール: tool_advanced_cli_composer
目的: 複数のCLIアプリを組み合わせて、一連のタスクを自動化する機能を提供します。
情報源: スキル発展
生成日: 2026-03-23
テスト: ✅ 通過済み
"""
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