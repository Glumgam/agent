"""
Zenn記事とはてなブログ記事のURLを紐付けて
相互リンクを管理するモジュール。
"""
import json
from pathlib import Path

AGENT_ROOT      = Path(__file__).parent
ZENN_LOG        = AGENT_ROOT / "memory" / "zenn_publish_log.json"
HATENA_LOG      = AGENT_ROOT / "memory" / "hatena_publish_log.json"
LINK_DB         = AGENT_ROOT / "memory" / "article_links.json"
ZENN_BASE_URL   = "https://zenn.dev/granking/articles"
HATENA_BASE_URL = "https://granking.hatenablog.com"


def build_link_db() -> dict:
    """
    ZennログとはてなログからURLを紐付けたDBを構築する。
    key: content/のファイル名
    value: {"zenn_url": ..., "hatena_url": ..., "title": ...}
    """
    db = {}

    # Zennログ読み込み
    if ZENN_LOG.exists():
        zenn = json.loads(ZENN_LOG.read_text(encoding="utf-8"))
        for fname, meta in zenn.items():
            slug     = meta.get("slug", "")
            zenn_url = f"{ZENN_BASE_URL}/{slug}"
            db[fname] = db.get(fname, {})
            db[fname]["zenn_url"] = zenn_url

    # はてなログ読み込み
    if HATENA_LOG.exists():
        hatena = json.loads(HATENA_LOG.read_text(encoding="utf-8"))
        for fname, meta in hatena.items():
            hatena_url = meta.get("url", "")
            title      = meta.get("title", "")
            db[fname] = db.get(fname, {})
            db[fname]["hatena_url"] = hatena_url
            db[fname]["title"]      = title

    # DBに保存
    LINK_DB.parent.mkdir(exist_ok=True)
    LINK_DB.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return db


def get_links(fname: str) -> dict:
    """記事ファイル名からURLを取得する"""
    if not LINK_DB.exists():
        build_link_db()
    db = json.loads(LINK_DB.read_text(encoding="utf-8"))
    return db.get(fname, {})


def make_zenn_footer(hatena_url: str) -> str:
    """Zenn記事用のはてなブログへの導線フッターを生成する"""
    if not hatena_url:
        return ""
    return f"""
---
## 📖 より詳しく知りたい方へ
この記事では基本的な実装を解説しました。
実務でのコード例・応用パターン・トラブル対処法は
以下の記事で詳しく解説しています。

👉 [詳細解説・実践コードはこちら]({hatena_url})

---
"""


def make_hatena_footer(zenn_url: str) -> str:
    """はてなブログ記事用のZennへの導線フッターを生成する"""
    if not zenn_url:
        return ""
    return f"""
---
## 🔗 関連記事
この記事の概要版はZennでも公開しています。

👉 [Zennで読む（概要版）]({zenn_url})

---
"""
