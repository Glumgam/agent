"""
Auto Research Agent with Knowledge Evolution。
任意分野の情報を収集し、エージェント自身の能力強化に使う。
収集した知識からスキルを抽出し、新ツールを自動生成する。
使い方:
  python research_agent.py                    # 全トピック
  python research_agent.py --topic ai_news    # 特定トピック
  python research_agent.py --dry-run          # 収集のみ（要約なし）
  python research_agent.py --list             # トピック一覧表示
"""
import json
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

AGENT_ROOT    = Path(__file__).parent
KNOWLEDGE_DIR = AGENT_ROOT / "knowledge"
REPORT_PATH   = AGENT_ROOT / "daily_report.md"
TOPICS_FILE   = AGENT_ROOT / "research_topics.json"

# 動的な年月（毎月クエリが変わりcollection_logの詰まりを防ぐ）
_YM = datetime.now().strftime("%Y-%m")   # 例: "2026-03"
_Y  = datetime.now().strftime("%Y")       # 例: "2026"

# =====================================================
# デフォルトトピック（research_topics.json で上書き可能）
# =====================================================
DEFAULT_TOPICS = [
    {
        "id":      "ai_news",
        "label":   "AI・LLM 最新動向",
        "queries": [
            f"AI LLM agent {_Y}",
            f"Claude GPT Gemini update {_YM}",
        ],
        "sources": ["news", "hackernews"],
        "evolve":  True,
    },
    {
        "id":      "python_tech",
        "label":   "Python 技術トレンド",
        "queries": [
            f"Python new library {_YM}",
            f"Python tool framework {_Y}",
            f"Python tips {_YM}",
            f"Python best practices {_Y}",
        ],
        "sources": ["github", "pypi"],
        "evolve":  True,
    },
    {
        "id":      "arxiv_ai",
        "label":   "AI 論文（arXiv）",
        "queries": ["LLM agent tool use", "autonomous agent learning"],
        "sources": ["arxiv"],
        "evolve":  True,
    },
    {
        "id":      "gadget",
        "label":   "ガジェット・テック",
        "queries": [
            f"latest gadget {_YM}",
            f"Apple Google tech news {_Y}",
        ],
        "sources": ["hackernews", "news"],
        "evolve":  False,
    },
    {
        "id":      "custom",
        "label":   "カスタムトピック",
        "queries": [],
        "sources": ["news"],
        "evolve":  False,
    },
]

# =====================================================
# メイン実行
# =====================================================
def run_research(
    topic_ids: list = None,
    dry_run: bool = False,
) -> dict:
    KNOWLEDGE_DIR.mkdir(exist_ok=True)

    topics = _load_topics()
    if topic_ids:
        topics = [t for t in topics if t["id"] in topic_ids]

    print(f"\n{'='*60}")
    print(f"  Knowledge Evolution Research Agent")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  トピック数: {len(topics)}")
    print(f"{'='*60}\n")

    all_results    = []
    evolved_skills = []

    for topic in topics:
        print(f"\n[{topic['id']}] {topic['label']}")
        result = _research_topic(topic, dry_run=dry_run)
        all_results.append(result)
        _save_topic_knowledge(result)

        # 能力強化フェーズ
        if topic.get("evolve") and not dry_run and result["collected"]:
            new_skills = _evolve_from_knowledge(topic, result)
            evolved_skills.extend(new_skills)

    _generate_daily_report(all_results, evolved_skills)

    return {
        "topics":         len(all_results),
        "total_items":    sum(r["item_count"] for r in all_results),
        "evolved_skills": len(evolved_skills),
        "report":         str(REPORT_PATH),
    }


