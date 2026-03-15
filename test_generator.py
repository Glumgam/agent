from llm import ask


def generate_test(file_name, code):

    prompt = f"""
次のPythonコードのpytestテストを書いてください。

ファイル:
{file_name}

コード:
{code}

pytest形式で出力してください。
"""

    return ask(prompt)
