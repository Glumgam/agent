"""
Auto Skill Learning System（ゲットアビリティ機能）。
タスク完了時にスキルを自動抽出・保存し、
次回の類似タスクでヒントとして再利用する。

スキルDB: memory/skill_db.json
"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field

AGENT_ROOT = Path(__file__).parent
SKILL_DB   = AGENT_ROOT / "memory" / "skill_db.json"

# -------------------------
# データクラス
# -------------------------

@dataclass
class Skill:
    name:          str
    task_example:  str
    success_count: int
    last_used:     str          # ISO8601 UTC
    tools_used:    list[str]
    key_imports:   list[str]
    keywords:      list[str]
    summary:       str


# -------------------------
# 内部ユーティリティ
# -------------------------

def _load_db() -> dict:
    if not SKILL_DB.exists():
        return {"skills": {}}
    with open(SKILL_DB, encoding="utf-8") as f:
        return json.load(f)


def _save_db(data: dict) -> None:
    SKILL_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(SKILL_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recency_score(last_used: str) -> float:
    """最近使ったスキルに最大+10のボーナス。1日ごとに1ポイント減衰。"""
    if not last_used:
        return 0.0
    try:
        last = datetime.fromisoformat(last_used)
        now  = datetime.now(timezone.utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_days = (now - last).total_seconds() / 86400
        return max(0.0, 10.0 - age_days)
    except Exception:
        return 0.0


def _extract_keywords(task_description: str) -> list[str]:
    """タスク説明からキーワードを抽出する。"""
    # 小文字化してトークン分割
    text = task_description.lower()
    # 記号を空白に置換
    text = re.sub(r"[^a-z0-9\u3040-\u9fff\s]", " ", text)
    tokens = text.split()
    # ストップワード除外
    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "to", "of", "in", "for", "on", "with", "and", "or", "but",
        "that", "this", "it", "as", "at", "by", "from", "その", "して",
        "する", "した", "が", "を", "は", "に", "で", "の", "と", "へ",
        "な", "も", "た", "て", "い", "く", "し", "れ", "ない", "ある",
    }
    keywords = [t for t in tokens if t not in stopwords and len(t) >= 2]
    # 重複除去・先頭15件
    seen = set()
    result = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
        if len(result) >= 15:
            break
    return result


def _extract_imports(history: list[dict]) -> list[str]:
    """履歴中の create_file / edit_file の content から import 文を収集。"""
    imports = set()
    for h in history:
        action = h.get("action", {})
        if action.get("tool") not in ("create_file", "edit_file", "append_file"):
            continue
        content = action.get("content", "") or ""
        for line in content.splitlines():
            line = line.strip()
            m = re.match(r"^(?:import|from)\s+([\w.]+)", line)
            if m:
                pkg = m.group(1).split(".")[0]
                imports.add(pkg)
    # stdlib 除外（よく使うもの）
    stdlib = {
        "os", "sys", "re", "json", "math", "time", "datetime",
        "pathlib", "typing", "collections", "itertools", "functools",
        "subprocess", "io", "abc", "copy", "enum", "dataclasses",
    }
    return sorted(imports - stdlib)[:10]


def _extract_tools_used(history: list[dict]) -> list[str]:
    """履歴から使ったツール一覧を返す。"""
    seen = set()
    tools = []
    for h in history:
        t = h.get("action", {}).get("tool", "")
        if t and t not in seen and t not in ("_error", "_loop_fix"):
            seen.add(t)
            tools.append(t)
    return tools


def _generate_skill_name(task: str, imports: list) -> str:
    """パターンマッチでスキル名を生成する。マッチしない場合は意味のある単語を使う。"""
    task_lower = task.lower()
    imports_lower = [i.lower() for i in imports]

    patterns = [
        (["scraping", "スクレイピング", "html", "bs4", "beautifulsoup", "scrape", "crawl"], "web_scraping"),
        (["excel", "xlsx", "openpyxl", "spreadsheet"], "excel_operation"),
        (["csv", "pandas", "dataframe", "集計", "分析", "analyze", "analysis"], "data_analysis"),
        (["pdf", "reportlab", "pdfplumber"], "pdf_operation"),
        (["flask", "fastapi", "web app", "server", "route"], "web_app"),
        (["api", "requests", "http", "fetch", "get request"], "api_client"),
        (["test", "unittest", "pytest", "assert", "テスト", "calculator", "add_subtract"], "testing"),
        (["bug", "バグ", "fix", "修正", "debug", "buggy", "エラー修正"], "bug_fix"),
        (["fizzbuzz", "fibonacci", "algorithm", "アルゴリズム", "実装", "implement"], "coding"),
        (["file", "ファイル", "directory", "フォルダ", "folder", "path"], "file_operation"),
        (["git", "commit", "version", "branch"], "git_operation"),
        (["plot", "chart", "matplotlib", "グラフ", "graph"], "data_visualization"),
        (["news", "ニュース", "rss", "feed"], "news_fetching"),
        (["slack", "discord", "notify", "通知"], "notification"),
        (["sql", "sqlite", "database", "db"], "database"),
        (["image", "画像", "PIL", "pillow", "cv2"], "image_processing"),
    ]

    # タスク説明とimportリストの両方でマッチング
    for keywords, name in patterns:
        if any(kw in task_lower for kw in keywords):
            return name
        if any(kw in imports_lower for kw in keywords):
            return name

    # マッチなし: タスクの意味のある単語を使う（ツール名は除外）
    exclude = {
        "create_file", "edit_file", "run", "done", "read_file",
        "make_dir", "append_file", "web_search",
    }
    words = [
        w for w in re.sub(r"[^\w\s]", "", task).split()
        if len(w) >= 3 and w.lower() not in exclude
    ][:2]
    return "_".join(w.lower() for w in words) or "general_task"


def _build_summary(task_description: str, history: list[dict]) -> str:
    """最後の done/answer の content を summary とする。なければタスク説明を使う。"""
    for h in reversed(history):
        action = h.get("action", {})
        if action.get("tool") in ("done", "answer"):
            content = action.get("content") or action.get("summary") or ""
            if content:
                return content[:200]
    return task_description[:200]


# -------------------------
# 公開 API
# -------------------------

def extract_skill(
    task_description: str,
    history: list[dict],
    final_output: str = "",
    succeeded: bool = False,
) -> "Skill | None":
    """
    履歴からスキルを抽出する。
    succeeded=True または履歴に done/answer がある場合にスキルを返す。
    main.py から呼ぶ際は succeeded=True を渡すこと（done検出時点では
    history にまだ done アクションが append されていないため）。
    """
    # 成功確認: 呼び出し元が明示するか、履歴に done/answer があること
    if not succeeded:
        success_tools = {"done", "answer"}
        succeeded = any(
            h.get("action", {}).get("tool") in success_tools
            for h in history
        )
    if not succeeded:
        return None

    tools_used  = _extract_tools_used(history)
    key_imports = _extract_imports(history)
    keywords    = _extract_keywords(task_description)
    name        = _generate_skill_name(task_description, key_imports)
    summary     = _build_summary(task_description, history) if not final_output else final_output[:200]

    return Skill(
        name          = name,
        task_example  = task_description[:300],
        success_count = 1,
        last_used     = _now_iso(),
        tools_used    = tools_used,
        key_imports   = key_imports,
        keywords      = keywords,
        summary       = summary,
    )


def save_skill(skill: "Skill", history: list[dict] | None = None) -> None:
    """
    スキルを memory/skill_db.json に upsert する。
    同名スキルが存在すれば success_count をインクリメントして更新。

    Args:
        skill:   extract_skill() が返した Skill オブジェクト
        history: main.py の history リスト。渡すとコードチェックが実行される。
    """
    # --- CODE CHECK START ---
    if history:
        try:
            from code_checker import check_history_code, format_report
            issues = check_history_code(history, skill.task_example)
            if issues:
                report = format_report(issues, source=skill.name)
                print(report)
                # error レベルがある場合は保存前に警告 (保存はブロックしない)
                errors = [i for i in issues if i["level"] == "error"]
                if errors:
                    print(f"    ⚠️ コード品質警告: {len(errors)}件のエラーがあります (保存は継続)")
        except Exception as _ce:
            pass  # チェック失敗時はスキップ
    # --- CODE CHECK END ---

    data = _load_db()
    skills = data.setdefault("skills", {})

    if skill.name in skills:
        existing = skills[skill.name]
        existing["success_count"] = existing.get("success_count", 0) + 1
        existing["last_used"]     = skill.last_used
        # tools / imports / keywords をマージ（重複除去）
        for key, new_vals in [
            ("tools_used",  skill.tools_used),
            ("key_imports", skill.key_imports),
            ("keywords",    skill.keywords),
        ]:
            merged = existing.get(key, [])
            for v in new_vals:
                if v not in merged:
                    merged.append(v)
            existing[key] = merged[:15]
        existing["summary"] = skill.summary
    else:
        skills[skill.name] = {
            "name":          skill.name,
            "task_example":  skill.task_example,
            "success_count": skill.success_count,
            "last_used":     skill.last_used,
            "tools_used":    skill.tools_used,
            "key_imports":   skill.key_imports,
            "keywords":      skill.keywords,
            "summary":       skill.summary,
        }

    _save_db(data)
    print(f"    💡 スキル保存: {skill.name} (成功{skills[skill.name]['success_count']}回)")

    # --- TOOLKIT INTEGRATION START ---
    # tools/evolved/{skill.name}.py があればtoolkitに統合する
    evolved_dir = AGENT_ROOT / "tools" / "evolved"
    tool_file   = evolved_dir / f"{skill.name}.py"
    if tool_file.exists():
        try:
            from toolkit_manager import integrate_tool
            code = tool_file.read_text(encoding="utf-8")
            func_match = re.search(r"def (tool_\w+)\(", code)
            if func_match:
                func_name  = func_match.group(1)
                func_start = code.find(f"def {func_name}(")
                func_code  = code[func_start:].strip()
                integrate_tool(func_name, func_code, skill.summary[:80])
        except Exception as e:
            print(f"    ⚠️ toolkit統合スキップ: {e}")
    # --- TOOLKIT INTEGRATION END ---


def search_skills(task_description: str, top_n: int = 3) -> list[dict]:
    """
    タスク説明と類似するスキルを返す。
    スコア = キーワード一致数 + 再近接ボーナス (_recency_score)
    """
    data = _load_db()
    skills = data.get("skills", {})
    if not skills:
        return []

    query_kws = set(_extract_keywords(task_description))
    scored = []

    for name, s in skills.items():
        skill_kws = set(s.get("keywords", []))
        overlap   = len(query_kws & skill_kws)
        recency   = _recency_score(s.get("last_used", ""))
        score     = overlap + recency
        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:top_n]]


def get_skill_hint(task_description: str) -> str:
    """
    プランナープロンプトに注入するヒント文字列を返す。
    類似スキルがなければ空文字を返す。
    """
    similar = search_skills(task_description, top_n=2)
    if not similar:
        return ""

    lines = ["[SKILL HINT] 過去の類似タスクから学習したスキル:"]
    for s in similar:
        lines.append(
            f"  - [{s['name']}] {s['summary']}"
            f" (成功{s.get('success_count', 1)}回"
            f" | ツール: {', '.join(s.get('tools_used', [])[:4])})"
        )
        if s.get("key_imports"):
            lines.append(f"    必要ライブラリ: {', '.join(s['key_imports'][:5])}")
    lines.append("")
    return "\n".join(lines)


def show_skill_stats() -> str:
    """スキルDBの統計を返す（複合スキル対応版）"""
    if not SKILL_DB.exists():
        return "## ⚡ Skill DB\n\nスキルなし"

    db = json.loads(SKILL_DB.read_text(encoding="utf-8"))
    skills = db.get("skills", {})

    base_skills     = {k: v for k, v in skills.items() if not v.get("is_composed")}
    composed_skills = {k: v for k, v in skills.items() if v.get("is_composed")}

    lines = [
        "## ⚡ Skill DB（習得済みスキル）",
        f"基本スキル: {len(base_skills)}個 / 複合スキル: {len(composed_skills)}個",
        "",
        "### 基本スキル",
    ]

    for name, s in sorted(base_skills.items(), key=lambda x: -x[1].get("success_count", 1)):
        count   = s.get("success_count", 1)
        imports = ", ".join(s.get("key_imports", [])[:3])
        lines.append(f"- **{name}** (×{count}) {f'[{imports}]' if imports else ''}")
        lines.append(f"  {s.get('summary', s.get('task_example', ''))[:60]}")

    if composed_skills:
        lines += ["", "### 複合スキル（自動生成）"]
        for name, s in composed_skills.items():
            sources = " + ".join(s.get("composed_from", []))
            lines.append(f"- **{name}**")
            lines.append(f"  合成元: {sources}")

    if not skills:
        lines.append("（まだ学習データなし）")

    return "\n".join(lines)


# -------------------------
# スキル名修正
# -------------------------

def repair_skill_names() -> None:
    """既存の壊れたスキル名を正規化する。"""
    if not SKILL_DB.exists():
        print("skill_db.json が存在しません")
        return
    db = json.loads(SKILL_DB.read_text(encoding="utf-8"))
    skills = db.get("skills", {})
    repaired = {}
    old_names = list(skills.keys())

    for name, data in skills.items():
        # 複合スキル（is_composed）はそのまま保持
        if data.get("is_composed"):
            repaired[name] = data
            continue
        # task_example または name 自体から新スキル名を生成
        task_src = data.get("task_example", data.get("description", name))
        imports  = data.get("key_imports", [])
        new_name = _generate_skill_name(task_src, imports)
        data["name"] = new_name
        if new_name in repaired:
            # マージ: success_count を合算
            repaired[new_name]["success_count"] = (
                repaired[new_name].get("success_count", 1)
                + data.get("success_count", 1)
            )
            # tools / imports / keywords をマージ
            for key in ("tools_used", "key_imports", "keywords"):
                merged = repaired[new_name].get(key, [])
                for v in data.get(key, []):
                    if v not in merged:
                        merged.append(v)
                repaired[new_name][key] = merged[:15]
        else:
            repaired[new_name] = data

    db["skills"] = repaired
    SKILL_DB.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    new_names = list(repaired.keys())
    print(f"スキル名修正: {old_names} → {new_names}")


# -------------------------
# Skill Composition
# -------------------------

def compose_skills(
    skill_names: list = None,
    min_co_occurrence: int = 2,
) -> list:
    """
    複数のスキルを組み合わせて複合スキルを生成する。

    Args:
        skill_names: 合成するスキル名のリスト（例: ["web_scraping", "data_analysis"]）
                     指定なしの場合は共起パターンを自動検出して合成
        min_co_occurrence: 自動検出時の最小共起回数（両スキルの合計 success_count）

    Returns:
        生成された複合スキルのリスト
    """
    if not SKILL_DB.exists():
        return []

    db     = json.loads(SKILL_DB.read_text(encoding="utf-8"))
    skills = db.get("skills", {})

    if skill_names:
        # 指定スキルを合成
        targets = [skills[n] for n in skill_names if n in skills]
        if len(targets) < 2:
            print(f"  ⚠️ 合成には2つ以上のスキルが必要: {skill_names}")
            return []
        composed = _merge_skills(targets, skill_names)
        _save_composed_skill(composed, db)
        return [composed]
    else:
        # 自動検出
        return _auto_compose(skills, db, min_co_occurrence)


def _merge_skills(skill_list: list, source_names: list) -> dict:
    """複数スキルをマージして複合スキルを生成する。"""
    composed_name = "_plus_".join(sorted(source_names))

    # tools_used を順序維持でマージ（重複除去）
    all_tools = []
    for s in skill_list:
        for t in s.get("tools_used", []):
            if t not in all_tools:
                all_tools.append(t)

    # key_imports をマージ
    all_imports = []
    for s in skill_list:
        for imp in s.get("key_imports", []):
            if imp not in all_imports:
                all_imports.append(imp)

    # keywords をマージ
    all_keywords = list({
        kw for s in skill_list for kw in s.get("keywords", [])
    })[:20]

    # 説明文を生成
    descriptions = [
        s.get("summary", s.get("task_example", ""))[:40]
        for s in skill_list
    ]
    composed_desc = " + ".join(descriptions)[:100]

    return {
        "name":          composed_name,
        "summary":       composed_desc,
        "keywords":      all_keywords,
        "tools_used":    all_tools,
        "key_imports":   all_imports,
        "success_count": 1,
        "last_used":     datetime.now(timezone.utc).isoformat(),
        "composed_from": source_names,   # 合成元を記録
        "is_composed":   True,
    }


def _auto_compose(skills: dict, db: dict, min_count: int) -> list:
    """
    tools_used の共起パターンから自動的に合成候補を見つける。
    2つのスキルが同じツールを共有 かつ 合計 success_count が閾値以上なら合成。
    """
    skill_list     = list(skills.items())
    composed_list  = []

    for i in range(len(skill_list)):
        for j in range(i + 1, len(skill_list)):
            name_a, skill_a = skill_list[i]
            name_b, skill_b = skill_list[j]

            # 既に合成済みはスキップ
            if skill_a.get("is_composed") or skill_b.get("is_composed"):
                continue

            tools_a = set(skill_a.get("tools_used", []))
            tools_b = set(skill_b.get("tools_used", []))
            shared  = tools_a & tools_b

            total_count = (
                skill_a.get("success_count", 1)
                + skill_b.get("success_count", 1)
            )

            if total_count >= min_count and len(shared) >= 1:
                composed_name = f"{name_a}_plus_{name_b}"
                if composed_name not in skills:
                    composed = _merge_skills([skill_a, skill_b], [name_a, name_b])
                    _save_composed_skill(composed, db)
                    composed_list.append(composed)
                    print(f"  🔗 複合スキル生成: {composed_name}")
                    print(f"     共有ツール: {shared}")

    return composed_list


def _save_composed_skill(composed: dict, db: dict) -> None:
    """複合スキルを DB に保存する。"""
    name = composed["name"]
    if name not in db.get("skills", {}):
        db.setdefault("skills", {})[name] = composed
        SKILL_DB.write_text(
            json.dumps(db, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  💾 複合スキル保存: {name}")
