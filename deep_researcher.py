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
    通常モデル（高速）で候補を発見する。thinkingモデルは使わない。
    """
    # --- FAST DISCOVERY START ---
    from llm import ask_plain

    prompt = f"""以下の情報から、Pythonエージェントが新たに獲得できる機能候補を最大2つ答えてください。
分野: {topic_label}
収集情報:
{collected_text[:800]}
必須条件:
- pypi.org に実在するPythonパッケージのみ
- pip install で入手可能
- Node.js/JS系は除外
- 確信がなければ CANDIDATE: none
出力形式:
CANDIDATE: パッケージ名（例: httpx, rich, typer）
PURPOSE: 何ができるか（1行）
SEARCH_QUERY: 検索クエリ
---
"""
    print("  🔍 候補を探索中...")
    response = ask_plain(prompt)

    candidates = []
    for block in response.split("---"):
        name    = re.search(r"CANDIDATE:\s*(\S+)", block)
        purpose = re.search(r"PURPOSE:\s*(.+)",    block)
        query   = re.search(r"SEARCH_QUERY:\s*(.+)", block)
        if not name:
            continue
        raw_name = name.group(1).strip()
        if re.match(r'^none', raw_name, re.IGNORECASE):
            continue
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_\-\.]*$', raw_name):
            continue
        if len(raw_name) > 80 or " " in raw_name:
            continue
        candidates.append({
            "name":    raw_name,
            "purpose": purpose.group(1).strip() if purpose else "",
            "query":   query.group(1).strip() if query else raw_name,
        })
    return candidates
    # --- FAST DISCOVERY END ---


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
    from llm import ask_plain

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
    response = ask_plain(prompt)

    # --- CODE EXTRACT FIX START ---
    def _extract_code_from_response(resp: str) -> tuple:
        """
        LLMの応答からツール名・コード・依存ライブラリを抽出する。
        複数のパターンを試みる。{name} 等のf-string未展開を検出して除外する。
        """
        tool_name_mx = re.search(r"TOOL_NAME:\s*([a-zA-Z][a-zA-Z0-9_]+)", resp)
        requires_mx  = re.search(r"REQUIRES:\s*(.+)",                       resp, re.IGNORECASE)

        code_val = None
        patterns = [
            r"CODE:\s*\n```python\n(.*?)```\s*END_CODE",
            r"CODE:\s*\n```python\n(.*?)```",
            r"CODE:\s*\n```\n(.*?)```\s*END_CODE",
            r"CODE:\s*\n```\n(.*?)```",
            r"CODE:\s*\n(.*?)END_CODE",
            r"```python\n(def tool_\w+.*?)```",
            r"```\n(def tool_\w+.*?)```",
            r"```python\n(.*?)```",
        ]
        for pat in patterns:
            m = re.search(pat, resp, re.DOTALL | re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                # {name} 等のf-string未展開を検出して除外
                if re.search(r"\{[a-z_]+\}", candidate[:80]):
                    continue
                if len(candidate) > 50:
                    code_val = candidate
                    break

        req_val = "none"
        if requires_mx:
            req_raw = re.sub(r"pip\s+install\s+", "", requires_mx.group(1).strip(),
                             flags=re.IGNORECASE).strip()
            req_first = req_raw.split()[0] if req_raw.split() else "none"
            req_val = "none" if req_first.lower().startswith("none") else req_first

        return tool_name_mx, code_val, req_val

    tool_name_m, code, requires = _extract_code_from_response(response)
    # --- CODE EXTRACT FIX END ---

    if not (tool_name_m and code):
        # デバッグ: 失敗時に応答の先頭200文字をログ出力
        print(f"  ⚠️ コード抽出失敗 (応答先頭): {repr(response[:200])}")
        return {"success": False, "reason": "コード抽出失敗"}

    tool_name = tool_name_m.group(1).strip()

    # --- FIX FULLWIDTH START ---
    # 全角文字・全角括弧を半角に変換（LLMが全角を混入するバグ対策）
    def _normalize_code(src: str) -> str:
        replacements = {
            '（': '(', '）': ')', '「': '"', '」': '"',
            '：': ':', '；': ';', '，': ',', '。': '.',
            '　': ' ', '＃': '#', '＝': '=', '＋': '+',
            '－': '-', '＊': '*', '／': '/', '！': '!',
            '？': '?', '＜': '<', '＞': '>', '｛': '{',
            '｝': '}', '［': '[', '］': ']',
        }
        for full, half in replacements.items():
            src = src.replace(full, half)
        return src
    code = _normalize_code(code)
    # --- FIX FULLWIDTH END ---

    # 構文チェック
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        return {"success": False, "reason": f"構文エラー: {e}"}

    # --- CODE CHECK START ---
    try:
        from code_checker import check_and_fix as _check_and_fix
        print(f"  🔍 コードチェック中: {tool_name}")
        code, check_passed, check_issues = _check_and_fix(
            code=code,
            tool_name=tool_name,
            use_llm=True,
            max_fix_attempts=2,
        )
        if not check_passed:
            return {
                "success": False,
                "reason":  f"コードチェック失敗: {[i['desc'][:50] for i in check_issues[:2]]}",
            }
    except Exception as _ce:
        print(f"  ⚠️ コードチェックエラー（スキップ）: {_ce}")
    # --- CODE CHECK END ---

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

    # 動作テスト＋失敗時の原因究明・再試行ループ
    MAX_FIX_ATTEMPTS = 2
    WORKSPACE.mkdir(exist_ok=True)
    print(f"  🧪 動作テスト: {tool_name}")

    for fix_attempt in range(MAX_FIX_ATTEMPTS + 1):
        test_file = WORKSPACE / f"_test_{tool_name}.py"
        test_file.write_text(code, encoding="utf-8")

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

        # 成功判定
        output    = test_result.stdout + test_result.stderr
        has_error = (
            test_result.returncode != 0
            or "ImportError" in output
            or "ModuleNotFoundError" in output
            or test_result.stdout.strip().startswith("ERROR:")
        )

        if not has_error:
            print(f"  ✅ テスト通過: {tool_name}")
            return {
                "success":   True,
                "tool_name": tool_name,
                "code":      code,
                "output":    test_result.stdout[:200],
                "requires":  requires,
            }

        # エラー内容を収集
        error_msg = (test_result.stderr or test_result.stdout)[:500]
        if fix_attempt >= MAX_FIX_ATTEMPTS:
            print(f"    ❌ 修正上限到達: {error_msg[:80]}")
            return {"success": False, "reason": f"テスト失敗: {error_msg[:200]}", "code": code}

        # 原因究明・修正コード生成
        print(f"    🔍 エラー分析中 (試行 {fix_attempt + 1}/{MAX_FIX_ATTEMPTS})...")
        fix_prompt = f"""以下のPythonコードがエラーになりました。

