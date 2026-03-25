# Pythonで並列処理を実装する3つのメソッド

## はじめに
Pythonで並列処理を実装するメソッドはいくつかありますが、ここでは最も基本的な3つのメソッドについて解説します。これらのメソッドは、異なるシナリオや状況に応じて選択できます。

## 基本的な使い方

### 1. `threading` モジュールを使用する
Pythonの標準ライブラリである `threading` モジュールを使って並列処理を行うメソッドです。以下は、簡単なコード例です：

```python
import threading

def print_numbers():
    for i in range(5):
        print(i)

def print_letters():
    for letter in 'abcde':
        print(letter)

# スレッドの作成
thread1 = threading.Thread(target=print_numbers)
thread2 = threading.Thread(target=print_letters)

# スレッドの開始
thread1.start()
thread2.start()

# スレッドの終了を待つ
thread1.join()
thread2.join()
```

このコードは、数字とアルファベットを同時に表示します。`threading.Thread` を使用して新しいスレッドを作成し、`start()` メソッドでスレッドを開始します。

### 2. `multiprocessing` モジュールを使用する
並列処理を行うもう一つのメソッドは `multiprocessing` モジュールを使用することです。以下はそのコード例です：

```python
import multiprocessing

def print_numbers():
    for i in range(5):
        print(i)

def print_letters():
    for letter in 'abcde':
        print(letter)

# プロセスの作成
process1 = multiprocessing.Process(target=print_numbers)
process2 = multiprocessing.Process(target=print_letters)

# プロセスの開始
process1.start()
process2.start()

# プロセスの終了を待つ
process1.join()
process2.join()
```

このコードも、数字とアルファベットを同時に表示しますが、`multiprocessing.Process` を使用して新しいプロセスを作成しています。

### 3. `concurrent.futures` モジュールを使用する
Pythonの標準ライブラリである `concurrent.futures` モジュールは、並列処理をより簡単に管理できるように設計されています。以下はそのコード例です：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def print_numbers():
    for i in range(5):
        print(i)

def print_letters():
    for letter in 'abcde':
        print(letter)

# スレッドプールの作成
with ThreadPoolExecutor(max_workers=2) as executor:
    # タスクの.submit() でタスクをスケジューリング
    future1 = executor.submit(print_numbers)
    future2 = executor.submit(print_letters)

    # 結果の取得（順不同）
    for future in as_completed([future1, future2]):
        print(future.result())
```

このコードは、`ThreadPoolExecutor` を使用してスレッドプールを作成し、タスクをスケジューリングしています。

## 実践例

並列処理の実用的な例として、複数のファイルの内容を同時に読み込むと仮定します。以下はそのコード例です：

```python
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

# ファイルパスのリスト
file_paths = ['file1.txt', 'file2.txt', 'file3.txt']

# スレッドプールの作成
with ThreadPoolExecutor(max_workers=3) as executor:
    # タスクの.submit() でタスクをスケジューリング
    futures = {executor.submit(read_file, path): path for path in file_paths}

    # 結果の取得（順不同）
    for future in as_completed(futures):
        file_path = futures[future]
        content = future.result()
        print(f"Content of {file_path}:")
        print(content)
```

このコードは、複数のファイルを同時に読み込みます。`ThreadPoolExecutor` を使用してスレッドプールを作成し、各ファイルの内容を読み込むタスクをスケジューリングしています。

## まとめ

- `threading` モジュールを使用すると、簡単にスレッドを作成できます。
- `multiprocessing` モジュールを使用すると、プロセスベースの並列処理が可能です。
- `concurrent.futures` モジュールは、タスク管理をより楽にしてくれます。

これらのメソッドは、初心者でも理解しやすいですが、深い応用や最適化については「詳細記事（はてなブログ）」に誘導することをお勧めします。
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
