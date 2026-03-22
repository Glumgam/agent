"""
はてなブログ自動投稿システム。
AtomPub APIを使って記事を自動投稿する。
Zenn（概要・入門）と役割分担し、
はてなブログでは実務・深掘り記事を投稿する。
使い方:
  python hatena_publisher.py              # 未投稿記事を全て投稿
  python hatena_publisher.py --dry-run    # 確認のみ
  python hatena_publisher.py --stats      # 統計表示
"""
import re
import json
import base64
import requests
import argparse
from pathlib import Path
from datetime import datetime

AGENT_ROOT   = Path(__file__).parent
CONTENT_DIR  = AGENT_ROOT / "content"
PUBLISH_LOG  = AGENT_ROOT / "memory" / "hatena_publish_log.json"
CONFIG_FILE  = AGENT_ROOT / "config" / "hatena_config.json"

# はてなブログ設定
HATENA_ID    = "granking"
BLOG_DOMAIN  = "granking.hatenablog.com"
API_ENDPOINT = f"https://blog.hatena.ne.jp/{HATENA_ID}/{BLOG_DOMAIN}/atom/entry"


def _load_config() -> dict:
    """設定ファイルからAPIキーを読み込む"""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def _load_log() -> dict:
    if PUBLISH_LOG.exists():
        return json.loads(PUBLISH_LOG.read_text(encoding="utf-8"))
    return {}


