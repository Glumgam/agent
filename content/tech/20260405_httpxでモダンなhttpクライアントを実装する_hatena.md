# httpxでモダンなHTTPクライアントを実装する 完全ガイド

> 📝 この記事はZennの概要版の詳細解説です。
> 概要版はこちら → [httpxでモダンなHTTPクライアントを実装する](（Zennで公開中）)

---

この記事は、Pythonで効率的なHTTP通信を行うためのモダンなHTTPクライアントである`httpx`を使用するエンジニア向けです。読み終えると、基本的なGET/POSTリクエストから高度な機能までを実装できるようになります。概要だけ知りたい方は、Zennに同題の記事もあわせてご覧ください。

## この記事でわかること

- `httpx`ライブラリのインストールとセットアップメソッド
- ベース的なGET/POSTリクエストの実装
- セッション管理とパフォーマンス最適化
- 非同期通信の利用法
- トラブルシューティングとFAQ

## 環境準備

まず、`httpx`をインストールします。以下のコマンドを使用してください。

```bash
pip install httpx
```

## 基礎実装

### GETリクエストの実装

以下は、基本的なGETリクエストを行うコードです。

```python
import httpx

response = httpx.get('https://jsonplaceholder.typicode.com/posts/1')
print(response.json())
```

このコードを実行すると、指定されたURLからJSONデータを取得し、コンソールに表示します。

### POSTリクエストの実装

次はPOSTリクエストの例です。`json`パラメータを使用して、JSON形式のデータを送信できます。

```python
import httpx

data = {'title': 'foo', 'body': 'bar', 'userId': 1}
response = httpx.post('https://jsonplaceholder.typicode.com/posts', json=data)
print(response.json())
```

このコードは、指定されたURLにJSONデータをPOST送信し、返答のJSONデータを表示します。

## 応用パターン

### セッション管理

セッションを使用することで、複数のリクエスト間で接続を保持できます。これによりパフォーマンスが向上します。

```python
import httpx

with httpx.Client() as client:
 response1 = client.get('https://jsonplaceholder.typicode.com/posts/1')
 print(response1.json())
 response2 = client.get('https://jsonplaceholder.typicode.com/posts/2')
 print(response2.json())
```

### 非同期通信

`httpx`は非同期通信をサポートしており、`asyncio`と組み合わせて効率的に並列リクエストを行うことができます。

```python
import httpx
import asyncio

async def fetch(url):
 async with httpx.AsyncClient() as client:
 response = await client.get(url)
 return response.json()

async def main():
 urls = ['https://jsonplaceholder.typicode.com/posts/1', 'https://jsonplaceholder.typicode.com/posts/2']
 tasks = [fetch(url) for url in urls]
 results = await asyncio.gather(*tasks)
 for result in results:
 print(result)

asyncio.run(main())
```

このコードは、非同期で複数のURLからデータを取得し、結果を表示します。

## パフォーマンス最適化・ベストプラクティス

- **セッション管理**: 複数のリクエストを行う場合は、セッションを使用して接続を保持します。
- **非同期通信**: 並列処理が必要な場合、非同期通信を利用すると効率が向上します。
- **タイムアウト設定**: タイムアウトを設定することで、無応答のリクエストに対策できます。

## トラブルシューティング

### エラー1: `httpx.ConnectError`

**原因**: 接続エラーが発生した場合。

**対処法**: ネットワーク接続を確認し、正しいURLを使用していることを確認してください。

```python
try:
 response = httpx.get('https://jsonplaceholder.typicode.com/posts/1')
except httpx.ConnectError as e:
 print(f"Connection error: {e}")
```

### エラー2: `httpx.TimeoutException`

**原因**: リクエストがタイムアウトした場合。

**対処法**: タイムアウト時間を調整するか、ネットワークの状態を確認してください。

```python
try:
 response = httpx.get('https://jsonplaceholder.typicode.com/posts/1', timeout=5.0)
except httpx.TimeoutException as e:
 print(f"Timeout error: {e}")
```

### エラー3: `httpx.HTTPStatusError`

**原因**: HTTPステータスコードがエラーレベルの場合。

**対処法**: レスポンスのステータスコードを確認し、適切な処理を行うようにしてください。

```python
try:
 response = httpx.get('https://jsonplaceholder.typicode.com/posts/1')
 response.raise_for_status()
except httpx.HTTPStatusError as e:
 print(f"HTTP error: {e}")
```

## FAQ

### Q1. `httpx`と`requests`の違いは何ですか？

**A**: `httpx`はPython 3.x用のモダンなHTTPクライアントで、非同期通信やセッション管理などの機能が豊富です。一方、`requests`はシンプルで使いやすいが、非同期サポートがないため現代的な開発では`httpx`の方が適していることが多いです。

### Q2. タイムアウト設定をどのようにしますか？

**A**: `timeout`パラメータを使用してタイムアウト時間を指定できます。例：`httpx.get('https://example.com', timeout=5.0)`。

### Q3. 並列リクエストはどのように行いますか？

**A**: `asyncio`と組み合わせて非同期通信を利用すると、効率的に並列リクエストを行うことができます。詳細なコード例は「応用パターン」セクションで紹介しています。

### Q4. セッション管理とは何ですか？

**A**: セッション管理は、複数のリクエスト間で接続を保持することにより、パフォーマンスを向上させます。`httpx.Client()`を使用してセッションを作成します。

## まとめ

この記事では、`httpx`ライブラリを使用したHTTP通信の実装メソッドについて詳しく解説しました。基本的なGET/POSTリクエストから高度な機能まで、様々なパターンを示しました。また、パフォーマンス最適化とトラブルシューティングのポイントも紹介しました。`httpx`は現代の開発で強力なHTTPクライアントであり、効果的な利用を学ぶことで開発効率が大幅に向上します。

実践的な判断基準：

- **非同期通信**が必要な場合は、`httpx`と`asyncio`を組み合わせて使用。
- **複数のリクエスト**を行う場合は、セッション管理を検討。
- **タイムアウト設定**は必須で、適切な値を設定すること。
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
<!-- score:9 variant:hatena generated:2026-04-05 16:11 -->