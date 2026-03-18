"""
TEXT Toolkit
自動生成・統合ツール集。
カテゴリ: text
作成日: 2026-03-18
収録ツール:
- tool_transformers_inference: 大規模言語モデル（LLM）の操作と機能拡張
- tool_rich: リッチなターミナル出力
- tool_create_cli: CLIアプリ構築
"""
from pathlib import Path


# ==================================================
# tool_create_cli
# ==================================================

def tool_create_cli(app_name: str, description: str, commands: List[str], help_text: Optional[str] = None) -> str:
    try:
        import typer
        from typing import List, Optional
        
        # Create a basic CLI application using Typer
        app = typer.Typer(help=description)
        
        # Add commands to the CLI
        for cmd_name in commands:
            @app.command()
            def command():
                typer.echo(f"Command: {cmd_name}")
        
        # Return the created CLI app structure
        return f"CLI Application '{app_name}' created with {len(commands)} commands. Help: {description}"
    except ImportError as e:
        return f"ERROR: Typer not installed. Install with 'pip install typer'"
    except Exception as e:
        return f"ERROR: {str(e)}"

def tool_run_cli(app_name: str, command: str) -> str:
    try:
        import typer
        from typer.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(app, [command])
        return result.output
    except ImportError as e:
        return f"ERROR: Typer not installed. Install with 'pip install typer'"
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
