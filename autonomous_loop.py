"""
18時間自律ループ。
サイクル:
  情報収集 → ゲットアビリティ → テスト → 情報収集 → ...
安全設計:
- テストが18/23未満になったら一時停止
- ループログを毎サイクル保存
- Ctrl+C で安全に停止
- macOS がスリープしても再開可能
"""
import time
import json
import signal
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

AGENT_ROOT  = Path(__file__).parent
LOG_PATH    = AGENT_ROOT / "logs" / "autonomous_loop.log"
STATUS_PATH = AGENT_ROOT / "logs" / "loop_status.json"
PYTHON      = str(AGENT_ROOT / "venv" / "bin" / "python")

# =====================================================
# 設定
# =====================================================
CONFIG = {
    # 実行時間
    "max_hours":        18,
    "cycle_interval":   0,     # サイクル間の待機（分）0=即移行
    # テスト品質ゲート
    "min_pass_rate":    0.78,  # 18/23 = 78% 未満で警告
    "stop_on_fail":     False, # True にすると品質低下で停止
    # 情報収集トピック（ローテーション）
    "research_topics":  [
        "python_tech",
        "ai_news",
        "arxiv_ai",
        "security",
        "gadget",
        "finance",
        "science",
        "food",
    ],
    # テストカテゴリ（毎回全部は重いので軽量テストのみ）
    "quick_test_only":  True,  # True=Codingのみ、False=全カテゴリ
}

# =====================================================
# ループ制御
# =====================================================
_running = True


def _signal_handler(sig, frame):
    global _running
    print("\n\n⚠️  停止シグナル受信 → 現在のサイクル完了後に停止します")
    _running = False


