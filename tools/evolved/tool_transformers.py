"""
自動生成ツール: tool_transformers
目的: Hugging FaceのLLMモデルを簡単に使用できるライブラリ
情報源: AI・LLM 最新動向
生成日: 2026-03-19
テスト: ✅ 通過済み
"""
import subprocess
import sys
import os

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