"""
SNS代替データ収集システム。

収集ソース:
- Yahoo掲示板（株式板）: 個別銘柄の投資家コメント感情分析
- Reddit (JapanFinance・japanstocks・investing): 海外投資家視点
- はてなブックマーク: 国内注目記事

信頼度: low（クロスチェック必須）
買い推奨・売り推奨表現は絶対に生成しない。
個別コメントは転載せず感情傾向のみ記録する。
"""
import re
import json
import requests
import feedparser
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent
SOCIAL_DIR = AGENT_ROOT / "knowledge" / "social"
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# UI・システム系テキストを除外するキーワード
_UI_SKIP = {
    "ポートフォリオ", "マイページ", "投稿する", "ログイン", "利用規約",
    "プライバシー", "ヘルプ", "キャンセル", "報告", "返信", "JavaScript",
    "リニューアル", "以前の掲示板", "感情の割合", "参考になりました",
}

# 感情分析キーワード
_POSITIVE_WORDS = [
    "上がる", "上昇", "強い", "好調", "期待", "買い", "反発", "底打ち",
    "割安", "爆上", "好業績", "増益", "配当", "良い", "プラス", "伸び",
]
_NEGATIVE_WORDS = [
    "下がる", "下落", "弱い", "不安", "心配", "売り", "暴落", "天井",
    "割高", "損失", "減益", "悪化", "危うい", "マイナス", "崩れ",
]


# =====================================================
# Yahoo掲示板（株式板）
# =====================================================
def fetch_yahoo_bbs(code: str, max_posts: int = 30) -> list:
    """
    Yahoo掲示板から銘柄コードのコメントを取得する。
    感情分析用のみ。テキストは保存するが記事には転載しない。
    """
    try:
        url  = f"https://finance.yahoo.co.jp/quote/{code}.T/bbs"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        # <article class="_BbsItem..."> からコメントを抽出
        items = re.findall(
            r'<article class="_BbsItem[^"]*">(.*?)</article>',
            resp.text, re.DOTALL,
        )
        posts = []
        for item in items[:max_posts]:
            text = re.sub(r'<[^>]+>', ' ', item)
            text = re.sub(r'\s+', ' ', text).strip()
            # UI テキストを除外
            if any(s in text for s in _UI_SKIP):
                # コメント本文だけ残す（番号・日付の後のテキスト）
                m = re.search(
                    r'No\.\s*\d+\s+[\d/]+\s+[\d:]+\s+(?:報告\s+)?(?:>>\s*\d+\s+)?(.{10,200}?)(?:\s*返信|\s*投資の参考)',
                    text,
                )
                if m:
                    posts.append(m.group(1).strip())
            else:
                if len(text) > 10:
                    posts.append(text[:200])

        return [p for p in posts if len(p) > 8][:max_posts]
    except Exception as e:
        return []


def analyze_bbs_sentiment(posts: list, code: str = "") -> dict:
    """
    掲示板コメントの感情傾向を分析する。
    個別コメントは転載せず、集計結果のみ返す。
    """
    if not posts:
        return {
            "code":       code,
            "sentiment":  "データなし",
            "post_count": 0,
            "note":       "Yahoo掲示板取得不可",
        }

    pos = sum(1 for p in posts for w in _POSITIVE_WORDS if w in p)
    neg = sum(1 for p in posts for w in _NEGATIVE_WORDS if w in p)
    total = pos + neg

    if total == 0:
        sentiment = "中立"
    elif pos > neg * 1.5:
        sentiment = "強気傾向"
    elif neg > pos * 1.5:
        sentiment = "弱気傾向"
    else:
        sentiment = "中立"

    return {
        "code":        code,
        "sentiment":   sentiment,
        "post_count":  len(posts),
        "pos_signals": pos,
        "neg_signals": neg,
        "note":        "掲示板コメントの感情傾向（参考程度）",
    }


