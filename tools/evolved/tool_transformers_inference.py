"""
自動生成ツール: tool_transformers_inference
目的: 大規模言語モデル（LLM）の操作と機能拡張
情報源: AI 論文
生成日: 2026-03-18
テスト: ✅ 通過済み
"""
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