# =====================================================
# 情報収集
# =====================================================
def _research_topic(topic: dict, dry_run: bool = False) -> dict:
    # --- KNOWLEDGE EVOLUTION START ---
    from tools.web_search import (
        _fetch_news_raw,
        tool_fetch_ranking,
        tool_fetch_tech_info,
        tool_web_search,
    )

    collected = []

    # --- DEDUP START ---
    try:
        from collection_log import get_recent_queries, log_collection
        _recent_queries = get_recent_queries(topic["id"], days=3)
    except Exception:
        _recent_queries = []
        log_collection = None
    # --- DEDUP END ---

    for source in topic.get("sources", ["news"]):
        for query in topic.get("queries", []):
            if not query.strip():
                continue

            # --- DEDUP CHECK ---
            if query in _recent_queries:
                print(f"  スキップ（既収集）: {query[:40]}")
                continue
            # --- DEDUP CHECK END ---

            print(f"  収集: [{source}] {query[:40]}")
            try:
                if source == "news":
                    r = _fetch_news_raw(query, max_results=3)
                elif source in ("hackernews", "github", "pypi"):
                    r = tool_fetch_ranking({"category": source})
                elif source == "arxiv":
                    r = tool_fetch_tech_info(query, source="arxiv")
                elif source == "reddit":
                    r = tool_fetch_tech_info(query, source="reddit")
                else:
                    r = tool_web_search({"query": query, "max_results": 3})

                if r.ok and r.output:
                    collected.append({
                        "source":  source,
                        "query":   query,
                        "content": r.output,
                    })
                    # --- LOG COLLECTION ---
                    if log_collection:
                        try:
                            log_collection(
                                topic_id=topic["id"],
                                source=source,
                                query=query,
                                item_count=1,
                            )
                        except Exception:
                            pass
                    # --- LOG COLLECTION END ---
                else:
                    print(f"    ⚠️ 取得失敗: {r.output[:80]}")
            except Exception as e:
                print(f"    ⚠️ {e}")
    # --- KNOWLEDGE EVOLUTION END ---

    summary = ""
    if collected and not dry_run:
        summary = _summarize(topic["label"], collected)

    return {
        "topic_id":   topic["id"],
        "label":      topic["label"],
        "collected":  collected,
        "item_count": len(collected),
        "summary":    summary,
        "timestamp":  datetime.now().isoformat(),
    }


def _summarize(label: str, collected: list) -> str:
    from llm import ask_plain

    content_text = ""
    for item in collected[:5]:
        content_text += f"\n[{item['source']}] {item['query']}\n"
        content_text += item["content"][:400] + "\n"

    prompt = f"""
以下は「{label}」の最新情報です。
重要なポイントを日本語で3〜5点にまとめてください。

{content_text}

出力形式:
## {label} まとめ
- ポイント1
- ポイント2
"""
    print(f"  🧠 要約中 (qwen2.5-coder:7b)...")
    return ask_plain(prompt)


# =====================================================
# 能力強化（Deep Research Evolution）
# =====================================================
def _evolve_from_knowledge(topic: dict, result: dict) -> list:
    """
    収集した情報から機能獲得を試みる。
    方針A: 収集情報から候補を発見（ask_plain で高速）
    方針B: A で0件の場合、未習得の有用ライブラリを1つ自動習得
    """
    # --- FAST EVOLVE START ---
    from deep_researcher import (
        run_deep_research, get_unacquired_libraries,
        deep_research_candidate, implement_and_test, register_tool,
    )

    content_text = "\n\n".join(
        f"[{c['source']}] {c['query']}\n{c['content'][:300]}"
        for c in result["collected"][:4]
    )

    print(f"\n  ⚡ 深掘り研究開始: {topic['label']}")
    acquired = run_deep_research(topic["label"], content_text)

    # 方針B: 収集情報から候補なし → 未習得の有用ライブラリを1つ習得
    if not acquired:
        unacquired = get_unacquired_libraries()
        if unacquired:
            target = unacquired[0]
            print(f"  📚 未習得ライブラリを習得: {target['name']}")
            research = deep_research_candidate(target)
            if research["sufficient"]:
                impl = implement_and_test(research)
                if impl["success"]:
                    registered = register_tool(impl, target, topic["label"])
                    if registered:
                        acquired.append(impl["tool_name"])
                else:
                    print(f"  ❌ 実装失敗(B): {impl.get('reason', '?')}")

    if acquired:
        print(f"  🎉 新機能獲得: {acquired}")
    else:
        print(f"  ℹ️  今回の獲得: なし")

    return acquired
    # --- FAST EVOLVE END ---


