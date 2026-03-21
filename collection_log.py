"""
情報収集ログ。
何を収集したか・いつ収集したかを記録する。
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

AGENT_ROOT = Path(__file__).parent
LOG_FILE   = AGENT_ROOT / "logs" / "collection_log.jsonl"  # JSONLines形式


def log_collection(
    topic_id:   str,
    source:     str,
    query:      str,
    item_count: int,
    urls:       list = None,
    acquired:   list = None,
):
    """収集結果をJSONLinesで記録する"""
    LOG_FILE.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp":  datetime.now().isoformat(),
        "topic_id":   topic_id,
        "source":     source,
        "query":      query,
        "item_count": item_count,
        "urls":       urls or [],
        "acquired":   acquired or [],
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_recent_queries(topic_id: str, days: int = 3) -> list:
    """
    直近N日間に収集したクエリ一覧を返す。
    重複収集を避けるために使用する。
    """
    if not LOG_FILE.exists():
        return []
    cutoff  = datetime.now() - timedelta(days=days)
    queries = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if (entry.get("topic_id") == topic_id and
                        datetime.fromisoformat(entry["timestamp"]) > cutoff):
                    queries.append(entry["query"])
            except Exception:
                pass
    return queries


def show_summary(days: int = 1) -> str:
    """直近N日間の収集サマリーを返す"""
    if not LOG_FILE.exists():
        return "収集ログなし"
    cutoff = datetime.now() - timedelta(days=days)
    counts = defaultdict(int)
    skills: list = []
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if datetime.fromisoformat(entry["timestamp"]) > cutoff:
                    counts[entry["topic_id"]] += entry.get("item_count", 0)
                    skills.extend(entry.get("acquired", []))
            except Exception:
                pass
    lines = [f"## 収集サマリー（直近{days}日）"]
    for topic, count in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {topic}: {count}件")
    if skills:
        lines.append(f"獲得スキル: {skills}")
    return "\n".join(lines)


if __name__ == "__main__":
    log_collection("test", "news", "test query", 3, acquired=["skill_a"])
    print(show_summary(days=1))
    recent = get_recent_queries("test", days=1)
    print(f"recent queries: {recent}")
    print("✅ collection_log OK")
