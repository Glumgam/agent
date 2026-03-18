"""
WEB Toolkit
自動生成・統合ツール集。
カテゴリ: web
作成日: 2026-03-18
収録ツール:
- tool_httpx_request: 非同期HTTPクライアント
- tool_httpx: 非同期HTTPクライアント
"""
from pathlib import Path


# ==================================================
# tool_httpx
# ==================================================

def tool_httpx(
    method: str = "GET",
    url: str = "",
    params: Optional[str] = None,
    headers: Optional[str] = None,
    data: Optional[str] = None,
    json_data: Optional[str] = None,
    timeout: Optional[str] = None
) -> str:
    """
    非同期HTTPクライアントを使用したリクエスト送信
    
    Args:
        method: HTTPメソッド (GET, POST, PUT, DELETE, etc.)
        url: リクエストURL
        params: クエリパラメータ (文字列としてJSON形式)
        headers: HTTPヘッダー (文字列としてJSON形式)
        data: リクエストボディ (form data形式)
        json_data: リクエストボディ (JSON形式)
        timeout: タイムアウト時間 (秒)
    
    Returns:
        str: レスポンスステータスとボディの文字列
    """
    try:
        # 外部ライブラリのインポート
        from httpx import AsyncClient, Timeout, HTTPStatusError, RequestError
        
        # 引数のパース
        try:
            params_dict = json.loads(params) if params else None
            headers_dict = json.loads(headers) if headers else None
            json_payload = json.loads(json_data) if json_data else None
        except json.JSONDecodeError:
            params_dict = None
            headers_dict = None
            json_payload = None
        
        # タイムアウト設定
        timeout_obj = Timeout.from_config(timeout=timeout) if timeout else None
        
        # クライアントの作成
        async with AsyncClient(timeout=timeout_obj) as client:
            # リクエストの作成
            request_kwargs = {"params": params_dict}
            if headers_dict:
                request_kwargs["headers"] = headers_dict
            if data:
                request_kwargs["data"] = data
            if json_payload:
                request_kwargs["json"] = json_payload
            
            # メソッド名の正規化
            method_upper = method.upper()
            
            # リクエストの実行
            response = await client.request(method_upper, url, **request_kwargs)
            
            # レスポンスの構築
            response_text = response.text
            response_json = response.json() if response.headers.get("content-type", "").startswith("application/json") else None
            
            # 結果の文字列化
            result = {
                "status_code": response.status_code,
                "status_message": response.reason_phrase,
                "url": str(response.url),
                "headers": dict(response.headers),
                "body": response_text[:1000] if response_text else ""  # 最大1000文字
            }
            
            if response_json:
                result["body_json"] = response_json
            
            # JSONを文字列に変換して返す
            return json.dumps(result, ensure_ascii=False, indent=2)
            
    except ImportError:
        return "ERROR: httpxライブラリがインストールされていません。pip install httpxを実行してください。"
    except RequestError as e:
        return f"ERROR: リクエストエラーが発生しました：{str(e)}"
    except HTTPStatusError as e:
        return f"ERROR: HTTPエラーが発生しました：{e.status_code} {e.response.reason_phrase}"
    except TimeoutException:
        return "ERROR: タイムアウトが発生しました。"
    except Exception as e:
        return f"ERROR: 予期せぬエラーが発生しました：{type(e).__name__} - {str(e)}"
    except KeyboardInterrupt:
        return "ERROR: ユーザーが操作を中断しました。"
    except Exception as e:
        return f"ERROR: 不明なエラーが発生しました：{type(e).__name__} - {str(e)}"


async def main():
    """動作確認用のメイン関数"""
    print("=" * 60)
    print("HTTPXツール動作確認")
    print("=" * 60)
    
    # 動作確認用のテストケース
    test_cases = [
        {
            "name": "GET リクエスト (GitHub)",
            "method": "GET",
            "url": "https://api.github.com/repos/tiangolo/fastapi",
        },
        {
            "name": "GET リクエスト (クエリパラメータ)",
            "method": "GET",
            "url": "https://jsonplaceholder.typicode.com/posts/1",
            "params": '{"limit": 10, "offset": 0}',
        },
        {
            "name": "POST リクエスト",
            "method": "POST",
            "url": "https://httpbin.org/post",
            "data": '{"name": "test", "value": 123}',
        },
        {
            "name": "エラーテスト (404)",
            "method": "GET",
            "url": "https://httpbin.org/status/404",
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}] テストケース：{test['name']}")
        print("-" * 60)
        
        try:
            result = await tool_httpx(
                method=test.get("method", "GET"),
                url=test.get("url", ""),
                params=test.get("params"),
                data=test.get("data"),
                json_data=test.get("json_data"),
                headers=test.get("headers")
            )
            print(result)
        except Exception as e:
            print(f"ERROR: {str(e)}")
    
    print("\n" + "=" * 60)
    print("動作確認完了")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())


# ==================================================
# tool_httpx_request
# ==================================================

def tool_httpx_request(url: str, method: str = "GET") -> str:
    """
    非同期 HTTP リクエストを送信するツール関数。
    httpx ライブラリを使用して、指定された URL へのリクエストを送信します。
    
    Args:
        url (str): リクエストを送信する URL
        method (str): HTTP メソッド（GET, POST, PUT, DELETE など）
    
    Returns:
        str: レスポンスのステータスコードと概要、またはエラーメッセージ
    """
    try:
        import httpx
    except ImportError:
        return "ERROR: httpx library is not installed. Please run: pip install httpx"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(method, url)
            
            if response.status_code >= 400:
                return f"ERROR: HTTP Error {response.status_code} - {response.text[:100]}"
            
            return f"Status: {response.status_code}, Content Length: {len(response.text)}"
    except httpx.HTTPError as e:
        return f"ERROR: HTTP Error - {str(e)}"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    # テスト実行
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(tool_httpx_request("https://httpbin.org/get"))
        print(result)
        loop.close()
    except Exception as e:
        print(f"ERROR: {e}")
