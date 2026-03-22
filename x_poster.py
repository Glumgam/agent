"""
X（Twitter）自動投稿システム。
はてなブログ投稿済み記事をXに自動ポストする。
1日3件まで・重複投稿防止・dry-run対応。

使い方:
  python x_poster.py              # 未投稿記事を投稿（1日3件まで）
  python x_poster.py --dry-run    # 確認のみ（実際には投稿しない）
  python x_poster.py --stats      # 統計表示
"""
import re
import json
import argparse
from pathlib import Path
from datetime import datetime, date

AGENT_ROOT  = Path(__file__).parent
HATENA_LOG  = AGENT_ROOT / "memory" / "hatena_publish_log.json"
X_LOG       = AGENT_ROOT / "memory" / "x_post_log.json"
CONFIG_FILE = AGENT_ROOT / "config" / "x_config.json"

# 1日あたりの最大投稿件数
DAILY_LIMIT = 3

# ハッシュタグ（記事に付与する共通タグ）
HASHTAGS = "#Python #プログラミング #エンジニア"

# X API v2 エンドポイント
TWEET_ENDPOINT = "https://api.twitter.com/2/tweets"


def _load_config() -> dict:
    """設定ファイルからAPIキーを読み込む"""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def _load_hatena_log() -> dict:
    if HATENA_LOG.exists():
        return json.loads(HATENA_LOG.read_text(encoding="utf-8"))
    return {}


def _load_x_log() -> dict:
    if X_LOG.exists():
        return json.loads(X_LOG.read_text(encoding="utf-8"))
    return {}


def _save_x_log(log: dict):
    X_LOG.parent.mkdir(exist_ok=True)
    X_LOG.write_text(
        json.dumps(log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _count_today_posts(log: dict) -> int:
    """今日の投稿件数を返す"""
    today = date.today().isoformat()
    return sum(
        1 for entry in log.values()
        if entry.get("posted_at", "")[:10] == today
    )


def _make_tweet(title: str, url: str) -> str:
    """ツイート本文を生成する（280文字以内）"""
    body = f"📘【新記事】{title}\n\n{url}\n\n{HASHTAGS}"
    # 280文字を超える場合はタイトルを切り詰める
    if len(body) > 280:
        max_title = 280 - len(f"📘【新記事】\n\n{url}\n\n{HASHTAGS}") - 3
        title_short = title[:max_title] + "…"
        body = f"📘【新記事】{title_short}\n\n{url}\n\n{HASHTAGS}"
    return body


def post_tweet(tweet_text: str, config: dict) -> dict:
    """
    X API v2 でツイートを投稿する。
    Returns: {"success": bool, "tweet_id": str}
    """
    try:
        from requests_oauthlib import OAuth1Session
        oauth = OAuth1Session(
            client_key=config["api_key"],
            client_secret=config["api_key_secret"],
            resource_owner_key=config["access_token"],
            resource_owner_secret=config["access_token_secret"],
        )
        payload = {"text": tweet_text}
        response = oauth.post(
            TWEET_ENDPOINT,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        tweet_id = data.get("data", {}).get("id", "")
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"
        print(f"  ✅ X投稿完了: {tweet_url}")
        return {"success": True, "tweet_id": tweet_id, "tweet_url": tweet_url}
    except Exception as e:
        print(f"  ❌ X投稿失敗: {e}")
        return {"success": False, "error": str(e)}


def post_articles(dry_run: bool = False) -> dict:
    """はてな投稿済みで未X投稿の記事をXに投稿する（1日3件まで）"""
    config      = _load_config()
    hatena_log  = _load_hatena_log()
    x_log       = _load_x_log()
    today_count = _count_today_posts(x_log)
    remaining   = DAILY_LIMIT - today_count

    # 未投稿記事を抽出（はてなに投稿済み、かつXに未投稿）
    unpublished = [
        (fname, meta)
        for fname, meta in hatena_log.items()
        if fname not in x_log and meta.get("url")
    ]

    print(f"\n{'='*50}")
    print(f"  X自動投稿")
    print(f"  今日の投稿済み: {today_count}件 / 上限: {DAILY_LIMIT}件")
    print(f"  投稿可能残数: {remaining}件")
    print(f"  未投稿記事: {len(unpublished)}件")
    print(f"{'='*50}\n")

    if remaining <= 0:
        print("  ℹ️  本日の投稿上限に達しました")
        return {"success": 0, "skipped": len(unpublished), "limit_reached": True}

    if not unpublished:
        print("  ℹ️  投稿する記事がありません")
        return {"success": 0, "skipped": 0}

    results = {"success": 0, "skipped": 0, "failed": 0}
    targets = unpublished[:remaining]  # 残数だけ取る

    for fname, meta in targets:
        title = meta.get("title", fname)
        url   = meta.get("url", "")
        tweet = _make_tweet(title, url)

        print(f"  🐦 {title[:40]}")
        print(f"     {url}")
        print(f"  ツイート内容 ({len(tweet)}文字):")
        print(f"  ---\n{tweet}\n  ---")

        if dry_run:
            print(f"  🔍 DRY RUN: 投稿スキップ")
            results["skipped"] += 1
            continue

        if not config.get("api_key"):
            print(f"  ❌ APIキー未設定 → スキップ")
            results["skipped"] += 1
            continue

        result = post_tweet(tweet, config)
        if result["success"]:
            x_log[fname] = {
                "title":     title,
                "hatena_url": url,
                "tweet_id":  result.get("tweet_id", ""),
                "tweet_url": result.get("tweet_url", ""),
                "tweet":     tweet,
                "posted_at": datetime.now().isoformat(),
            }
            _save_x_log(x_log)
            results["success"] += 1
        else:
            results["failed"] += 1

    return results


def show_stats():
    """投稿統計を表示する"""
    hatena_log = _load_hatena_log()
    x_log      = _load_x_log()
    today      = date.today().isoformat()
    today_count = _count_today_posts(x_log)

    print(f"\n## X投稿状況")
    print(f"はてな投稿済み: {len(hatena_log)}件")
    print(f"X投稿済み:     {len(x_log)}件")
    print(f"未投稿:        {len(hatena_log) - len(x_log)}件")
    print(f"本日投稿済み:  {today_count}/{DAILY_LIMIT}件")

    if x_log:
        print("\n### 最新5件")
        for fname, meta in list(x_log.items())[-5:]:
            print(f"  - {meta.get('title', '')[:40]}")
            print(f"    {meta.get('tweet_url', meta.get('hatena_url', ''))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X自動投稿")
    parser.add_argument("--dry-run", action="store_true", help="実際には投稿しない")
    parser.add_argument("--stats",   action="store_true", help="統計表示")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        config = _load_config()
        if not config.get("api_key") and not args.dry_run:
            print("❌ APIキーが設定されていません")
            print(f"以下のファイルを作成してください: {CONFIG_FILE}")
            print('{\n  "api_key":      "YOUR_API_KEY",\n  "api_secret":   "YOUR_API_SECRET",\n  "access_token": "YOUR_ACCESS_TOKEN",\n  "access_secret":"YOUR_ACCESS_SECRET"\n}')
            exit(1)
        results = post_articles(dry_run=args.dry_run)
        if not args.dry_run:
            print(f"\n完了: 投稿={results['success']} スキップ={results['skipped']} 失敗={results.get('failed', 0)}")
