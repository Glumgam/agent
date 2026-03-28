"""
Zenn自動投稿システム。
content/ に生成された記事を
zenn-content リポジトリに自動投稿する。
使い方:
  python zenn_publisher.py              # 未投稿記事を全て投稿
  python zenn_publisher.py --dry-run    # 投稿せず確認のみ
  python zenn_publisher.py --stats      # 投稿状況確認
"""
import re
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

AGENT_ROOT    = Path(__file__).parent
CONTENT_DIR   = AGENT_ROOT / "content"
ZENN_REPO     = Path.home() / "zenn-content"
ZENN_ARTICLES = ZENN_REPO / "articles"
PUBLISH_LOG   = AGENT_ROOT / "memory" / "zenn_publish_log.json"

# ジャンル別タグ
GENRE_TOPICS = {
    "python_tips":   ["python", "プログラミング", "tips"],
    "ai_tools":      ["python", "ollama", "llm", "ai"],
    "library_intro": ["python", "ライブラリ", "プログラミング"],
    "automation":    ["python", "automation", "プログラミング"],
}

# ジャンル別絵文字
GENRE_EMOJI = {
    "python_tips":   "🐍",
    "ai_tools":      "🤖",
    "library_intro": "📦",
    "automation":    "⚙️",
}


def convert_to_zenn(article_path: Path, genre_id: str = None) -> str:
    """
    記事をZennフォーマットに変換する。
    フロントマターを追加してZenn用Markdownを返す。
    """
    content = article_path.read_text(encoding="utf-8")

    # タイトルを抽出
    title = ""
    for line in content.split("\n"):
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break
    # タイトルが取得できない場合はファイル名から生成（日付プレフィックス除去）
    if not title:
        stem = article_path.stem
        stem = re.sub(r"^\d{8}_?", "", stem)   # 日付除去
        title = stem.replace("_", " ").strip()
        print(f"  ⚠️ タイトル抽出失敗 → ファイル名から生成: {title}")

    # ジャンル判定
    if not genre_id:
        genre_id = _detect_genre(content)

    topics     = GENRE_TOPICS.get(genre_id, ["python", "プログラミング"])
    emoji      = GENRE_EMOJI.get(genre_id, "📝")
    topics_str = json.dumps(topics, ensure_ascii=False)

    # タイトル内のダブルクォートをエスケープ
    title_escaped = title.replace('"', '\\"')

    frontmatter = f'''---
title: "{title_escaped}"
emoji: "{emoji}"
type: "tech"
topics: {topics_str}
published: false
---
'''
    # はてなブログへの導線フッターを追加（投稿済みの場合のみ）
    try:
        from publisher_linker import get_links, make_zenn_footer
        links      = get_links(article_path.name)
        hatena_url = links.get("hatena_url", "")
        if hatena_url:
            content = content + make_zenn_footer(hatena_url)
            print(f"  🔗 はてな導線を追加: {hatena_url}")
    except Exception:
        pass

    return frontmatter + content


def _detect_genre(content: str) -> str:
    """コンテンツからジャンルを推定する"""
    content_lower = content.lower()
    # ライブラリ紹介を最初に判定（pip install等は他ジャンルにも含まれるため先行チェック）
    if any(w in content_lower for w in [
        "インストール方法", "類似ライブラリ",
        "typer", "rich", "httpx", "loguru", "pydantic",
        "schedule", "arrow", "tqdm", "tabulate",
    ]):
        return "library_intro"
    # AI・LLMツール
    if any(w in content_lower for w in [
        "ollama", "llm", "gpt", "bert", "transformer",
        "hugging face", "sentence-transformer",
    ]):
        return "ai_tools"
    # 自動化
    if any(w in content_lower for w in [
        "自動化", "automation", "自動生成", "自動管理",
        "スクリプト", "cron",
    ]):
        return "automation"
    # pip install だけならライブラリ紹介
    if "pip install" in content_lower:
        return "library_intro"
    # デフォルト: Python tips
    return "python_tips"


