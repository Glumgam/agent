"""
Web検索ツール。
DuckDuckGo Instant Answer API を使用（無料・APIキー不要）。

使用場面:
- ImportError で pip install するパッケージ名が不明
- エラーメッセージの解決方法を調べる
- ライブラリのAPIを確認する
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# tool_result はエージェントルートにある
sys.path.insert(0, str(Path(__file__).parent.parent))
from tool_result import ToolResult

DDGO_URL = "https://api.duckduckgo.com/"


def tool_web_search(action: dict) -> ToolResult:
    """
    Web検索を実行して結果を返す。
    executor の registry 経由で呼ばれる（action dict を受け取る）。

    action keys:
        query   : 検索クエリ（必須）
        max_results: 返す件数（省略時3）
    """
    query = action.get("query", action.get("command", "")).strip()
    max_results = int(action.get("max_results", 3))

    if not query:
        return ToolResult(ok=False, output="ERROR: 検索クエリが空です")

    try:
        # DuckDuckGo Instant Answer API
        params = urllib.parse.urlencode({
            "q":              query,
            "format":         "json",
            "no_html":        "1",
            "skip_disambig":  "1",
        })
        url = f"{DDGO_URL}?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgentSearch/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = _extract_results(data, max_results)

        # フォールバック: HTMLスクレイピング
        if not results:
            results = _fallback_search(query, max_results)

        if not results:
            return ToolResult(
                ok=True,
                output=f"検索結果なし: '{query}'\n別のキーワードで試してください",
            )

        output = f"検索結果: '{query}'\n\n"
        for i, r in enumerate(results, 1):
            output += f"[{i}] {r['title']}\n{r['snippet']}\n"
            if r.get("url"):
                output += f"URL: {r['url']}\n"
            output += "\n"

        return ToolResult(ok=True, output=output.strip())

    except urllib.error.URLError as e:
        return ToolResult(
            ok=False,
            output=f"ERROR: ネットワークエラー: {e}\nインターネット接続を確認してください",
        )
    except Exception as e:
        return ToolResult(ok=False, output=f"ERROR: 検索失敗: {e}")


# =====================================================
# 内部: 結果抽出
# =====================================================

def _extract_results(data: dict, max_results: int) -> list:
    """DuckDuckGo APIレスポンスから結果を抽出"""
    results = []

    # Abstract（要約）
    if data.get("Abstract"):
        results.append({
            "title":   data.get("Heading", "概要"),
            "snippet": data["Abstract"],
            "url":     data.get("AbstractURL", ""),
        })

    # RelatedTopics
    for topic in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        if isinstance(topic, dict) and topic.get("Text"):
            results.append({
                "title":   topic.get("Text", "")[:60],
                "snippet": topic.get("Text", ""),
                "url":     topic.get("FirstURL", ""),
            })

    return results[:max_results]


def _fallback_search(query: str, max_results: int) -> list:
    """
    DuckDuckGo HTML スクレイピングによるフォールバック。
    API で結果が取れない場合に使用。
    """
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "jp-jp"})
        url = f"https://html.duckduckgo.com/html/?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        titles = re.findall(
            r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL
        )

        results = []
        for title, snippet in zip(titles[:max_results], snippets[:max_results]):
            clean_title   = re.sub(r"<[^>]+>", "", title).strip()
            clean_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            if clean_title and clean_snippet:
                results.append({
                    "title":   clean_title,
                    "snippet": clean_snippet,
                    "url":     "",
                })
        return results

    except Exception:
        return []


# --- NEWS/RANKING START ---
import json as _json
import xml.etree.ElementTree as _ET


def tool_fetch_news(action: dict) -> ToolResult:
    """
    Google News RSS から最新ニュースを取得する（executor registry 用）。
    action keys: query / topic, max_results
    """
    topic       = action.get("query", action.get("topic", "")).strip()
    max_results = int(action.get("max_results", 5))
    return _fetch_news_raw(topic, max_results)


def _fetch_news_raw(topic: str, max_results: int = 5) -> ToolResult:
    """内部: Google News RSS からニュース取得（位置引数版）"""
    if not topic:
        return ToolResult(ok=False, output="ERROR: トピックが空です")

    try:
        query = urllib.parse.quote(topic)
        url   = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
        req   = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()

        root  = _ET.fromstring(content)
        items = root.findall(".//item")

        results = []
        for item in items[:max_results]:
            title   = item.findtext("title",       "")
            link    = item.findtext("link",        "")
            pubdate = item.findtext("pubDate",     "")
            desc    = item.findtext("description", "")
            desc    = re.sub(r"<[^>]+>", "", desc).strip()[:150]
            results.append(f"【{pubdate[:16]}】{title}\n{desc}\nURL: {link}")

        if not results:
            return ToolResult(ok=True, output=f"ニュースなし: {topic}")

        output = f"=== 最新ニュース: {topic} ===\n\n" + "\n\n".join(results)
        return ToolResult(ok=True, output=output)

    except Exception as e:
        return ToolResult(ok=False, output=f"ERROR: {e}")


def tool_fetch_ranking(action: dict) -> ToolResult:
    """
    HackerNews / PyPI / GitHub Trending からランキングを取得する。
    全て公式API・robots.txt 許可済み。

    action keys:
        category : "hackernews" / "pypi" / "github"（省略時 hackernews）
    """
    category = action.get("category", "hackernews")

    try:
        if category == "hackernews":
            return _fetch_hackernews()
        elif category == "pypi":
            return _fetch_pypi_new()
        elif category == "github":
            return _fetch_github_trending()
        else:
            return ToolResult(
                ok=False,
                output=f"不明なカテゴリ: {category}\n使用可能: hackernews / pypi / github",
            )
    except Exception as e:
        return ToolResult(ok=False, output=f"ERROR: {e}")


def _fetch_hackernews() -> ToolResult:
    """HackerNews 公式 Firebase API（完全無料・制限なし）"""
    with urllib.request.urlopen(
        "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
    ) as r:
        ids = _json.loads(r.read())[:10]

    results = []
    for story_id in ids:
        with urllib.request.urlopen(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=10
        ) as r:
            item = _json.loads(r.read())
        if item and item.get("title"):
            score = item.get("score", 0)
            url   = item.get("url",   "")
            results.append(f"[{score}pts] {item['title']}\n{url}")

    output = "=== HackerNews Top10 ===\n\n" + "\n\n".join(results)
    return ToolResult(ok=True, output=output)


def _fetch_pypi_new() -> ToolResult:
    """PyPI 公式 RSS（最新パッケージ）"""
    with urllib.request.urlopen(
        "https://pypi.org/rss/updates.xml", timeout=10
    ) as r:
        root = _ET.fromstring(r.read())

    items   = root.findall(".//item")[:10]
    results = []
    for item in items:
        title = item.findtext("title", "")
        link  = item.findtext("link",  "")
        desc  = item.findtext("description", "")[:100]
        results.append(f"{title}\n{desc}\n{link}")

    output = "=== PyPI 最新パッケージ ===\n\n" + "\n\n".join(results)
    return ToolResult(ok=True, output=output)


def _fetch_github_trending() -> ToolResult:
    """GitHub 公式 API で Python リポジトリのトレンドを取得"""
    params = urllib.parse.urlencode({
        "q":        "language:python created:>2026-01-01",
        "sort":     "stars",
        "order":    "desc",
        "per_page": 10,
    })
    req = urllib.request.Request(
        f"https://api.github.com/search/repositories?{params}",
        headers={
            "User-Agent": "AgentBot/1.0",
            "Accept":     "application/vnd.github.v3+json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = _json.loads(r.read())

    results = []
    for repo in data.get("items", [])[:10]:
        name  = repo["full_name"]
        stars = repo["stargazers_count"]
        desc  = repo.get("description", "")[:100]
        url   = repo["html_url"]
        results.append(f"⭐{stars} {name}\n{desc}\n{url}")

    output = "=== GitHub Trending (Python) ===\n\n" + "\n\n".join(results)
    return ToolResult(ok=True, output=output)
# --- NEWS/RANKING END ---


# --- SECRETARY TOOLS START ---

def tool_search_places(
    query: str,
    location: str = "",
    limit: int = 5,
) -> ToolResult:
    """
    場所・店舗を検索する。
    OpenStreetMap Nominatim API（完全無料・APIキー不要）を使用。

    使用例:
      tool_search_places("ラーメン", "渋谷")
      tool_search_places("coffee shop", "Yokohama")
    """
    try:
        search_query = f"{query} {location}".strip()
        params = urllib.parse.urlencode({
            "q":               search_query,
            "format":          "json",
            "limit":           limit,
            "addressdetails":  1,
            "accept-language": "ja",
        })
        req = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/search?{params}",
            headers={"User-Agent": "AgentSecretary/1.0 (local research tool)"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            results = _json.loads(r.read())

        if not results:
            # フォールバック: Google News RSSで店舗情報を検索
            return _fetch_news_raw(f"{query} {location} おすすめ", max_results=3)

        lines = [f"=== {query} の検索結果 ({location}) ===\n"]
        for i, place in enumerate(results[:limit], 1):
            name    = place.get("display_name", "").split(",")[0]
            address = ", ".join(place.get("display_name", "").split(",")[:3])
            lat     = place.get("lat", "")
            lon     = place.get("lon", "")
            lines.append(
                f"[{i}] {name}\n"
                f"    住所: {address}\n"
                f"    座標: {lat}, {lon}\n"
            )

        return ToolResult(ok=True, output="\n".join(lines))

    except Exception as e:
        return ToolResult(ok=False, output=f"ERROR: {e}")


def tool_fetch_tech_info(
    topic: str,
    source: str = "auto",
) -> ToolResult:
    """
    技術・ガジェット情報を取得する。

    source:
      "auto"       - トピックに合わせて自動選択
      "news"       - Google News RSS
      "hackernews" - HackerNews Algolia API
      "github"     - GitHub API
      "arxiv"      - arXiv API（論文）
      "reddit"     - Reddit JSON API
    """
    try:
        if source == "auto":
            source = _detect_best_source(topic)
            print(f"    🔍 情報ソース自動選択: {source}")

        if source == "news":
            return _fetch_news_raw(topic, max_results=5)
        elif source == "hackernews":
            return _search_hackernews(topic)
        elif source == "github":
            return _search_github(topic)
        elif source == "arxiv":
            return _search_arxiv(topic)
        elif source == "reddit":
            return _search_reddit(topic)
        else:
            return _fetch_news_raw(topic, max_results=5)

    except Exception as e:
        return ToolResult(ok=False, output=f"ERROR: {e}")


def _detect_best_source(topic: str) -> str:
    """トピックのキーワードから最適なソースを判定する"""
    t = topic.lower()

    # 1. 論文・研究（最優先）
    if any(w in t for w in ["論文", "paper", "research", "arxiv", "llm", "transformer"]):
        return "arxiv"

    # 2. コード・ライブラリ（github優先）
    if any(w in t for w in ["python", "rust", "github", "library", "framework",
                             "api", "tool", "ライブラリ", "lang", "language"]):
        return "github"

    # 3. 技術ディスカッション
    if any(w in t for w in ["startup", "developer", "hack",
                             "gadget", "ガジェット", "programming"]):
        return "hackernews"

    return "news"


def _search_hackernews(query: str) -> ToolResult:
    """HackerNews Algolia API で全文検索（無料）"""
    params = urllib.parse.urlencode({
        "query":       query,
        "tags":        "story",
        "hitsPerPage": 5,
    })
    with urllib.request.urlopen(
        f"https://hn.algolia.com/api/v1/search?{params}", timeout=10
    ) as r:
        data = _json.loads(r.read())

    results = []
    for hit in data.get("hits", [])[:5]:
        title  = hit.get("title", "")
        points = hit.get("points", 0)
        url    = hit.get("url", "")
        results.append(f"[{points}pts] {title}\n{url}")

    output = f"=== HackerNews: {query} ===\n\n" + "\n\n".join(results)
    return ToolResult(ok=True, output=output)


def _search_github(query: str) -> ToolResult:
    """GitHub API でリポジトリ検索"""
    params = urllib.parse.urlencode({
        "q":        query,
        "sort":     "stars",
        "order":    "desc",
        "per_page": 5,
    })
    req = urllib.request.Request(
        f"https://api.github.com/search/repositories?{params}",
        headers={
            "User-Agent": "AgentSecretary/1.0",
            "Accept":     "application/vnd.github.v3+json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = _json.loads(r.read())

    results = []
    for repo in data.get("items", [])[:5]:
        name  = repo["full_name"]
        stars = repo["stargazers_count"]
        desc  = repo.get("description", "説明なし")[:100]
        url   = repo["html_url"]
        results.append(f"⭐{stars:,} {name}\n{desc}\n{url}")

    output = f"=== GitHub: {query} ===\n\n" + "\n\n".join(results)
    return ToolResult(ok=True, output=output)


def _search_arxiv(query: str) -> ToolResult:
    """arXiv API で論文検索（完全無料）"""
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "start":        0,
        "max_results":  5,
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    })
    with urllib.request.urlopen(
        f"https://export.arxiv.org/api/query?{params}", timeout=15
    ) as r:
        root = _ET.fromstring(r.read())

    ns      = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)

    results = []
    for entry in entries[:5]:
        title   = entry.findtext("atom:title",   "", ns).strip()
        summary = entry.findtext("atom:summary", "", ns).strip()[:150]
        link    = entry.find("atom:link[@rel='alternate']", ns)
        url     = link.get("href", "") if link is not None else ""
        results.append(f"📄 {title}\n{summary}...\n{url}")

    output = f"=== arXiv論文: {query} ===\n\n" + "\n\n".join(results)
    return ToolResult(ok=True, output=output)


def _search_reddit(query: str) -> ToolResult:
    """Reddit JSON API で情報検索（APIキー不要）"""
    params = urllib.parse.urlencode({
        "q":    query,
        "sort": "relevance",
        "t":    "month",
        "limit": 5,
    })
    req = urllib.request.Request(
        f"https://www.reddit.com/search.json?{params}",
        headers={"User-Agent": "AgentSecretary/1.0"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = _json.loads(r.read())

    posts   = data.get("data", {}).get("children", [])
    results = []
    for post in posts[:5]:
        d     = post.get("data", {})
        title = d.get("title", "")
        score = d.get("score", 0)
        sub   = d.get("subreddit", "")
        url   = f"https://reddit.com{d.get('permalink','')}"
        results.append(f"[r/{sub} | {score}pts] {title}\n{url}")

    output = f"=== Reddit: {query} ===\n\n" + "\n\n".join(results)
    return ToolResult(ok=True, output=output)


# --- PYPI STATS START ---
def tool_fetch_pypi_top(limit: int = 20) -> ToolResult:
    """
    PyPI の月間ダウンロード数トップパッケージを取得する。
    hugovk/top-pypi-packages の公開JSONを使用（無料・APIキー不要）。
    """
    import urllib.request as _req
    import json as _json2
    try:
        url = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
        with _req.urlopen(url, timeout=10) as r:
            data = _json2.loads(r.read())
        packages = data.get("rows", [])[:limit]
        lines = ["=== PyPI 月間トップパッケージ ===\n"]
        for i, pkg in enumerate(packages, 1):
            name     = pkg.get("project", "")
            dl_count = pkg.get("download_count", 0)
            lines.append(f"{i:2}. {name} ({dl_count:,} downloads/month)")
        return ToolResult(ok=True, output="\n".join(lines))
    except Exception as e:
        return ToolResult(ok=False, output=f"ERROR: {e}")
# --- PYPI STATS END ---
