"""
WEB Toolkit
自動生成・統合ツール集。
カテゴリ: web
作成日: 2026-03-18
収録ツール:
- tool_httpx_request: 非同期HTTPクライアント (同期ラッパー)
- tool_httpx: 非同期HTTPクライアント (同期ラッパー)
"""
import asyncio
import json
from pathlib import Path
from typing import Optional


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
    非同期HTTPクライアントを使用したリクエスト送信 (同期インターフェース)

    Args:
        method: HTTPメソッド (GET, POST, PUT, DELETE, etc.)
        url: リクエストURL
        params: クエリパラメータ (JSON文字列)
        headers: HTTPヘッダー (JSON文字列)
        data: リクエストボディ (form data)
        json_data: リクエストボディ (JSON文字列)
        timeout: タイムアウト秒数 (文字列)

    Returns:
        str: レスポンスステータスとボディの文字列
    """
    try:
        import httpx
    except ImportError:
        return "ERROR: httpxライブラリがインストールされていません。pip install httpx を実行してください。"

    async def _request() -> str:
        # 引数のパース
        try:
            params_dict = json.loads(params) if params else None
            headers_dict = json.loads(headers) if headers else None
            json_payload = json.loads(json_data) if json_data else None
        except json.JSONDecodeError:
            params_dict = headers_dict = json_payload = None

        timeout_val = float(timeout) if timeout else 30.0

        async with httpx.AsyncClient(timeout=timeout_val) as client:
            request_kwargs: dict = {"params": params_dict}
            if headers_dict:
                request_kwargs["headers"] = headers_dict
            if data:
                request_kwargs["data"] = data
            if json_payload:
                request_kwargs["json"] = json_payload

            response = await client.request(method.upper(), url, **request_kwargs)

            response_text = response.text
            result = {
                "status_code": response.status_code,
                "url": str(response.url),
                "body": response_text[:1000] if response_text else "",
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        return asyncio.run(_request())
    except httpx.RequestError as e:
        return f"ERROR: リクエストエラー：{str(e)}"
    except httpx.HTTPStatusError as e:
        return f"ERROR: HTTPエラー：{e.response.status_code}"
    except Exception as e:
        return f"ERROR: {type(e).__name__} - {str(e)}"


# ==================================================
# tool_httpx_request
# ==================================================

def tool_httpx_request(url: str, method: str = "GET") -> str:
    """
    非同期 HTTP リクエストを送信するツール関数 (同期ラッパー)。

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

    async def _request() -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(method, url)
            if response.status_code >= 400:
                return f"ERROR: HTTP Error {response.status_code} - {response.text[:100]}"
            return f"Status: {response.status_code}, Content Length: {len(response.text)}"

    try:
        return asyncio.run(_request())
    except httpx.HTTPError as e:
        return f"ERROR: HTTP Error - {str(e)}"
    except Exception as e:
        return f"ERROR: {str(e)}"


if __name__ == "__main__":
    result = tool_httpx_request("https://httpbin.org/get")
    print(result)