def _make_slug(article_path: Path) -> str:
    """記事のスラッグを生成する（キーワードマップ方式）"""
    import unicodedata
    stem = unicodedata.normalize("NFC", article_path.stem).lower()

    # 日付プレフィックスを抽出
    date_match = re.match(r"(\d{8})", stem)
    date_prefix = date_match.group(1) if date_match else ""

    # キーワードマップ（日本語 → 英語スラッグ）
    keyword_map = {
        "python":           "python",
        "ollama":           "ollama",
        "llm":              "llm",
        "ai":               "ai",
        "excel":            "excel",
        "git":              "git",
        "cli":              "cli",
        "api":              "api",
        "rag":              "rag",
        "型ヒント":          "type-hints",
        "並列処理":          "parallel",
        "コンテキスト":       "context",
        "マネージャ":        "manager",
        "データクラス":       "dataclass",
        "ライブラリ":        "library",
        "自動化":            "automation",
        "自動生成":          "autogen",
        "実践":              "practical",
        "ガイド":            "guide",
        "入門":              "intro",
        "活用":              "usage",
        "実装":              "impl",
        "方法":              "how-to",
        "使い方":            "howto",
        "ファイル":          "file",
        "管理":              "management",
        "モデル":            "model",
        "完全":              "complete",
        "ローカル":          "local",
        "保守性":            "maintainability",
        "logging":          "logging",
        "loggingモジュール": "logging",
        "モジュール":        "module",
        "使い分け":          "comparison",
        "namedtuple":       "namedtuple",
        "rich":             "rich",
        "typer":            "typer",
        "sentence":        "sentence",
        "transformer":      "transformer",
        "検索":              "search",
        "httpx":            "httpx",
        "pydantic":         "pydantic",
        "schedule":         "schedule",
        "loguru":           "loguru",
        "スクレイピング":     "scraping",
        "レポート":          "report",
        "デコレータ":        "decorator",
        "内包表記":          "comprehension",
        "ジェネレータ":       "generator",
        "pathlib":          "pathlib",
    }

    slug_parts = []  # 日付プレフィックスなし
    for ja, en in keyword_map.items():
        if ja in stem and en not in slug_parts:
            slug_parts.append(en)
            if len("-".join(slug_parts)) >= 30:
                break

    slug = "-".join(slug_parts)
    slug = re.sub(r"[^a-z0-9\-_]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")

    # 12文字未満は日付補完
    if len(slug) < 12:
        suffix = date_prefix[:6] if date_prefix else "article"
        slug = slug + "-" + suffix if slug else "article-" + suffix

    return slug[:50]


