"""
Deep Research System。
候補を発見したら複数ソースで深掘りし、
実際に動作するコードを生成・テストしてから登録する。
"""
import json
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime, timezone

AGENT_ROOT   = Path(__file__).parent
EVOLVED_DIR  = AGENT_ROOT / "tools" / "evolved"
WORKSPACE    = AGENT_ROOT / "workspace"
RESEARCH_LOG = AGENT_ROOT / "knowledge" / "deep_research_log.md"


# =====================================================
# Step1: 候補の発見
# =====================================================
def discover_candidates(topic_label: str, collected_text: str) -> list:
    """
    収集したテキストから「試してみる価値のある候補」を抽出する。
    """
    # --- DEEP RESEARCH START ---
    from llm import ask_thinking

    prompt = f"""
以下の情報から、Pythonエージェントが新たに獲得できる「具体的な機能候補」を
最大3つリストアップしてください。

分野: {topic_label}
収集情報:
{collected_text[:1500]}

必須条件（全て満たすもののみ）:
- PyPI に存在するPythonパッケージであること
- pip install で入手可能であること
- Node.js / JavaScript / Ruby 等の他言語パッケージは除外
- エージェントのツールとして実用的なもの
- 架空のパッケージ名は絶対に使わない

出力前に自問してください:
「このパッケージはpypi.org/project/XXXで実際に存在するか?」
存在が確かでないものは CANDIDATE: none とすること。

出力形式:
CANDIDATE: 正確なPyPIパッケージ名（例: requests, pandas, httpx）
PURPOSE: 何ができるか（1行）
SEARCH_QUERY: 実装例を探すための検索クエリ
---
（候補がなければ CANDIDATE: none のみ）
"""
    print("  🔍 候補を探索中...")
    response = ask_thinking(prompt)

    # CANDIDATE: が一つも無い場合は none
    if not re.search(r"CANDIDATE:", response, re.IGNORECASE):
        print("  ℹ️  CANDIDATE: マーカーなし → 候補なし")
        return []

    # CANDIDATE: を直接全文から抽出（--- 区切りに依存しない）
    candidates = []
    candidate_positions = [m.start() for m in re.finditer(r"CANDIDATE:", response, re.IGNORECASE)]

    for i, pos in enumerate(candidate_positions):
        # 次のCANDIDATE:またはEOFまでをブロックとして取得
        end = candidate_positions[i + 1] if i + 1 < len(candidate_positions) else len(response)
        block = response[pos:end]

        name    = re.search(r"CANDIDATE:\s*(.+)", block, re.IGNORECASE)
        purpose = re.search(r"PURPOSE:\s*(.+)", block, re.IGNORECASE)
        query   = re.search(r"SEARCH_QUERY:\s*(.+)", block, re.IGNORECASE)

        if name:
            name_val = name.group(1).strip()
            # "none" チェック（バリアントも含む）
            if re.match(r'^none', name_val, re.IGNORECASE):
                continue
            # 有効なPyPIパッケージ名のみ受け入れる（英数字・ハイフン・アンダースコアのみ）
            if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_\-\.]*$', name_val):
                continue
            # 長すぎる名前（スペース含む等）は不正とみなす
            if len(name_val) > 80 or " " in name_val:
                continue
            candidates.append({
                "name":    name_val,
                "purpose": purpose.group(1).strip() if purpose else "",
                "query":   query.group(1).strip() if query else name_val,
            })

    return candidates
    # --- DEEP RESEARCH END ---


# =====================================================
# Step2: 深掘り調査
# =====================================================
def deep_research_candidate(candidate: dict) -> dict:
    """
    候補について複数ソースで深掘り調査する。
    """
    # --- DEEP RESEARCH START ---
    from tools.web_search import tool_web_search, tool_fetch_tech_info

    name  = candidate["name"]
    query = candidate["query"]

    print(f"  📚 深掘り調査: {name}")
    research_data = []

    # 1. PyPI で基本情報を確認
    try:
        import urllib.request
        pkg_name = name.split()[0].lower().replace("-", "_")
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{pkg_name}/json",
            timeout=10
        ) as r:
            data = json.loads(r.read())
            info = data.get("info", {})
            research_data.append({
                "source":  "pypi",
                "content": (
                    f"Package: {info.get('name')}\n"
                    f"Version: {info.get('version')}\n"
                    f"Summary: {info.get('summary')}\n"
                    f"Homepage: {info.get('home_page')}"
                )
            })
            print(f"    ✅ PyPI: {info.get('name')} v{info.get('version')}")
    except Exception:
        pass

    # 2. GitHub で実装例を検索
    try:
        r = tool_fetch_tech_info(f"{query} python example", source="github")
        if r.ok:
            research_data.append({"source": "github", "content": r.output[:600]})
            print(f"    ✅ GitHub: 実装例取得")
    except Exception:
        pass

    # 3. Web検索で使い方・チュートリアルを取得
    try:
        r = tool_web_search({"query": f"python {query} tutorial example code", "max_results": 3})
        if r.ok:
            research_data.append({"source": "web", "content": r.output[:600]})
            print(f"    ✅ Web: チュートリアル取得")
    except Exception:
        pass

    # 4. arXiv（学術系の場合）
    if any(w in query.lower() for w in ["nlp", "ml", "ai", "model", "deep"]):
        try:
            r = tool_fetch_tech_info(query, source="arxiv")
            if r.ok:
                research_data.append({"source": "arxiv", "content": r.output[:400]})
        except Exception:
            pass

    return {
        "candidate":     candidate,
        "research_data": research_data,
        "sufficient":    len(research_data) >= 2,
    }
    # --- DEEP RESEARCH END ---