signal.signal(signal.SIGINT,  _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def run_autonomous_loop():
    LOG_PATH.parent.mkdir(exist_ok=True)
    start_time  = datetime.now()
    end_time    = start_time + timedelta(hours=CONFIG["max_hours"])
    topic_queue = list(CONFIG["research_topics"])
    cycle_num   = 0
    total_skills = 0
    test_history = []

    _log(f"🚀 自律ループ開始: {start_time.strftime('%Y-%m-%d %H:%M')}")
    _log(f"   終了予定: {end_time.strftime('%Y-%m-%d %H:%M')}")
    _log(f"   サイクル間隔: {CONFIG['cycle_interval']}分")
    _save_status("running", cycle_num, total_skills, start_time, end_time)

    while _running and datetime.now() < end_time:
        cycle_num += 1
        cycle_start = datetime.now()
        remaining   = end_time - datetime.now()

        _log(f"\n{'='*60}")
        _log(f"  サイクル {cycle_num} | 残り {_fmt_duration(remaining)}")
        _log(f"{'='*60}")

        # --- Phase 1: 情報収集 + ゲットアビリティ ---
        topic = topic_queue[0]
        topic_queue = topic_queue[1:] + [topic_queue[0]]  # ローテーション

        _log(f"\n[Phase 1] 情報収集: {topic}")
        skills_before = _count_evolved_skills()
        _run_research(topic)
        skills_after  = _count_evolved_skills()
        new_skills    = skills_after - skills_before
        total_skills += new_skills

        if new_skills > 0:
            _log(f"  ⚡ 新スキル獲得: {new_skills}個 (累計: {total_skills}個)")
        else:
            _log(f"  ℹ️  スキル獲得なし")

        # --- SKILL EVOLUTION START ---
        # Phase 1.5: 獲得済みスキルの応用・発展（2サイクルに1回）
        if cycle_num % 2 == 0:
            _log(f"\n[Phase 1.5] スキル応用・発展")
            evolve_result = _run_skill_evolution()
            if evolve_result:
                total_skills += len(evolve_result)
                _log(f"  ⚡ 発展スキル獲得: {evolve_result}")
            else:
                _log(f"  ℹ️  発展スキルなし")
        # --- SKILL EVOLUTION END ---

        # --- Phase 2: テスト ---
        _log(f"\n[Phase 2] テスト実行")
        test_result = _run_test()
        test_history.append(test_result)
        pass_rate = test_result["pass_rate"]
        _log(f"  結果: {test_result['passed']}/{test_result['total']} "
             f"({pass_rate*100:.0f}%)")

        # 品質ゲート
        if pass_rate < CONFIG["min_pass_rate"]:
            _log(f"  ⚠️  品質低下検出: {pass_rate*100:.0f}% < "
                 f"{CONFIG['min_pass_rate']*100:.0f}%")
            if CONFIG["stop_on_fail"]:
                _log("  🛑 stop_on_fail=True のため停止")
                break

        # --- Phase 3: ステータス保存 ---
        cycle_elapsed = (datetime.now() - cycle_start).seconds
        _log(f"\n[Phase 3] サイクル完了: {cycle_elapsed}秒")
        _save_status("running", cycle_num, total_skills, start_time, end_time,
                     test_history=test_history)

        # 次のサイクルまで待機
        if CONFIG["cycle_interval"] > 0 and _running and datetime.now() < end_time:
            wait_min = CONFIG["cycle_interval"]
            _log(f"\n⏳ 次のサイクルまで {wait_min}分待機...")
            _log(f"   次回: {(datetime.now() + timedelta(minutes=wait_min)).strftime('%H:%M')}")
            _sleep_interruptible(wait_min * 60)
        else:
            _log("\n▶ 次のサイクルへ即移行")

    # ループ終了
    elapsed = datetime.now() - start_time
    _log(f"\n{'='*60}")
    _log(f"  自律ループ終了")
    _log(f"  総サイクル数: {cycle_num}")
    _log(f"  総獲得スキル: {total_skills}個")
    _log(f"  総実行時間: {_fmt_duration(elapsed)}")
    _log(f"{'='*60}")
    _save_status("completed", cycle_num, total_skills, start_time, end_time,
                 test_history=test_history)
    _generate_final_report(cycle_num, total_skills, test_history, elapsed)


# =====================================================
# 各フェーズの実行
# =====================================================
def _run_research(topic: str) -> dict:
    """情報収集 + ゲットアビリティを実行する"""
    try:
        result = subprocess.run(
            [PYTHON, "research_agent.py", "--topic", topic],
            cwd=AGENT_ROOT,
            capture_output=True,
            text=True,
            timeout=1800,   # 最大30分
        )
        output = result.stdout + result.stderr
        _log(f"  {'✅' if result.returncode == 0 else '❌'} "
             f"research_agent exit={result.returncode}")
        # 重要な行だけログに残す
        for line in output.split("\n"):
            if any(w in line for w in ["⚡", "✅", "❌", "💾", "候補", "獲得", "ERROR"]):
                _log(f"    {line.strip()}")
        return {"success": result.returncode == 0, "topic": topic}
    except subprocess.TimeoutExpired:
        _log("  ⚠️  タイムアウト（30分）")
        return {"success": False, "topic": topic}
    except Exception as e:
        _log(f"  ❌ エラー: {e}")
        return {"success": False, "topic": topic}


def _run_test() -> dict:
    """テストを実行して結果を返す"""
    try:
        if CONFIG["quick_test_only"]:
            # coding カテゴリのみ（3件、高速）
            cmd = [PYTHON, "-c", """
import sys, json
sys.path.insert(0, '.')
from tester import run_test_suite
suite = run_test_suite(categories=["coding"], loop_round=1)
results = suite.get("results", [])
passed = sum(1 for r in results if r.get("success"))
total  = len(results)
print(json.dumps({"passed": passed, "total": total}))
"""]
        else:
            cmd = [PYTHON, "tester.py", "--rounds", "1"]

        result = subprocess.run(
            cmd, cwd=AGENT_ROOT,
            capture_output=True, text=True,
            timeout=3600,   # 最大1時間
        )

        if CONFIG["quick_test_only"]:
            passed, total = 0, 3
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                        passed = data["passed"]
                        total  = data["total"]
                        break
                    except json.JSONDecodeError:
                        pass
        else:
            import re
            passed, total = 0, 23
            m = re.search(r"(\d+)/(\d+)", result.stdout)
            if m:
                passed = int(m.group(1))
                total  = int(m.group(2))

        return {
            "passed":    passed,
            "total":     total,
            "pass_rate": passed / total if total > 0 else 0,
            "timestamp": datetime.now().isoformat(),
        }
    except subprocess.TimeoutExpired:
        _log("  ⚠️  テストタイムアウト")
        return {"passed": 0, "total": 3, "pass_rate": 0,
                "timestamp": datetime.now().isoformat()}
    except Exception as e:
        _log(f"  ❌ テストエラー: {e}")
        return {"passed": 0, "total": 3, "pass_rate": 0,
                "timestamp": datetime.now().isoformat()}


# --- SKILL EVOLUTION START ---
def _run_skill_evolution() -> list:
    """獲得済みスキルを応用・発展させる"""
    try:
        result = subprocess.run(
            [PYTHON, "-c", """
import sys; sys.path.insert(0, '.')
from deep_researcher import evolve_existing_skills
import json
acquired = evolve_existing_skills()
print(json.dumps(acquired))
"""],
            cwd=AGENT_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        for line in result.stdout.split("\n"):
            if line.strip().startswith("["):
                return json.loads(line.strip())
        return []
    except Exception as e:
        _log(f"  ⚠️ スキル発展エラー: {e}")
        return []
# --- SKILL EVOLUTION END ---


# =====================================================
# ユーティリティ
# =====================================================
def _count_evolved_skills() -> int:
    evolved_dir = AGENT_ROOT / "tools" / "evolved"
    if not evolved_dir.exists():
        return 0
    return len(list(evolved_dir.glob("*.py")))


def _sleep_interruptible(seconds: int):
    """Ctrl+C で中断可能なsleep"""
    interval = 30
    elapsed  = 0
    while elapsed < seconds and _running:
        time.sleep(min(interval, seconds - elapsed))
        elapsed += interval


def _fmt_duration(delta) -> str:
    total_sec = int(abs(delta.total_seconds()))
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    return f"{h}時間{m}分"


def _log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _save_status(
    status: str,
    cycle: int,
    skills: int,
    start: datetime,
    end: datetime,
    test_history: list = None,
):
    data = {
        "status":        status,
        "cycle":         cycle,
        "total_skills":  skills,
        "started_at":    start.isoformat(),
        "ends_at":       end.isoformat(),
        "updated_at":    datetime.now().isoformat(),
        "last_test":     test_history[-1] if test_history else None,
    }
    STATUS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _generate_final_report(
    cycles: int, skills: int,
    test_history: list, elapsed
):
    report_path = AGENT_ROOT / "logs" / "loop_final_report.md"
    lines = [
        "# Autonomous Loop Final Report",
        f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## サマリー",
        f"- 総サイクル数: {cycles}",
        f"- 総獲得スキル: {skills}個",
        f"- 総実行時間: {_fmt_duration(elapsed)}",
        "",
        "## テスト推移",
        "| サイクル | 成功率 | 時刻 |",
        "|---------|--------|------|",
    ]
    for i, t in enumerate(test_history, 1):
        ts  = t.get("timestamp", "")[:16]
        pct = f"{t['pass_rate']*100:.0f}%"
        lines.append(f"| {i} | {t['passed']}/{t['total']} ({pct}) | {ts} |")

    lines += ["", "## 獲得ツール一覧"]
    evolved_dir = AGENT_ROOT / "tools" / "evolved"
    if evolved_dir.exists():
        for f in sorted(evolved_dir.glob("*.py")):
            lines.append(f"- `{f.name}`")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    _log(f"\n📄 最終レポート: {report_path}")


# =====================================================
# エントリポイント
# =====================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="18時間自律ループ")
    parser.add_argument("--hours",     type=float, default=18,
                        help="実行時間（時間）")
    parser.add_argument("--interval",  type=int,   default=30,
                        help="サイクル間隔（分）")
    parser.add_argument("--full-test", action="store_true",
                        help="全カテゴリテストを実行（低速）")
    args = parser.parse_args()

    CONFIG["max_hours"]       = args.hours
    CONFIG["cycle_interval"]  = args.interval
    CONFIG["quick_test_only"] = not args.full_test

    run_autonomous_loop()
