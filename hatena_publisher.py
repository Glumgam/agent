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
import xml.sax.saxutils as saxutils
from pathlib import Path
from datetime import datetime

AGENT_ROOT   = Path(__file__).parent
CONTENT_DIR  = AGENT_ROOT / "content"
PUBLISH_LOG  = AGENT_ROOT / "memory" / "hatena_publish_log.json"
CONFIG_FILE  = AGENT_ROOT / "config" / "hatena_config.json"

# はてなブログ設定
HATENA_ID          = "granking"
BLOG_DOMAIN        = "granking.hatenablog.com"
API_ENDPOINT       = f"https://blog.hatena.ne.jp/{HATENA_ID}/{BLOG_DOMAIN}/atom/entry"
PHOTLIFE_ENDPOINT  = f"https://f.hatena.ne.jp/{HATENA_ID}/atom/post"

# GitHub raw URL 設定（グラフ画像の配信用）
GITHUB_USER   = "Glumgam"
GITHUB_REPO   = "agent"
GITHUB_BRANCH = "master"
_AGENT_ROOT_FOR_URL = Path("/Volumes/ESD-EHA/agent")


def get_chart_github_url(image_path: Path) -> str:
    """
    ローカルのグラフパスをGitHub raw URLに変換する。
    git pushされている前提。
    例: /Volumes/ESD-EHA/agent/content/charts/xxx.png
        → https://raw.githubusercontent.com/Glumgam/agent/master/content/charts/xxx.png
    """
    rel_path = image_path.relative_to(_AGENT_ROOT_FOR_URL)
    return (
        f"https://raw.githubusercontent.com/"
        f"{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{rel_path}"
    )


def upload_image_to_hatena(image_path: Path, api_key: str) -> "str | None":
    """
    はてなフォトライフに画像をアップロードし、画像URLを返す。
    Args:
        image_path: アップロードするPNG画像のPath
        api_key:    はてなAPIキー
    Returns:
        画像URL（str）または None
    """
    try:
        image_data = image_path.read_bytes()
        encoded    = base64.b64encode(image_data).decode("utf-8")
        title      = saxutils.escape(image_path.stem)
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:dc="http://purl.org/dc/elements/1.1/"
       xmlns:hatena="http://www.hatena.ne.jp/info/xmlns#">
  <title>{title}</title>
  <content mode="base64" type="image/png">{encoded}</content>
  <dc:subject>agent-charts</dc:subject>
</entry>"""
        credentials = base64.b64encode(
            f"{HATENA_ID}:{api_key}".encode()
        ).decode()
        headers = {
            "Content-Type": "application/atom+xml",
            "Authorization": f"Basic {credentials}",
        }
        response = requests.post(
            PHOTLIFE_ENDPOINT,
            data=xml.encode("utf-8"),
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        # <hatena:imageurl> から画像URLを抽出
        m = re.search(r"<hatena:imageurl>([^<]+)</hatena:imageurl>", response.text)
        if m:
            img_url = m.group(1)
            print(f"  🖼️ 画像アップロード完了: {img_url}")
            return img_url
        # フォールバック: syntaxが異なる場合
        m = re.search(r'src="(https://[^"]+fotolife[^"]+)"', response.text)
        if m:
            return m.group(1)
        print(f"  ⚠️ 画像URL取得失敗（レスポンス: {response.text[:200]}）")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ 画像アップロードHTTPエラー: {e.response.status_code} {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"  ⚠️ 画像アップロード失敗: {e}")
        return None


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


def _prepare_content(content: str) -> tuple:
    """
    記事を投稿用に準備する。
    Returns: (content, content_type)
    """
    # フロントマター除去
    content = re.sub(r'^---.*?---\n', '', content, flags=re.DOTALL)
    # Markdownをそのまま返す
    return content.strip(), "text/plain"


def _make_hatena_entry(title: str, body: str, content_type: str, draft: bool = True) -> str:
    """AtomPub形式のXMLエントリを生成する"""
    # タイトルとbodyをXMLエスケープ（& < > が含まれるMarkdown対策）
    title_escaped = saxutils.escape(title)
    body_escaped  = saxutils.escape(body)
    draft_str     = "yes" if draft else "no"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:app="http://www.w3.org/2007/app">
  <title>{title_escaped}</title>
  <content type="{content_type}">{body_escaped}</content>
  <app:control>
    <app:draft>{draft_str}</app:draft>
  </app:control>
</entry>"""


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
    body, content_type = _prepare_content(content)
    xml = _make_hatena_entry(title, body, content_type, draft=draft)
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

    # ZennのURLを取得して導線フッターを追加
    # ※フロントマター除去は _prepare_content() 内で実施
    body = content
    try:
        from publisher_linker import get_links, make_hatena_footer, build_link_db
        build_link_db()
        links    = get_links(article_path.name)
        zenn_url = links.get("zenn_url", "")
        if zenn_url:
            body = body + make_hatena_footer(zenn_url)
            print(f"  🔗 Zenn導線を追加: {zenn_url}")
        else:
            # Zenn未投稿の場合は汎用フッター
            body = body + f"\n\n---\n*この記事はAIエージェントによって自動生成されました。*\n"
    except Exception:
        body = body + f"\n\n---\n*この記事はAIエージェントによって自動生成されました。*\n"

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
    articles = sorted(CONTENT_DIR.rglob("*.md"))
    articles = [a for a in articles if not a.name.startswith("._")]

    unpublished = [
        a for a in articles
        if a.name not in log
        and not a.name.endswith("_zenn.md")  # Zenn版は除外
    ]

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
    articles = list(CONTENT_DIR.rglob("*.md"))
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