# =====================================================
# Step3: 実装・テスト
# =====================================================
def _verify_pypi_package(pkg_name: str) -> bool:
    """PyPIにパッケージが実際に存在するか確認する"""
    # --- DEEP RESEARCH START ---
    import urllib.request
    try:
        name = pkg_name.replace("pip install", "").strip().split()[0]
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{name}/json",
            timeout=5
        ) as r:
            return r.status == 200
    except Exception:
        return False
    # --- DEEP RESEARCH END ---


def implement_and_test(research_result: dict) -> dict:
    """
    調査結果を元にコードを生成し、実際に動作テストする。
    """
    # --- DEEP RESEARCH START ---
    from llm import ask_thinking

    candidate = research_result["candidate"]
    data_text = "\n\n".join(
        f"[{d['source']}]\n{d['content']}"
        for d in research_result["research_data"]
    )

    prompt = f"""
以下の調査結果を元に、Pythonエージェントのツール関数を実装してください。

ツール名: {candidate['name']}
目的: {candidate['purpose']}

調査結果:
{data_text}

実装要件:
1. 関数名は tool_ で始める（例: tool_fetch_weather）
2. 引数は文字列型のみ（複雑な型は避ける）
3. 戻り値は str 型
4. エラー時は "ERROR: ..." を返す
5. 外部ライブラリが必要な場合は try/except でImportErrorを処理する
6. 動作確認用の __main__ ブロックを含める

出力形式:
TOOL_NAME: tool_xxx
REQUIRES: pip install xxx（不要なら REQUIRES: none）
CODE:
（完全なPythonコード）
END_CODE
"""
    print(f"  🔨 コード生成中: {candidate['name']}")
    response = ask_thinking(prompt)

    tool_name_m = re.search(r"TOOL_NAME:\s*(\S+)", response, re.IGNORECASE)
    requires_m  = re.search(r"REQUIRES:\s*(.+)", response, re.IGNORECASE)

    # コード抽出: 複数パターンを順番に試す
    code_m = (
        re.search(r"CODE:\s*\n(.*?)END_CODE",   response, re.DOTALL | re.IGNORECASE)
        or re.search(r"```python\s*\n(.*?)```",  response, re.DOTALL)
        or re.search(r"```\s*\n(.*?)```",        response, re.DOTALL)
    )

    if not (tool_name_m and code_m):
        # デバッグ: 失敗時に応答の先頭200文字をログ出力
        print(f"  ⚠️ コード抽出失敗 (応答先頭): {repr(response[:200])}")
        return {"success": False, "reason": "コード抽出失敗"}

    tool_name = tool_name_m.group(1).strip()
    requires  = requires_m.group(1).strip() if requires_m else "none"
    code      = code_m.group(1).strip()

    # 構文チェック
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        return {"success": False, "reason": f"構文エラー: {e}"}

    # 依存ライブラリのインストール（必要な場合）
    if requires.lower() != "none":
        pkg = requires.replace("pip install", "").strip().split()[0]

        # --- DEEP RESEARCH START ---
        if not _verify_pypi_package(pkg):
            return {
                "success": False,
                "reason":  f"PyPIに存在しないパッケージ: {pkg}"
            }
        # --- DEEP RESEARCH END ---

        print(f"  📦 インストール: {pkg}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return {"success": False, "reason": f"インストール失敗: {pkg}"}

    # 動作テスト（__main__ ブロックを実行）
    WORKSPACE.mkdir(exist_ok=True)
    test_file = WORKSPACE / f"_test_{tool_name}.py"
    test_file.write_text(code, encoding="utf-8")
    print(f"  🧪 動作テスト: {tool_name}")

    try:
        test_result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True, text=True,
            cwd=str(WORKSPACE), timeout=30,
        )
    except subprocess.TimeoutExpired:
        test_file.unlink(missing_ok=True)
        return {"success": False, "reason": "テストタイムアウト(30s)"}

    test_file.unlink(missing_ok=True)

    if test_result.returncode != 0:
        error = (test_result.stderr or test_result.stdout)[:200]
        return {"success": False, "reason": f"テスト失敗: {error}", "code": code}

    # テスト通過後の追加確認
    output = test_result.stdout + test_result.stderr
    if "ImportError" in output or "ModuleNotFoundError" in output:
        return {
            "success": False,
            "reason":  f"インポートエラーが出力に含まれる: {output[:100]}"
        }
    if test_result.stdout.strip().startswith("ERROR:"):
        return {
            "success": False,
            "reason":  f"ツールがエラーを返した: {test_result.stdout[:100]}"
        }

    print(f"  ✅ テスト通過: {tool_name}")
    return {
        "success":   True,
        "tool_name": tool_name,
        "code":      code,
        "output":    test_result.stdout[:200],
        "requires":  requires,
    }
    # --- DEEP RESEARCH END ---


