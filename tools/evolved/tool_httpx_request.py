"""
自動生成ツール: tool_httpx_request
目的: 非同期HTTPクライアント
情報源: Python 技術トレンド
生成日: 2026-03-17
テスト: ✅ 通過済み
"""
import asyncio

async def tool_httpx_request(url: str, method: str = "GET") -> str:
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