# =====================================================
# Reddit（JSON API・APIキー不要）
# =====================================================
def fetch_reddit(subreddit: str, max_posts: int = 5) -> list:
    """
    Reddit から hot 投稿を JSON API で取得する。
    """
    try:
        url  = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={max_posts}"
        resp = requests.get(
            url,
            headers={**HEADERS, "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        posts = []
        for child in resp.json().get("data", {}).get("children", []):
            d     = child.get("data", {})
            title = d.get("title", "").strip()
            score = d.get("score", 0)
            url_  = f"https://reddit.com{d.get('permalink', '')}"
            if title and score > 0:
                posts.append({
                    "title":             title,
                    "score":             score,
                    "url":               url_,
                    "source":            f"Reddit r/{subreddit}",
                    "credibility":       "low",
                    "credibility_score": 0.3,
                })
        return posts
    except Exception as e:
        print(f"  ⚠️ Reddit r/{subreddit}: {e}")
        return []


def fetch_investment_reddit() -> list:
    """投資関連 Reddit を収集する"""
    subreddits = [
        "JapanFinance",
        "japanstocks",
        "investing",
        "stocks",
        "worldnews",
    ]
    all_posts = []
    ok = 0
    for sub in subreddits:
        posts = fetch_reddit(sub, max_posts=5)
        if posts:
            all_posts.extend(posts)
            ok += 1
            print(f"  ✅ Reddit r/{sub}: {len(posts)}件")
        else:
            print(f"  ⚠️ Reddit r/{sub}: 0件")
    print(f"  [Reddit] {ok}/{len(subreddits)} subreddits")
    return all_posts


# =====================================================
# はてなブックマーク（RSS）
# =====================================================
HATENA_CATEGORY_URLS = {
    "finance": "https://b.hatena.ne.jp/hotentry/money.rss",
    "tech":    "https://b.hatena.ne.jp/hotentry/it.rss",
    "general": "https://b.hatena.ne.jp/hotentry/general.rss",
}


def fetch_hatena_hotentries(category: str = "finance") -> list:
    """はてなブックマークの人気エントリを RSS から取得する"""
    try:
        url  = HATENA_CATEGORY_URLS.get(category, HATENA_CATEGORY_URLS["general"])
        feed = feedparser.parse(url)
        posts = []
        for entry in feed.entries[:10]:
            title   = entry.get("title", "").strip()
            link    = entry.get("link", "")
            summary = re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:200].strip()
            if title:
                posts.append({
                    "title":             title,
                    "link":              link,
                    "summary":           summary,
                    "source":            f"はてなブックマーク({category})",
                    "credibility":       "medium",
                    "credibility_score": 0.6,
                })
        print(f"  ✅ はてなブックマーク({category}): {len(posts)}件")
        return posts
    except Exception as e:
        print(f"  ⚠️ はてなブックマーク({category}): {e}")
        return []


# =====================================================
# 銘柄別SNS感情分析
# =====================================================
def analyze_stock_social_sentiment(
    codes: list,
    high_cred_news: list = None,
) -> dict:
    """
    主要銘柄の SNS 感情傾向を分析する。
    Returns: {銘柄コード: 感情分析結果}
    """
    results = {}
    for code in codes[:5]:  # 最大5銘柄
        posts     = fetch_yahoo_bbs(code, max_posts=30)
        sentiment = analyze_bbs_sentiment(posts, code)
        results[code] = sentiment
        label = sentiment["sentiment"]
        count = sentiment["post_count"]
        print(f"  ✅ Yahoo BBS {code}: {label}（{count}件）")
    return results


# =====================================================
# メイン収集
# =====================================================
def collect_social_data(
    stock_codes: list = None,
    high_cred_news: list = None,
) -> dict:
    """SNS データを収集して返す"""
    print("\n  💬 SNSデータ収集中...")

    data = {
        "date":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "reddit": fetch_investment_reddit(),
        "hatena": fetch_hatena_hotentries("finance"),
    }

    # 銘柄別感情分析
    if stock_codes:
        data["stock_sentiment"] = analyze_stock_social_sentiment(
            stock_codes, high_cred_news
        )
    else:
        data["stock_sentiment"] = {}

    # 保存
    SOCIAL_DIR.mkdir(parents=True, exist_ok=True)
    stamp    = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = SOCIAL_DIR / f"{stamp}_social.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  💾 保存: {out_path.name}")
    return data


def format_social_for_article(data: dict) -> str:
    """SNS データを記事挿入用 Markdown に変換する"""
    lines = [
        "## 💬 市場参加者の声（SNS・掲示板）\n",
        "> ⚠️ 以下は SNS・掲示板の傾向まとめです。",
        "> 個人の意見であり、投資判断の根拠にしないでください。\n",
    ]

    # Reddit 注目投稿（スコア降順・上位3件）
    reddit = sorted(
        data.get("reddit", []),
        key=lambda x: x.get("score", 0),
        reverse=True,
    )
    if reddit:
        lines.append("### 🌐 Reddit（海外投資家の視点）")
        for post in reddit[:3]:
            title = post.get("title", "")
            score = post.get("score", 0)
            sub   = post.get("source", "")
            lines.append(f"- **[{sub}]** {title[:80]}（スコア: {score}）")
        lines.append("")

    # はてなブックマーク
    hatena = data.get("hatena", [])
    if hatena:
        lines.append("### 📌 はてなブックマーク（国内注目記事）")
        for post in hatena[:3]:
            title = post.get("title", "")
            lines.append(f"- {title}")
        lines.append("")

    # 銘柄別感情傾向
    sentiments = data.get("stock_sentiment", {})
    if sentiments:
        lines.append("### 📊 掲示板の感情傾向（参考）")
        for code, s in sentiments.items():
            sentiment  = s.get("sentiment", "N/A")
            post_count = s.get("post_count", 0)
            pos        = s.get("pos_signals", 0)
            neg        = s.get("neg_signals", 0)
            if post_count > 0:
                lines.append(
                    f"- 銘柄 {code}: **{sentiment}**"
                    f"（{post_count}件集計 / ポジ信号:{pos} ネガ信号:{neg}）"
                )
            else:
                lines.append(f"- 銘柄 {code}: データなし")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SNS代替データ収集")
    parser.add_argument("--codes", nargs="*", default=["7203", "6758"],
                        help="感情分析する銘柄コード（スペース区切り）")
    args = parser.parse_args()

    data = collect_social_data(stock_codes=args.codes)
    print()
    print(format_social_for_article(data))
