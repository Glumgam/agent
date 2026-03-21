"""
公式ドキュメント自動収集システム。
docs_sources.json に記載されたソースを取得し、
rag_retriever の official_docs コレクションに登録する。
"""
import json
import re
import hashlib
import time
from pathlib import Path
from datetime import datetime

AGENT_ROOT   = Path(__file__).parent
SOURCES_FILE = AGENT_ROOT / "docs_sources.json"

# =====================================================
# HTML → Markdown 変換
# =====================================================

def _strip_tags(html: str) -> str:
    """最小限のタグ除去。requests が不要な箇所に使う。"""
    # scriptタグ・styleタグを丸ごと除去
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # コメント除去
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    # その他タグ除去
    html = re.sub(r"<[^>]+>", " ", html)
    return html


def html_to_markdown(html: str) -> str:
    """
    HTMLをシンプルなMarkdownに変換する。
    外部ライブラリ非依存（html.parser のみ使用）。
    """
    from html.parser import HTMLParser

    class _MDParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.result      = []
            self._skip       = False
            self._skip_tags  = {"script", "style", "nav", "footer", "header",
                                 "aside", "form", "noscript"}
            self._block_tags = {"p", "div", "section", "article",
                                 "li", "dt", "dd", "blockquote"}
            self._heading    = None
            self._link_href  = None
            self._in_pre     = False
            self._in_code    = False
            self._depth      = {}   # tag -> nesting depth for skip_tags

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            attrs_d = dict(attrs)

            # skip タグに入ったら内部を無視
            if tag in self._skip_tags:
                self._depth[tag] = self._depth.get(tag, 0) + 1
                self._skip = True
                return

            if self._skip:
                return

            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(tag[1])
                self.result.append("\n" + "#" * level + " ")
                self._heading = tag
            elif tag == "pre":
                self._in_pre = True
                self.result.append("\n```\n")
            elif tag == "code" and not self._in_pre:
                self._in_code = True
                self.result.append("`")
            elif tag == "a":
                self._link_href = attrs_d.get("href", "")
            elif tag == "br":
                self.result.append("\n")
            elif tag == "hr":
                self.result.append("\n---\n")
            elif tag in self._block_tags:
                self.result.append("\n")
            elif tag == "li":
                self.result.append("\n- ")
            elif tag == "strong" or tag == "b":
                self.result.append("**")
            elif tag == "em" or tag == "i":
                self.result.append("_")

        def handle_endtag(self, tag):
            tag = tag.lower()

            if tag in self._skip_tags:
                self._depth[tag] = max(0, self._depth.get(tag, 1) - 1)
                if self._depth[tag] == 0:
                    self._skip = False
                return

            if self._skip:
                return

            if tag == "pre":
                self._in_pre = False
                self.result.append("\n```\n")
            elif tag == "code" and not self._in_pre:
                self._in_code = False
                self.result.append("`")
            elif tag == "a" and self._link_href:
                # リンクテキストはすでに追加済み
                self._link_href = None
            elif tag in ("strong", "b"):
                self.result.append("**")
            elif tag in ("em", "i"):
                self.result.append("_")
            elif self._heading and tag == self._heading:
                self.result.append("\n")
                self._heading = None
            elif tag in self._block_tags:
                self.result.append("\n")

        def handle_data(self, data):
            if self._skip:
                return
            self.result.append(data)

        def get_markdown(self):
            text = "".join(self.result)
            # 連続改行を2つまでに圧縮
            text = re.sub(r"\n{3,}", "\n\n", text)
            # 各行末尾の空白を除去
            text = "\n".join(line.rstrip() for line in text.splitlines())
            return text.strip()

    parser = _MDParser()
    try:
        parser.feed(html)
    except Exception:
        # フォールバック: タグを単純除去
        return _strip_tags(html)
    return parser.get_markdown()


# =====================================================
# バージョン取得
# =====================================================

