"""
Git自己進化トラッカー。
修復・改善が成功したとき自動でgit commitし、
エージェントの進化履歴を蓄積する。
"""

# --- GIT EVOLUTION START ---
import subprocess
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

AGENT_ROOT    = Path(__file__).parent
EVOLUTION_LOG = AGENT_ROOT / "evolution_log.md"
PATTERN_DB    = AGENT_ROOT / "memory" / "repair_patterns.json"


@dataclass
class EvolutionRecord:
    timestamp:     str
    error_type:    str
    file_repaired: str
    strategy:      str
    commit_hash:   str
    description:   str
    success:       bool


def record_evolution(
    error_type: str,
    file_repaired: str,
    strategy: str,
    description: str,
    files_to_commit: list = None,
) -> EvolutionRecord:
    """修復成功時に呼ぶ。git commitして進化記録を保存する。"""
    commit_hash = _git_commit(
        files=files_to_commit or [file_repaired],
        message=_build_commit_message(error_type, strategy, description),
    )
    record = EvolutionRecord(
        timestamp=datetime.now().isoformat(),
        error_type=error_type,
        file_repaired=file_repaired,
        strategy=strategy,
        commit_hash=commit_hash,
        description=description,
        success=commit_hash not in ("no-commit", "no-change"),
    )
    _append_evolution_log(record)
    _update_pattern_db(record)
    print(f"  📌 進化記録: [{commit_hash[:8]}] {error_type} → {strategy}")
    return record


def get_evolution_history(limit: int = 20) -> list:
    """進化履歴を返す（新しい順）"""
    if not PATTERN_DB.exists():
        return []
    with open(PATTERN_DB, encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", [])
    return records[-limit:][::-1]


def get_successful_patterns(error_type: str) -> list:
    """特定エラータイプで成功した修復戦略を返す"""
    if not PATTERN_DB.exists():
        return []
    with open(PATTERN_DB, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("patterns", {}).get(error_type, [])


def generate_evolution_report() -> str:
    """進化サマリーレポートを生成して返す"""
    history = get_evolution_history(50)
    if not history:
        return "# Evolution Report\n\n進化記録なし"

    total   = len(history)
    success = sum(1 for r in history if r.get("success"))
    by_type  = {}
    by_strat = {}
    for r in history:
        et = r.get("error_type", "unknown")
        st = r.get("strategy",   "unknown")
        by_type[et]  = by_type.get(et, 0)  + 1
        by_strat[st] = by_strat.get(st, 0) + 1

    lines = [
        "# Evolution Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Summary",
        f"- 総修復回数: {total}",
        f"- 成功率: {success}/{total} ({success/total*100:.0f}%)",
        "",
        "## エラータイプ別",
    ]
    for et, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f"- {et}: {cnt}回")
    lines += ["", "## 修復戦略別"]
    for st, cnt in sorted(by_strat.items(), key=lambda x: -x[1]):
        lines.append(f"- {st}: {cnt}回")
    lines += ["", "## 直近10件"]
    for r in history[:10]:
        ts  = r.get("timestamp", "")[:16]
        ok  = "✅" if r.get("success") else "❌"
        lines.append(
            f"- `{ts}` [{r.get('commit_hash', '?')[:8]}] "
            f"{r.get('error_type')} → {r.get('strategy')} {ok}"
        )
    return "\n".join(lines)


# =====================================================
# 内部関数
# =====================================================

def _git_commit(files: list, message: str) -> str:
    try:
        for f in files:
            subprocess.run(
                ["git", "add", str(f)],
                cwd=AGENT_ROOT, capture_output=True
            )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=AGENT_ROOT, capture_output=True, text=True
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                return "no-change"
            return "no-commit"
        h = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=AGENT_ROOT, capture_output=True, text=True
        )
        return h.stdout.strip()
    except Exception as e:
        print(f"    ⚠️ git commit失敗: {e}")
        return "no-commit"


def _build_commit_message(error_type: str, strategy: str, description: str) -> str:
    prefix_map = {
        "loop_detected": "fix(loop)",
        "max_steps":     "fix(done)",
        "invalid_tool":  "fix(tool)",
        "import_error":  "fix(import)",
        "syntax_error":  "fix(syntax)",
        "runtime_error": "fix(runtime)",
        "no_run":        "fix(run)",
        "wrong_output":  "fix(output)",
        "timeout":       "fix(timeout)",
    }
    prefix = prefix_map.get(error_type, "fix(auto)")
    return f"{prefix}: {description[:60]} [{strategy}]"


def _append_evolution_log(record: EvolutionRecord):
    with open(EVOLUTION_LOG, "a", encoding="utf-8") as f:
        ok = "✅" if record.success else "❌"
        f.write(
            f"| {record.timestamp[:16]} "
            f"| {record.error_type} "
            f"| {record.file_repaired} "
            f"| {record.strategy} "
            f"| `{record.commit_hash[:8]}` "
            f"| {ok} |\n"
        )


def _update_pattern_db(record: EvolutionRecord):
    PATTERN_DB.parent.mkdir(exist_ok=True)
    if PATTERN_DB.exists():
        with open(PATTERN_DB, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"records": [], "patterns": {}}
        # evolution_log.md のヘッダーを初回だけ書く
        with open(EVOLUTION_LOG, "w", encoding="utf-8") as f:
            f.write("# Evolution Log\n\n")
            f.write("| Timestamp | Error Type | File | Strategy | Commit | Result |\n")
            f.write("|-----------|-----------|------|----------|--------|--------|\n")

    data["records"].append(asdict(record))

    if record.success:
        et = record.error_type
        if et not in data["patterns"]:
            data["patterns"][et] = []
        existing = [p["strategy"] for p in data["patterns"][et]]
        if record.strategy not in existing:
            data["patterns"][et].append({
                "strategy": record.strategy,
                "description": record.description,
                "count": 1,
            })
        else:
            for p in data["patterns"][et]:
                if p["strategy"] == record.strategy:
                    p["count"] = p.get("count", 0) + 1

    with open(PATTERN_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
# --- GIT EVOLUTION END ---
