# Pythonのloggingモジュール実践入門

## はじめに

Pythonの`logging`モジュールは、デバッグやエラーログなどの記録に非常に有効です。これにより、プログラムの動作状況を追跡し、問題解決に役立ちます。この記事では、`logging`モジュールの基本的な使い方から応用テクニックまで、実践的なガイドラインを提供します。

## 基本的な使い方

`logging`モジュールは非常にシンプルで直感的です。以下のコード例で基本的な使い方を示します。

```python
import logging

# ログレベルの設定
logging.basicConfig(level=logging.DEBUG)

# 各レベルのログを出力
logging.debug('これはDEBUGレベルのログ')
logging.info('これはINFOレベルのログ')
logging.warning('これはWARNINGレベルのログ')
logging.error('これはERRORレベルのログ')
logging.critical('これはCRITICALレベルのログ')
```

このコードでは、`basicConfig`関数でログレベルを設定し、それぞれのレベルでログを出力します。`DEBUG`レベルは最も詳細な情報から始まり、`CRITICAL`レベルは最も重大な問題に達します。

## 実践例

実際のプロジェクトでは、ファイルへのロギングやロガーの階層化がよく使われます。以下は、ファイルへのログ出力の例です。

```python
import logging

# ロガーの設定
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

# ハンドラの設定
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)

# フォーマッタの設定
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# ロガーにハンドラを追加
logger.addHandler(file_handler)

# ログを出力
logger.debug('これはDEBUGレベルのログ')
```

この例では、`FileHandler`を使用してログをファイルに出力します。また、フォーマッタを使用してログの形式を指定することができます。

## 応用テクニック

実務でよく使われる応用テクニックとして、ロガーの階層化とフィルターを挙げます。

### ロガーの階層化

ロガーは階層的です。親ロガーと子ロガーがあります。子ロガーは親ロガーの設定に継承しますが、独自の設定もできます。

```python
import logging

# 親ロガーの設定
parent_logger = logging.getLogger('parent')
parent_logger.setLevel(logging.DEBUG)

# 子ロガーの設定
child_logger = logging.getLogger('parent.child')
child_logger.setLevel(logging.ERROR)

# ハンドラとフォーマッタの設定（親ロガー用）
file_handler_parent = logging.FileHandler('parent.log')
formatter_parent = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler_parent.setFormatter(formatter_parent)
parent_logger.addHandler(file_handler_parent)

# ハンドラとフォーマッタの設定（子ロガー用）
file_handler_child = logging.FileHandler('child.log')
formatter_child = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler_child.setFormatter(formatter_child)
child_logger.addHandler(file_handler_child)

# ログを出力
parent_logger.debug('これはDEBUGレベルのログ（親ロガー）')
child_logger.error('これはERRORレベルのログ（子ロガー）')
```

### フィルター

フィルターを使用すると、特定の条件に合致するログのみを出力できます。

```python
import logging

class MyFilter(logging.Filter):
    def filter(self, record):
        return 'important' in record.getMessage()

# ロガーの設定
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

# ハンドラとフォーマッタの設定
file_handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# フィルターを追加
logger.addFilter(MyFilter())

# ログを出力
logger.debug('これはDEBUGレベルのログ')
logger.error('important: このエラーメッセージは重要です')
```

この例では、`MyFilter`クラスでフィルターを作成し、特定の文字列が含まれている場合のみを出力します。

## いつ使うべきか（使い分けガイド）

以下の観点で使い分けを表形式で示します。

| ユースケース | 使用するメソッド |
| --- | --- |
| 小規模なアプリケーションでのデバッグ | 基本的な`logging`モジュールを使用 |
| 中規模以上のアプリケーションでのデバッグ | ファイルへのロギングと階層化を適用 |
| 特定の条件に合致するログのみを出力したい | フィルターを使用 |

## まとめ

- `logging`モジュールは、プログラムの動作状況を追跡し、問題解決に役立ちます。
- 基本的な使い方から応用テクニックまで、実践的なガイドラインを提供します。
- ロガーの階層化とフィルターを使用して、より高度なログ管理が可能になります。

## FAQ

Q: `logging`モジュールで何種類のレベルがありますか？

A: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`の5種類のレベルがあります。

Q: ファイルへのロギングはどのように行いますか？

A: `FileHandler`を使用してログをファイルに出力します。フォーマッタでログの形式を指定できます。

Q: インスタンス化が必要なオブジェクトは何ですか？

A: `Logger`, `Formatter`, `FileHandler`などがインスタンス化が必要なオブジェクトです。

Q: ロガーの階層化とは何ですか？

A: 親ロガーと子ロガーがあります。親ロガーの設定に継承しますが、独自の設定もできます。

Q: フィルターはどのように使用しますか？

A: `Filter`クラスを作成し、特定の条件に合致するログのみを出力できます。
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