def _fetch_version(source: dict) -> str:
    """
    version_url が指定されていれば APIを叩いてバージョンを取得する。
    失敗時は static_version を返す。
    """
    static = source.get("static_version") or "unknown"
    version_url = source.get("version_url")
    if not version_url:
        return static

    try:
        import urllib.request
        req = urllib.request.Request(version_url,
                                     headers={"User-Agent": "Mozilla/5.0 (agent)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        key = source.get("version_pattern", "tag_name")
        ver = str(data.get(key, "")).lstrip("v").strip()
        return ver if ver else static
    except Exception:
        return static


# =====================================================
# コンテンツ取得
# =====================================================

def fetch_content(source: dict) -> tuple:
    """
    ソース定義から HTML を取得し Markdown に変換する。
    Returns:
        (markdown: str, version: str)
    戻り値が ("", ...) の場合は取得失敗。
    """
    url = source["url"]
    version = _fetch_version(source)

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; agent/1.0)",
            "Accept":     "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "ja,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_bytes = resp.read()

        # エンコーディング検出（Content-Type ヘッダーを優先）
        ct = resp.headers.get("Content-Type", "")
        charset_m = re.search(r"charset=([^\s;]+)", ct, re.IGNORECASE)
        charset = charset_m.group(1) if charset_m else "utf-8"

        html = raw_bytes.decode(charset, errors="replace")

        fmt = source.get("format", "html")
        if fmt == "html":
            markdown = html_to_markdown(html)
        else:
            markdown = html  # Markdown ファイルはそのまま

        if not markdown or len(markdown) < 200:
            print(f"  ⚠️ コンテンツが短すぎる ({len(markdown)}文字): {url}")
            return ("", version)

        return (markdown, version)

    except Exception as e:
        print(f"  ❌ 取得失敗 [{source['id']}]: {e}")
        return ("", version)


# =====================================================
# メイン: 全ソースを収集・登録
# =====================================================

def collect_all(force: bool = False, target_id: str = None) -> dict:
    """
    docs_sources.json の全ソースを収集して official_docs に登録する。
    Args:
        force:     Trueなら既存バージョンでも再登録
        target_id: 指定がある場合はそのIDのみ処理
    Returns:
        {"registered": int, "skipped": int, "failed": int, "sources": [...]}
    """
    if not SOURCES_FILE.exists():
        print(f"  ❌ {SOURCES_FILE} が見つかりません")
        return {"registered": 0, "skipped": 0, "failed": 0, "sources": []}

    sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    if target_id:
        sources = [s for s in sources if s["id"] == target_id]
        if not sources:
            print(f"  ❌ ID '{target_id}' が docs_sources.json に見つかりません")
            return {"registered": 0, "skipped": 0, "failed": 1, "sources": []}

    from rag_retriever import index_official_doc

    results = {"registered": 0, "skipped": 0, "failed": 0, "sources": []}

    for source in sources:
        sid = source["id"]
        print(f"\n📥 収集中: {sid} ({source['name']})")

        markdown, version = fetch_content(source)
        if not markdown:
            results["failed"] += 1
            results["sources"].append({"id": sid, "status": "failed"})
            continue

        # ハッシュでコンテンツの変化を検出
        content_hash = hashlib.md5(markdown.encode()).hexdigest()[:8]
        ver_with_hash = f"{version}-{content_hash}"

        n = index_official_doc(
            doc_id=sid,
            content=markdown,
            source=source["url"],
            version=ver_with_hash,
            force=force,
        )

        if n == 0:
            results["skipped"] += 1
            results["sources"].append({"id": sid, "status": "skipped", "version": ver_with_hash})
        else:
            results["registered"] += 1
            results["sources"].append({
                "id":      sid,
                "status":  "registered",
                "version": ver_with_hash,
                "chunks":  n,
            })

        # サーバー負荷軽減のため少し待機
        time.sleep(1)

    print(f"\n✅ 収集完了: registered={results['registered']} "
          f"skipped={results['skipped']} failed={results['failed']}")
    return results


def show_status() -> None:
    """登録済み公式ドキュメント一覧を表示する"""
    from rag_retriever import list_official_docs
    docs = list_official_docs()
    if not docs:
        print("登録済みドキュメントなし")
        return

    print(f"\n{'ID':<30} {'Version':<20} {'Chunks':>6}  Last Updated")
    print("-" * 75)
    for doc_id, meta in sorted(docs.items()):
        ver     = meta.get("version", "?")[:18]
        chunks  = meta.get("chunks", 0)
        updated = meta.get("last_updated", "")[:16]
        print(f"{doc_id:<30} {ver:<20} {chunks:>6}  {updated}")


def run_doc_collection(force: bool = False) -> dict:
    """autonomous_loop.py から呼ばれるエントリポイント"""
    return collect_all(force=force)


# =====================================================
# CLI エントリポイント
# =====================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="公式ドキュメント自動収集")
    parser.add_argument("--id",    type=str,  default=None,  help="特定ドキュメントIDのみ収集")
    parser.add_argument("--force", action="store_true",      help="既存バージョンでも再登録")
    parser.add_argument("--list",  action="store_true",      help="登録済み一覧を表示")
    args = parser.parse_args()

    if args.list:
        show_status()
    else:
        collect_all(force=args.force, target_id=args.id)
