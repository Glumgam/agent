# Pythonのpathlib完全活用ガイド

## はじめに（このライブラリ/技術とは）

Pythonの`pathlib`モジュールは、ファイルシステムパスを扱うためのオブジェクト指向的なAPIを提供します。これにより、ファイルやディレクトリの操作がより直感的で、かつPythonicに書けます。

## 基本的な使い方

以下は、`pathlib`を使用して基本的なファイル操作を行うメソッドです。

```python
from pathlib import Path

# パスを表すオブジェクトを作成
file_path = Path('example.txt')

# ファイルが存在するか確認
if file_path.exists():
    print(f"{file_path} は存在します。")
else:
    print(f"{file_path} は存在しません。")

# ディレクトリ作成
dir_path = Path('new_directory')
if not dir_path.exists():
    dir_path.mkdir()
    print(f"{dir_path} を作成しました。")
```

## 実践例

以下は、`pathlib`を使用してディレクトリ内のファイルを一覧表示し、特定の拡張子を持つファイルを抽出するメソッドです。

```python
from pathlib import Path

# ディレクトリパス
directory_path = Path('.')

# ディレクトリ内の一覧表示
for item in directory_path.iterdir():
    print(item)

# 拡張子 '.txt' のファイルを抽出
txt_files = [file for file in directory_path.glob('*.txt')]
print(f"TXT ファイル: {txt_files}")
```

## まとめ

- `pathlib`はPythonでファイルシステム操作を行うための強力なツールです。
- 簡単に直感的なコードでファイルやディレクトリを操作できます。
- 深い応用については、詳細記事（はてなブログ）をご覧ください。

このガイドを通じて、`pathlib`の基本的な使用メソッドを理解し始めることができます。より高度な機能や実践例については、詳細な説明が含まれた記事を参照してください。
---
## 🛠️ この記事で紹介した環境・ツール
| ツール | 用途 | 入手先 |
|--------|------|--------|
| Python | プログラミング言語 | python.org |
| VS Code | コードエディタ | code.visualstudio.com |
| Ollama | ローカルLLM実行 | ollama.ai |

## 📚 関連記事
- Pythonで始めるAI開発
- ローカルLLMの活用法
- 自動化スクリプトの作り方

---
*この記事はAIエージェントによって自動生成されました。*
*誤りや改善点があればコメントでお知らせください。*