【エラー内容】
{error_msg[:500]}

【元のコード】
{code[:2000]}

【修正方針】
- エラーの原因を特定して修正する
- {tool_name}の最新APIに合わせる
- ImportErrorの場合は正しいimport文に修正する
- 修正済みのコード全体を出力する（説明不要）

修正済みコード:
"""
        fixed_response = ask_plain(fix_prompt)

        if not fixed_response or len(fixed_response) < 50:
            print(f"    ❌ 修正コード生成失敗")
            return {"success": False, "reason": f"テスト失敗: {error_msg[:200]}", "code": code}

        # 修正コードを抽出（既存の _extract_code_from_response を再利用）
        _, extracted, _ = _extract_code_from_response(fixed_response)
        if extracted and len(extracted) > 50:
            code = _normalize_code(extracted)
        else:
            # フォールバック: 応答全体をコードとして扱う
            code = _normalize_code(fixed_response)

        # 構文チェック
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            print(f"    ❌ 修正コード構文エラー: {e}")
            return {"success": False, "reason": f"修正コード構文エラー: {e}"}

        print(f"    🔧 修正コードを生成・再試行 ({fix_attempt + 1}/{MAX_FIX_ATTEMPTS})...")

    return {"success": False, "reason": "テスト失敗（修正上限到達）"}
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

    # 品質チェック（登録前に自動修正）
    try:
        from code_checker import check_and_fix
        raw = tool_path.read_text(encoding="utf-8")
        final_code, passed, issues = check_and_fix(
            code=raw,
            tool_name=tool_name,
            use_llm=True,
            max_fix_attempts=2,
        )
        if final_code.strip() != raw.strip():
            tool_path.write_text(final_code, encoding="utf-8")
            print(f"  🔧 品質チェック修正済み: {tool_name}")
        if not passed:
            errors = [i for i in issues if i.get("severity") == "error"]
            if errors:
                print(f"  ❌ 品質チェック失敗（error {len(errors)}件）: 登録スキップ")
                for e in errors[:3]:
                    print(f"     [{e['rule']}] {e['desc'][:70]}")
                tool_path.unlink(missing_ok=True)
                return False
        else:
            warn_count = len([i for i in issues if i.get("severity") == "warning"])
            if warn_count:
                print(f"  ✅ 品質チェック通過（警告 {warn_count}件）")
            else:
                print(f"  ✅ 品質チェック通過")
    except Exception as e:
        print(f"  ⚠️ 品質チェックスキップ: {e}")

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
# 自己主導型ライブラリ習得
# =====================================================
# --- SELF_DIRECTED START ---
USEFUL_LIBRARIES = [
    {"name": "httpx",         "purpose": "非同期HTTPクライアント"},
    {"name": "rich",          "purpose": "リッチなターミナル出力"},
    {"name": "typer",         "purpose": "CLIアプリ構築"},
    {"name": "schedule",      "purpose": "タスクスケジューリング"},
    {"name": "loguru",        "purpose": "高機能ロギング"},
    {"name": "pydantic",      "purpose": "データバリデーション"},
    {"name": "arrow",         "purpose": "日時処理"},
    {"name": "tqdm",          "purpose": "プログレスバー"},
    {"name": "tabulate",      "purpose": "テーブル表示"},
    {"name": "python-dotenv", "purpose": "環境変数管理"},
]


def get_unacquired_libraries() -> list:
    """
    USEFUL_LIBRARIES の中でまだ tools/evolved/ にもskill_dbにもないものを返す。
    """
    existing_files = {f.stem for f in EVOLVED_DIR.glob("*.py")}
    # skill_db も確認
    skill_db_path = AGENT_ROOT / "memory" / "skill_db.json"
    existing_skills: set = set()
    if skill_db_path.exists():
        try:
            db = json.loads(skill_db_path.read_text())
            existing_skills = set(db.get("skills", {}).keys())
        except Exception:
            pass
    result = []
    for lib in USEFUL_LIBRARIES:
        tool_name = f"tool_{lib['name'].replace('-', '_')}"
        if tool_name not in existing_files and tool_name not in existing_skills:
            result.append({
                "name":    lib["name"],
                "purpose": lib["purpose"],
                "query":   f"{lib['name']} python example tutorial",
            })
    return result
# --- SELF_DIRECTED END ---


# =====================================================
# スキル応用・発展
# =====================================================
# --- SKILL EVOLUTION START ---
def evolve_existing_skills() -> list:
    """
    既存の獲得済みツールを「応用・発展」させる。
    発展パターン:
    - 単機能 → 複合機能（例: httpx単体 → httpx+パース+保存）
    - 既存ツール同士を組み合わせて新ツールを生成
    - 既存ツールに機能追加（エラー処理強化・出力形式改善等）
    """
    from llm import ask_plain

    evolved_dir = AGENT_ROOT / "tools" / "evolved"
    if not evolved_dir.exists():
        return []

    existing_tools = list(evolved_dir.glob("*.py"))
    if not existing_tools:
        return []

    # 既存ツールの内容を読み込む
    tools_summary = []
    for tool_path in existing_tools[:3]:  # 最大3個
        content = tool_path.read_text(encoding="utf-8")
        func_match = re.search(r"def (tool_\w+)\(", content)
        doc_match  = re.search(r'"""(.+?)"""', content, re.DOTALL)
        if func_match:
            func_name = func_match.group(1)
            doc = doc_match.group(1).strip()[:100] if doc_match else ""
            tools_summary.append(f"- {func_name}: {doc}")

    tools_text = "\n".join(tools_summary)

    prompt = f"""
