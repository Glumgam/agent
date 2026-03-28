"""
content/ 直下のMarkdownファイルをジャンル別サブディレクトリに再分類する。
一度だけ実行すればよい移行スクリプト。
"""
import shutil
from pathlib import Path

AGENT_ROOT = Path("/Volumes/ESD-EHA/agent")
CONTENT    = AGENT_ROOT / "content"

# (判定関数, 移動先ディレクトリ) のリスト（上から順に評価）
RULES = [
    # 投資・市場記事
    (
        lambda f: any(kw in f for kw in [
            "市況", "ランキング", "株", "優待", "配当",
            "日本株", "nikkei", "finance",
        ]),
        CONTENT / "finance",
    ),
    # 技術記事
    (
        lambda f: any(kw in f for kw in [
            "python", "ai", "llm", "ollama", "coder",
            "security", "sentence", "transformer",
            "pathlib", "logging", "decorator", "generator",
            "comprehension", "dataclass", "namedtuple",
            "automation", "git", "excel", "api", "rag",
            "httpx", "pydantic", "rich", "typer", "loguru",
        ]),
        CONTENT / "tech",
    ),
]


def reorganize():
    moved_counts = {"finance": 0, "tech": 0, "general": 0, "skipped": 0}

    for md_file in sorted(CONTENT.glob("*.md")):
        if md_file.name.startswith("._"):
            moved_counts["skipped"] += 1
            continue

        fname = md_file.name.lower()
        dest  = CONTENT / "general"  # デフォルト

        for rule_fn, target_dir in RULES:
            if rule_fn(fname):
                dest = target_dir
                break

        dest.mkdir(parents=True, exist_ok=True)
        target_path = dest / md_file.name

        # 重複ファイル名の回避
        if target_path.exists():
            stem    = md_file.stem
            suffix  = md_file.suffix
            counter = 1
            while target_path.exists():
                target_path = dest / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.move(str(md_file), str(target_path))
        genre = dest.name
        moved_counts[genre] = moved_counts.get(genre, 0) + 1
        print(f"  [{genre:8s}] {md_file.name}")

    print(f"\n{'='*50}")
    print(f"  再分類完了")
    print(f"  finance : {moved_counts.get('finance', 0)}件")
    print(f"  tech    : {moved_counts.get('tech', 0)}件")
    print(f"  general : {moved_counts.get('general', 0)}件")
    print(f"  skipped : {moved_counts.get('skipped', 0)}件")
    print(f"{'='*50}")


if __name__ == "__main__":
    reorganize()
