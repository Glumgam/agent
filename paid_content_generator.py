"""
有料記事生成システム。
無料記事（Zenn）と有料記事（はてな）の差別化を管理する。
有料コンテンツの要素:
- 詳細な分析データ（グラフ・数値）
- 実践的なコード（コピペで使える）
- 相関分析・トラッキングデータ
- 法務リスク情報
- 専門家レベルの解説
"""
from pathlib import Path
from datetime import datetime

AGENT_ROOT = Path(__file__).parent

# =====================================================
# 有料コンテンツの差別化定義
# =====================================================
PAID_VALUE_MAP = {
    "finance_news": {
        "free": [
            "市場概況（日経平均・主要指数）",
            "本日のニュース3〜5件",
            "値動きの簡単な紹介",
        ],
        "paid": [
            "相関分析グラフ（銘柄×為替・原油・米株）",
            "相関変化トラッキング（前回比での変化検知）",
            "法務・行政処分リスク情報（金融庁・公取委）",
            "適時開示の詳細分類（ポジティブ/ネガティブ/中立）",
            "企業採用動向から読む経営戦略",
            "マクロ環境の詳細分析",
            "FAQ（投資初心者向け解説）",
        ],
        "price": 200,
        "tagline": "AIが毎日自動収集・分析する投資情報レポート",
    },
    "python_tips": {
        "free": [
            "概念の説明",
            "基本的なコード例1つ",
            "主要なポイントの紹介",
        ],
        "paid": [
            "実践的なコード例（コピペで使える）",
            "エラー対処法とデバッグのコツ",
            "パフォーマンス最適化",
            "実務での応用例",
            "関連ライブラリとの組み合わせ",
            "練習問題と解答",
        ],
        "price": 100,
        "tagline": "実務で使えるPythonテクニック詳細解説",
    },
    "ai_tools": {
        "free": [
            "ツールの概要と特徴",
            "基本的な使い方",
        ],
        "paid": [
            "実装コード（完全版）",
            "カスタマイズ方法",
            "他ツールとの比較",
            "実務での活用事例",
            "トラブルシューティング",
        ],
        "price": 150,
        "tagline": "AIツール完全活用ガイド",
    },
}


# =====================================================
# 有料記事フッター生成
# =====================================================
def generate_paid_footer(genre_id: str) -> str:
    """はてな有料記事のフッターを生成する"""
    info       = PAID_VALUE_MAP.get(genre_id, {})
    paid_items = info.get("paid", [])
    price      = info.get("price", 100)
    tagline    = info.get("tagline", "詳細解説記事")

    if not paid_items:
        return ""

    # 月曜日は無料フッター
    if genre_id == "finance_news" and is_monday_free_day():
        return """
---
## 📰 毎週月曜日は無料公開
週の始まりに市場情報をお届けするため、月曜日の記事は無料公開しています。
火曜日〜金曜日の記事では以下の詳細データも掲載しています：

- 📈 相関分析グラフ
- ⚖️ 法務・行政処分リスク情報
- 💼 企業採用動向から読む経営戦略

👉 [はてなブログで購読する](https://granking.hatenablog.com)

---
"""

    if genre_id == "finance_news":
        return """
---
## 📋 この記事について
**AIが毎日自動収集・分析する投資情報レポート**

本記事に含まれる情報：
- ✅ 法務・行政処分リスク情報（金融庁・公取委）
- ✅ マクロ経済環境の詳細分析（為替・原油・米株・VIX）
- ✅ 適時開示の分類結果
- ✅ 値上がり・値下がりランキング解説
- ✅ FAQ（投資初心者向け解説）

> 💡 Zenn版では概要のみを掲載しています。

---
"""
    items_text = "\n".join(f"- ✅ {item}" for item in paid_items)
    return f"""
---
## 📋 この記事について
**{tagline}**

本記事（詳細版）に含まれる内容：
{items_text}

> 💡 Zenn版では概要のみを掲載しています。

---
"""


def generate_free_teaser(
    genre_id: str,
    paid_url: str = "",
) -> str:
    """Zenn無料版の末尾ティーザーを生成する"""
    info       = PAID_VALUE_MAP.get(genre_id, {})
    paid_items = info.get("paid", [])
    price      = info.get("price", 100)

    if not paid_items:
        return ""

    # 有料コンテンツの一部だけ見せる（2〜3件）
    teaser_items = paid_items[:3]
    items_text   = "\n".join(f"- 🔒 {item}" for item in teaser_items)
    more_count   = len(paid_items) - len(teaser_items)

    return f"""
---
## 📊 詳細版（はてなブログ）で公開中
以下のコンテンツは詳細版でご覧いただけます：
{items_text}
{'- 🔒 他' + str(more_count) + '項目...' if more_count > 0 else ''}

👉 [詳細版を読む]({paid_url if paid_url else 'https://granking.hatenablog.com'})

---
"""


# =====================================================
# 月曜無料判定
# =====================================================
def is_monday_free_day() -> bool:
    """
    月曜日（週明け）は無料公開にする。
    週の最初に無料で集客し、有料読者を増やす戦略。
    """
    return datetime.now().weekday() == 0  # 0 = 月曜日


# =====================================================
# 記事品質スコアから有料適性を判定
# =====================================================
def is_suitable_for_paid(
    content: str,
    score: int,
    genre_id: str,
) -> bool:
    """
    記事が有料公開に適しているか判定する。
    月曜日の投資記事は無料公開。
    基準:
    - 品質スコア 8/10 以上
    - 2000文字以上
    - 免責事項が含まれる（投資記事）
    """
    # 月曜日の投資記事は無料
    if genre_id == "finance_news" and is_monday_free_day():
        return False
    if score < 8:
        return False
    if len(content) < 2000:
        return False
    if genre_id == "finance_news" and "免責事項" not in content:
        return False
    return True


def generate_paid_label(genre_id: str, score: int) -> str:
    """記事の有料ラベルを生成する"""
    info  = PAID_VALUE_MAP.get(genre_id, {})
    price = info.get("price", 100)

    # 月曜日は無料ラベル
    if genre_id == "finance_news" and is_monday_free_day():
        return "📰 週明け無料記事（毎週月曜公開）"

    if score >= 9:
        return f"💎 プレミアム記事（{price}円）"
    elif score >= 8:
        return f"📊 詳細分析記事（{price}円）"
    else:
        return "📝 無料記事"
