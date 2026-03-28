# Pythonで毎日の作業を自動化するスクリプト

## はじめに（このライブラリ/技術とは）

Pythonは非常に柔軟で機能豊富なプログラミング言語であり、多くのライブラリとフレームワークが利用可能です。その中でも、特定のライブラリを使うことで毎日の作業を自動化することができます。今回は、Pythonで作業を自動化するためのいくつかのメソッドを紹介します。

## 基本的な使い方

まずは最も簡単なスクリプトから始めましょう。以下に、ファイル名の一覧を取得し、その中から特定の拡張子を持つファイルのみをリストアップするPythonスクリプトを作成します。

```python
import os

def list_files_with_extension(directory, extension):
    files = []
    for filename in os.listdir(directory):
        if filename.endswith(extension):
            files.append(filename)
    return files

# 使用例
directory_path = '/path/to/your/directory'
extension_to_find = '.txt'
found_files = list_files_with_extension(directory_path, extension_to_find)
print(f"Found {len(found_files)} files with .{extension_to_find} extension:")
for file in found_files:
    print(file)
```

このスクリプトは指定されたディレクトリ内のファイルを一覧表示し、特定の拡張子を持つファイルのみを選択します。これにより、毎日のファイル管理作業を効率的に行うことができます。

## 実践例

次に、より実用的な例をいくつか紹介します。例えば、メール送信やデータのダウンロードなどもスクリプトで自動化できます。

### メール送信の自動化

Pythonには`smtplib`と`email`ライブラリを使用してメールを送信することができます。以下に、簡単なメール送信スクリプトを作成します。

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(subject, body, to_email):
    from_email = "your_email@example.com"
    password = "your_password"

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.example.com', 587)
    server.starttls()
    server.login(from_email, password)
    text = msg.as_string()
    server.sendmail(from_email, to_email, text)
    server.quit()

# 使用例
subject = "Automated Email"
body = "This is an automated email sent using Python."
to_email = "recipient@example.com"
send_email(subject, body, to_email)
```

このスクリプトは指定した内容でメールを送信します。ただし、実際の使用にはSMTPサーバーの情報を正しく設定し、必要に応じて認証情報を安全に管理する必要があります。

### データダウンロードの自動化

Pythonの`requests`ライブラリを使用してウェブ上のデータをダウンロードすることができます。以下に、指定されたURLからCSVファイルをダウンロードするスクリプトを作成します。

```python
import requests

def download_file(url, local_filename):
    response = requests.get(url)
    with open(local_filename, 'wb') as f:
        f.write(response.content)

# 使用例
url = "https://example.com/data.csv"
local_filename = "downloaded_data.csv"
download_file(url, local_filename)
```

このスクリプトは指定されたURLからCSVファイルをダウンロードし、ローカルに保存します。これにより、定期的に必要とするデータの取得が自動化できます。

## まとめ

Pythonで毎日の作業を自動化するスクリプトを作成することは非常に簡単で効果的です。上記の例では、ファイル一覧表示やメール送信、データダウンロードなど、実用的な機能を示しました。これらはあくまで基本的な例ですが、Pythonの強力なライブラリを利用して、より複雑な作業も自動化することができます。

より詳しい内容については、詳細記事（はてなブログ）をご覧いただくことをお勧めします。
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