def _load_publish_log() -> dict:
    if PUBLISH_LOG.exists():
        try:
            return json.loads(PUBLISH_LOG.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_publish_log(log: dict):
    PUBLISH_LOG.parent.mkdir(exist_ok=True)
    PUBLISH_LOG.write_text(
        json.dumps(log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def publish_article(
    article_path: Path,
    dry_run: bool = False,
) -> dict:
    """1記事をZennフォーマットに変換してファイルを書き込む（git操作なし）"""
    log = _load_publish_log()

    key = article_path.name
    if key in log:
        return {"success": False, "reason": "already_published"}

    zenn_content = convert_to_zenn(article_path)
    slug         = _make_slug(article_path)
    zenn_path    = ZENN_ARTICLES / f"{slug}.md"

    # 重複回避（既存ファイルがある場合はスキップ）
    if zenn_path.exists():
        print(f"  ⚠️ ファイル既存スキップ: {zenn_path.name}")
        return {"success": False, "reason": "file_exists"}

    if dry_run:
        print(f"  🔍 DRY RUN: {zenn_path.name}")
        return {"success": True, "dry_run": True, "slug": slug}

    ZENN_ARTICLES.mkdir(parents=True, exist_ok=True)
    zenn_path.write_text(zenn_content, encoding="utf-8")
    print(f"  ✅ 変換完了: {zenn_path.name}")

    log[key] = {
        "slug":         slug,
        "zenn_path":    str(zenn_path),
        "published_at": datetime.now().isoformat(),
    }
    _save_publish_log(log)
    return {"success": True, "slug": slug, "zenn_path": str(zenn_path)}


PUBLISH_GENRES = {"finance"}  # 投稿対象ジャンル（tech/general はローカル保存のみ）


def publish_all(dry_run: bool = False) -> dict:
    """未投稿の記事を全て変換して1回だけgit pushする。
    finance ジャンルのみ投稿。tech/general はローカル保存のみ。
    """
    log      = _load_publish_log()
    articles = sorted(CONTENT_DIR.rglob("*.md"))

    # ログ同期（zenn-contentに存在しないファイルはログから削除）
    cleaned = 0
    for key, meta in list(log.items()):
        zenn_path = Path(meta.get("zenn_path", ""))
        if not zenn_path.exists():
            del log[key]
            cleaned += 1
    if cleaned > 0:
        _save_publish_log(log)
        print(f"  🔄 ログ同期: {cleaned}件削除")

    unpublished = [
        a for a in articles
        if not a.name.startswith("._")
        and a.name not in log
        and not a.name.endswith("_hatena.md")  # はてな版は除外
        and a.parent.name in PUBLISH_GENRES     # finance のみ投稿
    ]

    # ジャンル別に件数を表示
    non_finance = [
        a for a in articles
        if not a.name.startswith("._")
        and not a.name.endswith("_hatena.md")
        and a.parent.name not in PUBLISH_GENRES
    ]
    print(f"\n{'='*50}")
    print(f"  Zenn自動投稿（finance のみ）")
    print(f"  投稿対象: {len(unpublished)}件 / スキップ（tech/general）: {len(non_finance)}件")
    print(f"{'='*50}\n")
    for a in non_finance:
        print(f"  ⏭️ 投稿スキップ（{a.parent.name}）: {a.name}")

    if not unpublished:
        print("  投稿する記事なし")
        return {"success": 0, "skipped": len(articles), "failed": 0}

    results = {"success": 0, "skipped": len(articles) - len(unpublished), "failed": 0}

    # 全記事をファイルに書き込む
    for article in unpublished:
        result = publish_article(article, dry_run=dry_run)
        if result.get("success"):
            results["success"] += 1
        elif result.get("reason") != "already_published":
            results["failed"] += 1

    if dry_run or results["success"] == 0:
        return results

    # 1回だけgit add & commit & push（zenn-content）
    try:
        subprocess.run(
            ["git", "add", "articles/"],
            cwd=ZENN_REPO, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"feat: {results['success']}件の記事を追加"],
            cwd=ZENN_REPO, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=ZENN_REPO, check=True, capture_output=True,
        )
        print(f"\n  ✅ Zenn push完了: {results['success']}件")
    except subprocess.CalledProcessError as e:
        print(f"\n  ❌ Zenn push失敗: {e}")
        results["failed"] += 1

    # グラフ画像を agent リポジトリへ push（GitHub raw URL で配信するため）
    charts_dir = AGENT_ROOT / "content" / "charts"
    if charts_dir.exists() and any(charts_dir.iterdir()):
        try:
            subprocess.run(
                ["git", "add", "content/charts/"],
                cwd=AGENT_ROOT, check=True, capture_output=True,
            )
            # 差分がある場合のみコミット
            diff = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=AGENT_ROOT, capture_output=True,
            )
            if diff.returncode != 0:  # returncode=1 → staged changes あり
                subprocess.run(
                    ["git", "commit", "-m", "chore: update chart images"],
                    cwd=AGENT_ROOT, check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "push", "origin", "master"],
                    cwd=AGENT_ROOT, check=True, capture_output=True,
                )
                print("  ✅ charts push完了（agent repo）")
            else:
                print("  ℹ️ charts に差分なし（push スキップ）")
        except subprocess.CalledProcessError as e:
            print(f"  ⚠️ charts push失敗: {e}")

    return results


def show_stats():
    """投稿状況を表示する"""
    log      = _load_publish_log()
    articles = list(CONTENT_DIR.rglob("[0-9]*.md"))
    print(f"\n## Zenn投稿状況")
    print(f"生成記事: {len(articles)}件")
    print(f"投稿済み: {len(log)}件")
    print(f"未投稿:   {len(articles) - len(log)}件")
    if log:
        print("\n### 投稿済み記事（最新5件）")
        for fname, meta in list(log.items())[-5:]:
            print(f"  - {fname[:40]} → {meta['slug']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zenn自動投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず確認のみ")
    parser.add_argument("--stats",   action="store_true", help="投稿状況確認")
    parser.add_argument("--all",     action="store_true", help="全記事を投稿")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.dry_run:
        publish_all(dry_run=True)
    elif args.all:
        results = publish_all()
        print(f"\n完了: 投稿={results['success']} "
              f"スキップ={results['skipped']} 失敗={results['failed']}")
    else:
        publish_all()
