"""
自動生成ツール: tool_fetch_arxiv_papers
目的: AI agents running research on single-GPU nanochat training automatically
情報源: Python 技術トレンド
生成日: 2026-03-23
テスト: ✅ 通過済み
"""
import requests

def tool_fetch_arxiv_papers(query):
    url = f"https://arxiv.org/api/query?search_query={query}&start=0&max_results=3"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        else:
            return "ERROR: Failed to fetch papers from arXiv API"
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    print(tool_fetch_arxiv_papers("AI agent research"))