def _parse_and_apply_evolution(response: str, topic: dict) -> list:
    """LLMの提案を解析してツール・スキルを生成する"""
    new_skills = []

    if "SKILL_NAME: none" in response:
        print(f"  ℹ️  新規獲得スキルなし")
        return []

    blocks = re.split(r"(?=SKILL_NAME:)", response)
    for block in blocks:
        if "SKILL_NAME:" not in block:
            continue

        skill_name  = re.search(r"SKILL_NAME:\s*(\S+)", block)
        description = re.search(r"DESCRIPTION:\s*(.+)", block)
        code_match  = re.search(r"CODE:\n(.*?)END_CODE", block, re.DOTALL)

        if not (skill_name and code_match):
            continue

        name = skill_name.group(1).strip()
        desc = description.group(1).strip() if description else ""
        code = code_match.group(1).strip()

        if not name or name == "none":
            continue

        # 構文チェック
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            print(f"  ⚠️ 構文エラーでスキップ: {name} ({e})")
            continue

        tool_created = _create_evolved_tool(name, desc, code)
        if tool_created:
            _register_evolved_skill(name, desc, topic)
            new_skills.append(name)
            print(f"  ⚡ 新スキル獲得: {name}")

    return new_skills


def _create_evolved_tool(name: str, description: str, code: str) -> bool:
    """獲得したスキルをツールファイルとして保存する"""
    evolved_dir = AGENT_ROOT / "tools" / "evolved"
    evolved_dir.mkdir(exist_ok=True)

    tool_path = evolved_dir / f"{name}.py"
    if tool_path.exists():
        print(f"  ℹ️  既存ツール: {name}")
        return False

    tool_content = f'''"""
自動生成ツール: {name}
説明: {description}
生成日: {datetime.now().strftime("%Y-%m-%d")}
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from tool_result import ToolResult

{code}

def get_tool_name() -> str:
    return "{name}"
'''
    tool_path.write_text(tool_content, encoding="utf-8")
    print(f"  💾 ツール保存: tools/evolved/{name}.py")
    return True


def _register_evolved_skill(name: str, description: str, topic: dict):
    """獲得したスキルを skill_db.json に登録する"""
    # --- KNOWLEDGE EVOLUTION START ---
    from skill_extractor import save_skill, Skill
    skill = Skill(
        name=name,
        task_example=f"[進化獲得] {description} (from: {topic['label']})",
        success_count=1,
        last_used=datetime.now(timezone.utc).isoformat(),
        tools_used=["evolved_tool"],
        key_imports=[],
        keywords=[topic["id"]] + name.split("_"),
        summary=f"Knowledge Evolution により獲得。分野: {topic['label']}",
    )
    save_skill(skill)
    # --- KNOWLEDGE EVOLUTION END ---


# =====================================================
# レポート・設定
# =====================================================
def _apply_dynamic_dates(topics: list) -> list:
    """クエリ内の固定年月を動的な年月に置き換える（毎月クエリが変わりログ詰まりを防ぐ）"""
    result = []
    for topic in topics:
        t = dict(topic)
        new_queries = []
        for q in t.get("queries", []):
            # 固定の年月（YYYY-MM）→ 動的年月
            q = re.sub(r"\b\d{4}-\d{2}\b", _YM, q)
            # 固定の年（YYYY）→ 動的年（年月置換後に残った単独年のみ）
            q = re.sub(r"\b\d{4}\b", _Y, q)
            new_queries.append(q)
        t["queries"] = new_queries
        result.append(t)
    return result


