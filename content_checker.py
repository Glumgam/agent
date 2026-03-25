"""
記事品質・重複チェックシステム。
チェック内容:
1. 重複チェック（タイトル一致・内容類似）
2. トピック被り検出（同じキーワードの記事が多すぎる）
3. 品質スコア計算
"""
import re
import json
from pathlib import Path

AGENT_ROOT  = Path(__file__).parent
CONTENT_DIR = AGENT_ROOT / "content"
DEDUP_DB    = AGENT_ROOT / "memory" / "content_dedup.json"


# =====================================================
# 重複チェック
# =====================================================

def _load_dedup_db() -> dict:
    if DEDUP_DB.exists():
        try:
            return json.loads(DEDUP_DB.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"titles": {}, "fingerprints": {}}


def _save_dedup_db(db: dict):
    DEDUP_DB.parent.mkdir(exist_ok=True)
    DEDUP_DB.write_text(
        json.dumps(db, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fingerprint(content: str) -> str:
    """記事の特徴量を抽出（先頭・中間・末尾の組み合わせ）"""
    # コードブロックと空白を除去してから比較
    clean = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    clean = re.sub(r"\s+", " ", clean).strip()
    mid   = len(clean) // 2
    return clean[:100] + clean[mid:mid + 100] + clean[-100:]


def _title_similarity(a: str, b: str) -> float:
    """2つのタイトルの類似度を計算（単語ベース Jaccard係数）"""
    words_a = set(re.sub(r"[^\w]", " ", a.lower()).split())
    words_b = set(re.sub(r"[^\w]", " ", b.lower()).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union        = words_a | words_b
    return len(intersection) / len(union)


def is_duplicate(title: str, content: str, variant: str = "") -> tuple:
    """
    重複チェック。
    variant: "zenn" / "hatena" / "" — 同じvariantの記事のみを重複とみなす。
    日付入りタイトル（日次トピック）は類似チェックをスキップし、
    同variant・同タイトルの完全一致のみを重複とみなす。
    Returns: (is_dup: bool, reason: str)
    """
    db = _load_dedup_db()

    # 日次トピック判定（日付入りタイトル）
    has_date = bool(re.search(
        r'\d{4}年\d{1,2}月\d{1,2}日|\d{4}/\d{2}/\d{2}', title
    ))

    # variantが指定されている場合は同じsuffixのファイルのみチェック
    suffix = f"_{variant}.md" if variant else ""

    def _same_variant(existing_path: str) -> bool:
        """既存パスが同じvariantか（variantなし時は全てTrue）"""
        if not suffix:
            return True
        return existing_path.endswith(suffix)

    # タイトル完全一致
    if title in db["titles"]:
        existing_path = db["titles"][title]
        if _same_variant(existing_path):
            return True, f"タイトル重複: '{title}' (既存: {existing_path})"

    # タイトル類似（日次トピックはスキップ — 日付が違えば別記事）
    if not has_date:
        for existing_title, existing_path in db["titles"].items():
            if not _same_variant(existing_path):
                continue
            similarity = _title_similarity(title, existing_title)
            if similarity > 0.8:
                return True, (
                    f"タイトル類似: '{title}' ≈ '{existing_title}'"
                    f" ({similarity:.0%})"
                )

    # 内容フィンガープリント
    fp = _fingerprint(content)
    if fp in db["fingerprints"]:
        return True, f"内容重複: {db['fingerprints'][fp]}"

    return False, "OK"


def register_article(title: str, content: str, path: str):
    """記事をデータベースに登録する"""
    db = _load_dedup_db()
    db["titles"][title]                   = path
    db["fingerprints"][_fingerprint(content)] = path
    _save_dedup_db(db)


def check_topic_saturation(genre_id: str, topic: str) -> tuple:
    """
    同ジャンル・同トピックの記事が多すぎないかチェック。
    日本語は空白区切りがないため、ASCII英数字キーワードのみで判定する。
    Returns: (is_saturated: bool, reason: str)
    """
    if not DEDUP_DB.exists():
        return False, "OK"
    db     = _load_dedup_db()
    titles = list(db["titles"].keys())

    # 汎用すぎるキーワードは飽和チェックから除外
    _STOP_WORDS = {"python", "tips", "how", "the", "for", "with", "and"}

    # ASCII英数字のみのキーワードを抽出（4文字以上、ストップワード除外）
    ascii_keywords = [
        kw for kw in re.findall(r"[a-z][a-z0-9_]{3,}", topic.lower())
        if kw not in _STOP_WORDS
    ]

    for kw in ascii_keywords:
        count = sum(1 for t in titles if kw in t.lower())
        if count >= 3:
            return True, f"トピック飽和: '{kw}' に関する記事が {count} 件あります"

    return False, "OK"


# =====================================================
# 既存記事のスキャン・登録
# =====================================================

def scan_existing_articles() -> int:
    """既存の記事を全てデータベースに登録する"""
    db    = {"titles": {}, "fingerprints": {}}
    count = 0
    for md in sorted(CONTENT_DIR.glob("*.md")):
        if md.name.startswith("._"):
            continue
        try:
            content = md.read_text(encoding="utf-8", errors="ignore")
            title   = ""
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line.lstrip("# ").strip()
                    break
            if not title:
                title = md.stem
            fp                     = _fingerprint(content)
            db["titles"][title]    = md.name
            db["fingerprints"][fp] = md.name
            count += 1
        except Exception as e:
            print(f"  ⚠️ スキャンエラー: {md.name}: {e}")
    _save_dedup_db(db)
    print(f"✅ {count}件の記事をスキャン完了")
    return count


def show_stats() -> str:
    """重複DBの統計を表示"""
    if not DEDUP_DB.exists():
        return "重複DBなし（scan_existing_articles()を実行してください）"
    db = _load_dedup_db()
    return (
        f"## 記事重複DB\n"
        f"登録タイトル:     {len(db['titles'])}件\n"
        f"フィンガープリント: {len(db['fingerprints'])}件"
    )


if __name__ == "__main__":
    scan_existing_articles()
    print(show_stats())