def _save_log(log: dict):
    PUBLISH_LOG.parent.mkdir(exist_ok=True)
    PUBLISH_LOG.write_text(
        json.dumps(log, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _make_hatena_entry(title: str, content: str, draft: bool = True) -> str:
    """AtomPub形式のXMLを生成する"""
    draft_str = "yes" if draft else "no"
    # MarkdownをHTMLに簡易変換
    html = _markdown_to_html(content)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:app="http://www.w3.org/2007/app">
  <title>{title}</title>
  <content type="text/html">{html}</content>
  <app:control>
    <app:draft>{draft_str}</app:draft>
  </app:control>
</entry>"""


def _markdown_to_html(md: str) -> str:
    """MarkdownをHTMLに変換する（簡易版）"""
    try:
        import markdown
        return markdown.markdown(md, extensions=["fenced_code", "tables"])
    except ImportError:
        # markdownライブラリがない場合は簡易変換
        html = md
        # コードブロック
        html = re.sub(
            r"```(\w+)?\n(.*?)```",
            lambda m: f"<pre><code>{m.group(2)}</code></pre>",
            html, flags=re.DOTALL
        )
        # 見出し
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$",  r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$",   r"<h1>\1</h1>", html, flags=re.MULTILINE)
        # 改行
        html = html.replace("\n", "<br>\n")
        return html


def post_article(
    title: str,
    content: str,
    api_key: str,
    draft: bool = True,
) -> dict:
    """
    はてなブログに記事を投稿する。
    Args:
        title:   記事タイトル
        content: 記事本文（Markdown）
        api_key: はてなAPIキー
        draft:   下書きとして投稿するか
    Returns:
        {"success": bool, "url": str, "entry_id": str}
    """
    xml = _make_hatena_entry(title, content, draft=draft)
    credentials = base64.b64encode(
        f"{HATENA_ID}:{api_key}".encode()
    ).decode()
    headers = {
        "Content-Type": "application/atom+xml",
        "Authorization": f"Basic {credentials}",
    }
    try:
        response = requests.post(
            API_ENDPOINT,
            data=xml.encode("utf-8"),
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        # レスポンスからURLを抽出
        url = ""
        m = re.search(r"<link[^>]+rel=\"alternate\"[^>]+href=\"([^\"]+)\"", response.text)
        if m:
            url = m.group(1)
        entry_id = ""
        m = re.search(r"<id>([^<]+)</id>", response.text)
        if m:
            entry_id = m.group(1)
        print(f"  ✅ 投稿完了: {url or 'URL取得失敗'}")
        return {"success": True, "url": url, "entry_id": entry_id}
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ HTTPエラー: {e.response.status_code} {e.response.text[:200]}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"  ❌ 投稿失敗: {e}")
        return {"success": False, "error": str(e)}


def publish_article(article_path: Path, api_key: str, dry_run: bool = False) -> dict:
    """1記事をはてなブログに投稿する"""
    log = _load_log()
    key = article_path.name
    if key in log:
        return {"success": False, "reason": "already_published"}

    content = article_path.read_text(encoding="utf-8", errors="ignore")

    # タイトル抽出
    title = ""
    for line in content.split("\n"):
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break
    if not title:
        title = article_path.stem.replace("_", " ")

    # フロントマター（Zenn用）を除去
    body = re.sub(r"^---.*?---\n", "", content, flags=re.DOTALL).strip()

    # Zennへの誘導リンクをフッターに追加
    zenn_footer = f"""

---
## 🔗 関連記事
この記事の基本的な内容はZennでも解説しています。
コード例や環境構築の詳細はZennの記事もあわせてご覧ください。
- [Zennで技術記事を読む](https://zenn.dev/{HATENA_ID})
---
*この記事はAIエージェントによって自動生成されました。*
"""
    body = body + zenn_footer

    if dry_run:
        print(f"  🔍 DRY RUN: {title[:40]}")
        return {"success": True, "dry_run": True}

    result = post_article(title, body, api_key, draft=True)
    if result["success"]:
        log[key] = {
            "title":        title,
            "url":          result.get("url", ""),
            "entry_id":     result.get("entry_id", ""),
            "published_at": datetime.now().isoformat(),
        }
        _save_log(log)
    return result


def publish_all(api_key: str, dry_run: bool = False) -> dict:
    """未投稿の記事を全て投稿する"""
    log      = _load_log()
    articles = sorted(CONTENT_DIR.glob("*.md"))
    articles = [a for a in articles if not a.name.startswith("._")]

    unpublished = [a for a in articles if a.name not in log]

    print(f"\n{'='*50}")
    print(f"  はてなブログ自動投稿")
    print(f"  未投稿記事: {len(unpublished)}件")
    print(f"{'='*50}\n")

    results = {"success": 0, "skipped": len(articles) - len(unpublished), "failed": 0}

    for article in unpublished:
        content = article.read_text(encoding="utf-8", errors="ignore")
        title = ""
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
        print(f"  📝 {title[:40]}")
        result = publish_article(article, api_key, dry_run=dry_run)
        if result.get("success"):
            results["success"] += 1
        elif result.get("reason") != "already_published":
            results["failed"] += 1

    return results


def show_stats():
    log      = _load_log()
    articles = list(CONTENT_DIR.glob("*.md"))
    print(f"\n## はてなブログ投稿状況")
    print(f"生成記事: {len(articles)}件")
    print(f"投稿済み: {len(log)}件")
    print(f"未投稿:   {len(articles) - len(log)}件")
    if log:
        print("\n### 最新5件")
        for fname, meta in list(log.items())[-5:]:
            print(f"  - {meta.get('title', '')[:40]}")
            print(f"    {meta.get('url', '')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="はてなブログ自動投稿")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stats",   action="store_true")
    parser.add_argument("--all",     action="store_true")
    args = parser.parse_args()

    # APIキーを設定ファイルから読み込む
    config  = _load_config()
    api_key = config.get("api_key", "")

    if not api_key and not args.stats:
        print("❌ APIキーが設定されていません")
        print(f"以下のファイルを作成してください: {CONFIG_FILE}")
        print('{"api_key": "your_api_key_here"}')
        exit(1)

    if args.stats:
        show_stats()
    elif args.dry_run:
        publish_all(api_key, dry_run=True)
    else:
        results = publish_all(api_key)
        print(f"\n完了: 投稿={results['success']} スキップ={results['skipped']} 失敗={results['failed']}")