以下は既に獲得済みのPythonツール関数です。
{tools_text}

これらを「応用・発展」させた新しいツール関数を1つ提案してください。

発展の方向性:
1. 複数ツールを組み合わせた複合ツール
2. 既存ツールに新機能を追加したもの
3. 既存ツールの出力を別の形式に変換するもの

条件:
- pypi.org に実在するライブラリのみ使う
- 既存ツールと重複しない新機能
- 実用的で汎用性が高いもの

出力形式:
CANDIDATE: ツール名（tool_で始まる）
PURPOSE: 何ができるか（1行）
SEARCH_QUERY: 実装例を探すための検索クエリ
BASED_ON: 元にした既存ツール名（なければ none）
---
"""
    try:
        response = ask_plain(prompt)
    except Exception as e:
        print(f"  ⚠️ スキル発展LLM呼び出しエラー: {e}")
        return []

    # 空応答チェック
    if not response or not response.strip():
        print(f"  ⚠️ スキル発展: LLMが空応答を返しました")
        return []

    # 候補を解析
    candidates = []
    name_m    = re.search(r"CANDIDATE:\s*(\S+)", response)
    purpose_m = re.search(r"PURPOSE:\s*(.+)",    response)
    query_m   = re.search(r"SEARCH_QUERY:\s*(.+)", response)
    based_m   = re.search(r"BASED_ON:\s*(.+)",   response)

    if name_m:
        raw = name_m.group(1).strip()
        if (not re.match(r'^none', raw, re.IGNORECASE) and
                re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_\-\.]*$', raw) and
                len(raw) <= 80):
            candidates.append({
                "name":     raw,
                "purpose":  purpose_m.group(1).strip() if purpose_m else "",
                "query":    query_m.group(1).strip() if query_m else raw,
                "based_on": based_m.group(1).strip() if based_m else "none",
            })

    if not candidates:
        return []

    # 深掘り → 実装 → テスト → 登録
    acquired = []
    for candidate in candidates:
        print(f"  🔬 スキル発展: {candidate['name']} "
              f"(based on: {candidate.get('based_on', 'none')})")
        research = deep_research_candidate(candidate)
        if not research["sufficient"]:
            continue
        impl = implement_and_test(research)
        if not impl["success"]:
            print(f"  ❌ 発展失敗: {impl['reason']}")
            continue
        registered = register_tool(impl, candidate, "スキル発展")
        if registered:
            acquired.append(impl["tool_name"])
            print(f"  ⚡ スキル発展獲得: {impl['tool_name']}")

    return acquired
# --- SKILL EVOLUTION END ---


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