# =====================================================
# Step4: ツール登録
# =====================================================
def register_tool(impl_result: dict, candidate: dict, topic_label: str) -> bool:
    """
    テスト通過したツールを tools/evolved/ に登録する。
    """
    # --- DEEP RESEARCH START ---
    EVOLVED_DIR.mkdir(parents=True, exist_ok=True)

    tool_name = impl_result["tool_name"]
    code      = impl_result["code"]
    tool_path = EVOLVED_DIR / f"{tool_name}.py"

    if tool_path.exists():
        print(f"  ℹ️  既存ツール: {tool_name}")
        return False

    header = f'''"""
自動生成ツール: {tool_name}
目的: {candidate['purpose']}
情報源: {topic_label}
生成日: {datetime.now().strftime("%Y-%m-%d")}
テスト: ✅ 通過済み
"""
'''
    tool_path.write_text(header + code, encoding="utf-8")
    print(f"  💾 登録: tools/evolved/{tool_name}.py")

    # skill_db に登録
    try:
        from skill_extractor import save_skill, Skill
        pkg = impl_result.get("requires", "none").replace("pip install", "").strip()
        skill = Skill(
            name=tool_name,
            task_example=f"[深掘り獲得] {candidate['purpose']} (from: {topic_label})",
            success_count=1,
            last_used=datetime.now(timezone.utc).isoformat(),
            tools_used=["evolved_tool"],
            key_imports=[pkg] if pkg.lower() != "none" else [],
            keywords=[topic_label] + tool_name.split("_"),
            summary=f"Deep Research により獲得。分野: {topic_label}",
        )
        save_skill(skill)
    except Exception as e:
        print(f"  ⚠️ skill_db登録スキップ: {e}")

    _log_research(tool_name, candidate, impl_result)
    return True
    # --- DEEP RESEARCH END ---


def _log_research(tool_name: str, candidate: dict, impl_result: dict):
    RESEARCH_LOG.parent.mkdir(exist_ok=True)
    with open(RESEARCH_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — {tool_name}\n")
        f.write(f"**候補:** {candidate['name']}\n")
        f.write(f"**目的:** {candidate['purpose']}\n")
        f.write(f"**テスト出力:** {impl_result.get('output', '')[:100]}\n")


# =====================================================
# メインパイプライン
# =====================================================
def run_deep_research(topic_label: str, collected_text: str) -> list:
    """
    収集テキストから候補発見 → 深掘り → 実装 → 登録 を実行する。
    research_agent.py の _evolve_from_knowledge から呼ぶ。
    """
    # --- DEEP RESEARCH START ---
    acquired = []

    # Step1: 候補発見
    candidates = discover_candidates(topic_label, collected_text)
    if not candidates:
        print(f"  ℹ️  獲得候補なし")
        return []

    print(f"  📋 候補: {[c['name'] for c in candidates]}")

    for candidate in candidates:
        print(f"\n  🎯 候補: {candidate['name']} — {candidate['purpose']}")

        # Step2: 深掘り調査
        research = deep_research_candidate(candidate)
        if not research["sufficient"]:
            print(f"  ⚠️  情報不足でスキップ: {candidate['name']}")
            continue

        # Step3: 実装・テスト
        impl = implement_and_test(research)
        if not impl["success"]:
            print(f"  ❌ 実装失敗: {impl['reason']}")
            continue

        # Step4: 登録
        registered = register_tool(impl, candidate, topic_label)
        if registered:
            acquired.append(impl["tool_name"])
            print(f"  ⚡ 機能獲得: {impl['tool_name']}")

    return acquired
    # --- DEEP RESEARCH END ---
