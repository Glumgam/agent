"""
無料→有料の導線文自動生成システム。
Zenn（無料・概要）→ はてな（有料・詳細）への誘導文を
記事の内容に合わせて自動生成する。
設計思想:
- 「気になるけど足りない」状態を作る
- 有料記事の価値を具体的に示す
- 押しつけがましくない自然な文体
"""
from pathlib import Path
from datetime import datetime

AGENT_ROOT  = Path(__file__).parent
CONTENT_DIR = AGENT_ROOT / "content"

# =====================================================
# ジャンル別導線テンプレート
# =====================================================
UPSELL_TEMPLATES = {
    "finance_news": {
        "zenn_footer": """
---
## 📊 より詳しい分析はこちら
この記事では市場の概要をお伝えしました。
**はてなブログの詳細版**では以下を掲載しています：

- 📈 **相関分析グラフ**（値上がり銘柄×為替・原油の連動性）
- ⚖️ **法務・行政処分リスク情報**（金融庁・公取委の最新動向）
- 💼 **企業採用動向から読む経営戦略**
- 🔔 **相関変化トラッキング**（前回比での変化検知）

👉 [詳細版を読む（はてなブログ）]({hatena_url})

---
> ⚠️ 本記事は情報提供のみを目的としており、投資助言ではありません。
""",
        "hatena_header": """
> 📝 この記事はZennの概要版の詳細解説です。
> 概要版はこちら → [{zenn_title}]({zenn_url})

---
""",
    },
    "python_tips": {
        "zenn_footer": """
---
## 🔍 さらに深く学ぶ
この記事ではポイントを絞って解説しました。
**はてなブログの詳細版**では以下を掲載しています：

- 💻 **実践的なコード例**（コピペで使える実装）
- 🛠️ **エラー対処法とデバッグのコツ**
- 📦 **関連ライブラリとの組み合わせ**
- ⚡ **パフォーマンス最適化のテクニック**

👉 [詳細版を読む（はてなブログ）]({hatena_url})
""",
        "hatena_header": """
> 📝 この記事はZennの概要版の詳細解説です。
> 概要版はこちら → [{zenn_title}]({zenn_url})

---
""",
    },
    "finance_news_monday": {
        "zenn_footer": """
---
## 📰 週明け無料記事
今週も市場情報をお届けします。
**毎週月曜日は全文無料公開**しています。

火曜日以降の詳細分析版（相関グラフ・法務リスク情報など）は
はてなブログでご覧いただけます。

👉 [はてなブログで読む]({hatena_url})

---
> ⚠️ 本記事は情報提供のみを目的としており、投資助言ではありません。
""",
        "hatena_header": """
> 📝 この記事はZennの概要版の詳細解説です。
> 概要版はこちら → [{zenn_title}]({zenn_url})

---
""",
    },
    "default": {
        "zenn_footer": """
---
## 📖 詳細版はこちら
**はてなブログの詳細版**では、より深い解説と実践的な内容を掲載しています。

👉 [詳細版を読む（はてなブログ）]({hatena_url})
""",
        "hatena_header": """
> 📝 この記事はZennの概要版の詳細解説です。
> 概要版はこちら → [{zenn_title}]({zenn_url})

---
""",
    },
}

# =====================================================
# URLリンク管理
# =====================================================
def _load_link_db() -> dict:
    """Zenn↔はてなのリンクDBを読み込む"""
    link_file = AGENT_ROOT / "memory" / "article_links.json"
    if link_file.exists():
        import json
        try:
            return json.loads(link_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_link_db(db: dict):
    """リンクDBを保存する"""
    import json
    link_file = AGENT_ROOT / "memory" / "article_links.json"
    link_file.parent.mkdir(exist_ok=True)
    link_file.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def register_article_pair(
    topic: str,
    zenn_url: str = "",
    hatena_url: str = "",
    zenn_path: str = "",
    hatena_path: str = "",
):
    """Zenn・はてな記事のペアを登録する"""
    db = _load_link_db()
    db[topic] = {
        "topic":       topic,
        "zenn_url":    zenn_url,
        "hatena_url":  hatena_url,
        "zenn_path":   zenn_path,
        "hatena_path": hatena_path,
        "registered":  datetime.now().isoformat(),
    }
    _save_link_db(db)


# =====================================================
# 導線文生成
# =====================================================
def generate_upsell_text(
    topic: str,
    genre_id: str,
    variant: str,
    zenn_url: str = "",
    hatena_url: str = "",
    zenn_title: str = "",
) -> str:
    """
    記事の導線文を生成する。
    variant="zenn"   → はてなへの誘導文（フッター）
    variant="hatena" → Zennへの逆リンク（ヘッダー）
    """
    # 月曜日の投資記事は専用テンプレート
    from datetime import datetime as _dt
    if genre_id == "finance_news" and _dt.now().weekday() == 0:
        template_set = UPSELL_TEMPLATES.get(
            "finance_news_monday",
            UPSELL_TEMPLATES["finance_news"],
        )
    else:
        template_set = UPSELL_TEMPLATES.get(genre_id, UPSELL_TEMPLATES["default"])

    if variant == "zenn":
        template = template_set["zenn_footer"]
        return template.format(
            hatena_url=hatena_url or "（はてなブログで公開予定）",
            topic=topic,
        )
    else:
        template = template_set["hatena_header"]
        return template.format(
            zenn_url=zenn_url or "（Zennで公開中）",
            zenn_title=zenn_title or topic,
            topic=topic,
        )


def inject_upsell_into_article(
    content: str,
    topic: str,
    genre_id: str,
    variant: str,
    zenn_url: str = "",
    hatena_url: str = "",
    zenn_title: str = "",
) -> str:
    """
    記事に導線文を注入する。
    Zenn版:   免責事項の前 または 末尾の --- の前に誘導フッターを挿入
    はてな版: タイトル行（# ）の直後に逆リンクヘッダーを挿入
    """
    upsell = generate_upsell_text(
        topic, genre_id, variant,
        zenn_url, hatena_url, zenn_title
    )
    if not upsell:
        return content

    if variant == "zenn":
        # 免責事項の前に挿入（finance_news テンプレート内の免責事項を置換しない）
        if "⚠️ 免責事項" in content:
            content = content.replace(
                "⚠️ 免責事項",
                upsell.strip() + "\n\n⚠️ 免責事項",
                1,  # 最初の1箇所のみ
            )
        elif "\n---" in content:
            # 最後の --- の前に挿入
            last_hr = content.rfind("\n---")
            content = content[:last_hr] + "\n" + upsell.strip() + content[last_hr:]
        else:
            content += "\n" + upsell
    else:  # hatena
        # タイトル行（# で始まる行）の直後に挿入
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("# "):
                insert_idx = i + 1
                break
        lines.insert(insert_idx, "\n" + upsell.strip() + "\n")
        content = "\n".join(lines)

    return content
