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


# =====================================================
# 品質比較付き重複解決
# =====================================================

def _get_score_from_file(file_path: Path) -> int:
    """
    ファイルから品質スコアを読み取る。
    <!-- score:N --> コメントがなければ文字数から推定。
    """
    try:
        text = file_path.read_text(encoding="utf-8")
        m = re.search(r'<!--\s*score:(\d+)', text)
        if m:
            return int(m.group(1))
        # コメントがない古いファイル → 文字数から推定
        char_count = len(text)
        if char_count > 3000:
            return 9
        elif char_count > 1500:
            return 7
        else:
            return 5
    except Exception:
        return 7


def check_and_resolve_duplicate(
    new_content: str,
    new_score: int,
    new_path: Path,
    existing_path: Path,
    existing_score: int = None,
) -> dict:
    """
    重複タイトルが存在する場合、品質を比較して高品質な方を残す。

    Returns:
        {"action": "keep_new" | "keep_existing", "reason": str}
    """
    if existing_score is None:
        existing_score = _get_score_from_file(existing_path)

    if new_score > existing_score:
        try:
            existing_path.unlink()
            print(f"  🔄 品質比較: 新記事({new_score}点) > 既存({existing_score}点) → 既存を置換")
        except Exception as e:
            print(f"  ⚠️ 既存ファイル削除失敗: {e}")
        return {"action": "keep_new", "reason": f"新記事({new_score}点) > 既存({existing_score}点)"}

    elif new_score == existing_score:
        try:
            existing_len = len(existing_path.read_text(encoding="utf-8"))
            new_len      = len(new_content)
            if new_len > existing_len:
                existing_path.unlink()
                print(f"  🔄 同スコア({new_score}点)・文字数比較: 新({new_len}字) > 既存({existing_len}字) → 既存を置換")
                return {"action": "keep_new", "reason": "同スコアだが新記事の方が詳細"}
            else:
                print(f"  ⏭️ 同スコア・既存の方が詳細 → 新記事をスキップ")
                return {"action": "keep_existing", "reason": "同スコアだが既存記事の方が詳細"}
        except Exception:
            return {"action": "keep_existing", "reason": "比較失敗のため既存を維持"}

    else:
        print(f"  ⏭️ 品質比較: 既存({existing_score}点) >= 新記事({new_score}点) → スキップ")
        return {"action": "keep_existing", "reason": f"既存({existing_score}点) >= 新記事({new_score}点)"}


def check_duplicate(
    title: str,
    content: str,
    out_path: Path,
    score: int = 7,
) -> dict:
    """
    重複チェック。重複時は品質比較して処理を決定する。
    DBの登録・更新もここで行う。

    Returns:
        {"duplicate": bool, "action": str, "reason": str}
    """
    db     = _load_dedup_db()
    titles = db.get("titles", {})
    fp     = _fingerprint(content)

    # タイトル重複チェック
    if title in titles:
        existing_path = Path(titles[title])

        if not existing_path.exists():
            # 既存ファイルが消えている → 新規として扱う
            titles[title]   = str(out_path)
            db["fingerprints"][fp] = str(out_path)
            _save_dedup_db(db)
            return {"duplicate": False, "action": "keep_new", "reason": "既存ファイル消失のため新規登録"}

        result = check_and_resolve_duplicate(
            new_content=content,
            new_score=score,
            new_path=out_path,
            existing_path=existing_path,
        )

        if result["action"] == "keep_new":
            titles[title]   = str(out_path)
            db["fingerprints"][fp] = str(out_path)
            _save_dedup_db(db)
            return {"duplicate": False, "action": "keep_new", "reason": result["reason"]}
        else:
            return {"duplicate": True, "action": "keep_existing", "reason": result["reason"]}

    # フィンガープリント重複チェック
    if fp in db.get("fingerprints", {}):
        return {
            "duplicate": True,
            "action":    "keep_existing",
            "reason":    f"内容重複: {db['fingerprints'][fp]}",
        }

    # 新規 → 登録
    titles[title]   = str(out_path)
    db["titles"]    = titles
    db["fingerprints"][fp] = str(out_path)
    _save_dedup_db(db)
    return {"duplicate": False, "action": "new", "reason": "新規登録"}


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
    for md in sorted(CONTENT_DIR.rglob("*.md")):
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