def _load_topics() -> list:
    if TOPICS_FILE.exists():
        with open(TOPICS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  カスタムトピック読み込み: {TOPICS_FILE.name}")
        # 固定年月を動的に置き換える
        data = _apply_dynamic_dates(data)
        return data
    return [t for t in DEFAULT_TOPICS if t.get("queries")]


def _save_topic_knowledge(result: dict):
    topic_dir = KNOWLEDGE_DIR / result["topic_id"]
    topic_dir.mkdir(exist_ok=True)

    date_str  = datetime.now().strftime("%Y-%m-%d")
    save_path = topic_dir / f"{date_str}.md"

    lines = [
        f"# {result['label']}",
        f"Date: {result['timestamp'][:10]}",
        "",
    ]
    if result.get("summary"):
        lines += [result["summary"], ""]
    lines += ["## 収集データ", ""]
    for item in result["collected"]:
        lines += [
            f"### [{item['source']}] {item['query']}",
            item["content"][:600],
            "",
        ]

    save_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  💾 保存: knowledge/{result['topic_id']}/{save_path.name}")

    # --- NEWS RSS START ---
    # RSSニュースを knowledge ファイルに追記する
    try:
        from news_collector import TOPIC_TO_GENRE, get_latest_news, format_news_for_article
        genre      = TOPIC_TO_GENRE.get(result["topic_id"], "general")
        news_items = get_latest_news(genre, max_items=10)
        news_text  = format_news_for_article(news_items)
        if news_text:
            existing = save_path.read_text(encoding="utf-8")
            save_path.write_text(
                existing + f"\n\n## 最新ニュース（RSS: {genre}）\n\n{news_text}\n",
                encoding="utf-8",
            )
            print(f"  📰 RSSニュース追記: {len(news_items)}件 [{genre}]")
    except Exception as e:
        pass  # ニュース収集失敗はサイレントスキップ
    # --- NEWS RSS END ---


def _generate_daily_report(all_results: list, evolved_skills: list):
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# Daily Research & Evolution Report",
        f"Date: {date_str}",
        f"Generated: {datetime.now().strftime('%H:%M')}",
        "",
        "## サマリー",
        f"- 収集トピック: {len(all_results)}件",
        f"- 総収集アイテム: {sum(r['item_count'] for r in all_results)}件",
        f"- 新規獲得スキル: {len(evolved_skills)}個",
        "",
    ]
    if evolved_skills:
        lines += ["## ⚡ 新規獲得スキル（ゲットアビリティ）", ""]
        for s in evolved_skills:
            lines.append(f"- `{s}`")
        lines.append("")

    for result in all_results:
        lines += [f"## {result['label']}", ""]
        if result.get("summary"):
            lines += [result["summary"], ""]
        lines += ["---", ""]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    evolved_path = KNOWLEDGE_DIR / f"daily_report_{date_str}.md"
    evolved_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n📄 レポート: {REPORT_PATH}")


# =====================================================
# エントリポイント
# =====================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Knowledge Evolution Research Agent")
    parser.add_argument("--topic",   nargs="+", help="トピックID")
    parser.add_argument("--dry-run", action="store_true", help="収集のみ")
    parser.add_argument("--list",    action="store_true", help="トピック一覧")
    args = parser.parse_args()

    if args.list:
        topics = _load_topics()
        print("利用可能なトピック:")
        for t in topics:
            evolve = "⚡進化あり" if t.get("evolve") else "📰収集のみ"
            print(f"  {t['id']:20} {t['label']} [{evolve}]")
        sys.exit(0)

    result = run_research(
        topic_ids=args.topic,
        dry_run=args.dry_run,
    )
    print(
        f"\n完了: {result['topics']}トピック / "
        f"{result['total_items']}件収集 / "
        f"{result['evolved_skills']}スキル獲得"
    )
