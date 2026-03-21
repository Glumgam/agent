"""
既読URL記録システム。
同じURLを重複して収集しないようにする。
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

AGENT_ROOT  = Path(__file__).parent
SEEN_FILE   = AGENT_ROOT / "memory" / "seen_urls.json"
EXPIRE_DAYS = 7   # 7日後に再収集可能


def _load() -> dict:
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(data: dict):
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_seen(url: str) -> bool:
    """URLが既読かどうかを確認する（EXPIRE_DAYS日以内）"""
    data = _load()
    key  = hashlib.md5(url.encode()).hexdigest()
    if key not in data:
        return False
    try:
        seen_at = datetime.fromisoformat(data[key])
        return datetime.now() - seen_at < timedelta(days=EXPIRE_DAYS)
    except Exception:
        return False


def mark_seen(url: str):
    """URLを既読として記録する"""
    data = _load()
    key  = hashlib.md5(url.encode()).hexdigest()
    data[key] = datetime.now().isoformat()
    # 1000件超えたら古い100件を削除
    if len(data) > 1000:
        sorted_items = sorted(data.items(), key=lambda x: x[1])
        data = dict(sorted_items[100:])
    _save(data)


def filter_new(items: list, url_key: str = "url") -> list:
    """
    リストから未読のアイテムだけを返す。
    items: [{"url": "...", ...}, ...]
    """
    new_items = []
    for item in items:
        url = item.get(url_key, "") or item.get("link", "") or str(item)
        if not is_seen(url):
            new_items.append(item)
            mark_seen(url)
    return new_items


def get_stats() -> dict:
    """統計情報を返す"""
    data = _load()
    return {
        "total_seen": len(data),
        "file": str(SEEN_FILE),
    }


if __name__ == "__main__":
    mark_seen("https://example.com/test")
    print(f"is_seen: {is_seen('https://example.com/test')}")
    print(f"is_seen (new): {is_seen('https://example.com/other')}")
    print(f"stats: {get_stats()}")
    print("✅ seen_urls OK")
