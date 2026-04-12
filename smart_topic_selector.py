"""
実行日時に応じて適切な記事タイプとトピックを自動選択する。

ルール:
  平日（祝日除く）かつ 6:30以降 → 当日の市況まとめ
  土曜日                        → 金曜日の市況まとめ
  日曜日                        → 土曜日のニュースまとめ
  月曜日 6:30以前               → 日曜日のニュースまとめ
  祝日（平日扱いの祝日）         → 前営業日の市況まとめ
  祝日の翌平日 6:30以前          → 前日のニュースまとめ
"""
import jpholiday
from datetime import datetime, date, timedelta


def _is_market_open(d: date) -> bool:
    """その日が市場営業日か（平日かつ祝日でない）"""
    if d.weekday() >= 5:  # 土日
        return False
    if jpholiday.is_holiday(d):
        return False
    return True


def _prev_business_day(d: date) -> date:
    """直前の営業日を返す"""
    prev = d - timedelta(days=1)
    while not _is_market_open(prev):
        prev -= timedelta(days=1)
    return prev


def select_article_type(now: datetime = None) -> dict:
    """
    実行日時に応じて記事タイプとトピックを返す。

    Returns:
        {
            "genre": "finance_news" | "news_digest",
            "topic": str,
            "target_date": date,
            "reason": str
        }
    """
    if now is None:
        now = datetime.now()

    today = now.date()
    weekday = today.weekday()  # 0=月 〜 6=日
    hour = now.hour
    minute = now.minute
    is_early_morning = (hour < 6) or (hour == 6 and minute < 30)

    def fmt_date(d: date) -> str:
        return f"{d.year}年{d.month:02d}月{d.day:02d}日"

    def market_topic(d: date) -> dict:
        return {
            "genre": "finance_news",
            "topic": f"本日の日本株市況まとめ（{fmt_date(d)}）",
            "target_date": d,
            "reason": f"{fmt_date(d)}の市況まとめ"
        }

    def news_topic(d: date) -> dict:
        return {
            "genre": "news_digest",
            "topic": f"今日のニュースまとめ（{fmt_date(d)}）",
            "target_date": d,
            "reason": f"{fmt_date(d)}のニュースまとめ（市場休業日）"
        }

    # 月曜日早朝 → 日曜日のニュースまとめ
    if weekday == 0 and is_early_morning:
        sunday = today - timedelta(days=1)
        return news_topic(sunday)

    # 日曜日 → 土曜日のニュースまとめ
    if weekday == 6:
        saturday = today - timedelta(days=1)
        return news_topic(saturday)

    # 土曜日 → 金曜日の市況まとめ
    if weekday == 5:
        friday = _prev_business_day(today)
        return market_topic(friday)

    # 祝日の場合
    if jpholiday.is_holiday(today):
        yesterday = today - timedelta(days=1)
        # 前日も祝日・土日 → 連続休暇の2日目以降 → 前日のニュースまとめ
        if not _is_market_open(yesterday):
            return news_topic(yesterday)
        # 前日は営業日 → 連続休暇の初日 → 前日市況まとめ
        else:
            return market_topic(yesterday)

    # 平日早朝 → 前日のニュースまとめ（前日が休日の場合）
    if is_early_morning:
        yesterday = today - timedelta(days=1)
        if not _is_market_open(yesterday):
            return news_topic(yesterday)

    # 通常平日 → 当日の市況まとめ
    return market_topic(today)


if __name__ == "__main__":
    result = select_article_type()
    print(f"ジャンル: {result['genre']}")
    print(f"トピック: {result['topic']}")
    print(f"理由: {result['reason']}")
