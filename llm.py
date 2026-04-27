import requests
import json
import re
import subprocess
import time
import os


# -------------------------
# SETTINGS
# -------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"
PLANNER_MODEL = "qwen2.5-coder:14b"
CODER_MODEL   = "qwen3:14b"


# -------------------------
# SYSTEM PROMPT
# -------------------------

SYSTEM_PROMPT = """
[CRITICAL RULES — HIGHEST PRIORITY]

[RULE #1 — NEVER SKIP EXECUTION]
create_file → run → (fix if error) → done
This sequence is MANDATORY. Skipping run = TASK FAILURE.

[RULE #2 — NEVER CHANGE FILENAME ON RETRY]
If create_file fails or file already exists, use edit_file on the SAME filename.
WRONG: create_file "script_v2.py" when "script.py" already exists
RIGHT: edit_file "script.py" with corrected content

[RULE #3 — VALID TOOLS ONLY]
Valid: create_file, edit_file, read_file, append_file, delete_file,
       make_dir, read_directory, diff_edit, run, run_test, done, ask_user
Invalid tool = immediate error. Never use: run_task_loop, execute, bash

[RULE #4 — DECLARE DONE IMMEDIATELY ON SUCCESS]
When run shows exit code 0 with correct output → IMMEDIATELY use {"tool": "done"}.
Do NOT add extra read_file or run after success.


RULE 4b: After EACH successful run (exit code 0), declare done IMMEDIATELY. No extra steps.
[RULE #5 — USE python NOT python3]
CORRECT: {"tool": "run", "command": "python script.py"}
WRONG:   {"tool": "run", "command": "python3 script.py"}
WRONG:   {"tool": "run", "command": "bash script.sh"}

[RULE #6 — NEVER EDIT BINARY FILES DIRECTLY]
NEVER use create_file or edit_file on .xlsx, .xls, .pdf, .docx, .db, .png, .jpg, or other binary files.
To create or modify binary files, write a Python script using the appropriate library (openpyxl, reportlab, pypdf, pandas, etc.) and run it.
WRONG: {"tool": "create_file", "path": "sales.xlsx", "content": "..."}
RIGHT: {"tool": "create_file", "path": "make_excel.py", "content": "import openpyxl; ..."}

[RULE #8 — EXCEL PYTHON CODE MUST USE PYTHON SYNTAX]
When writing Python scripts to create/read .xlsx files, ALWAYS use real Python code.
NEVER write Excel formula strings (like =SUM(...), =A1*B1) inside Python code.
NEVER run an .xlsx file as a Python script: "python sales.xlsx" is WRONG.
CORRECT Python code to create xlsx:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Month', 'Sales', 'MoM'])
    ws.append([1, 10000, 0])
    wb.save('sales.xlsx')
CORRECT Python code to read xlsx:
    import pandas as pd
    df = pd.read_excel('sales.xlsx')
    print(df)
Only .py files can be run with "python". Never "python filename.xlsx".

[RULE #7 — 情報収集ツール（秘書機能）]
web_search: 技術的な問題解決・ドキュメント検索
  {"tool": "web_search", "query": "python pandas merge dataframe"}
fetch_news: 最新ニュース収集
  {"tool": "fetch_news", "query": "AI LLM 2026"}
fetch_ranking: ランキング取得
  {"tool": "fetch_ranking", "category": "hackernews"}
  {"tool": "fetch_ranking", "category": "github"}
  {"tool": "fetch_ranking", "category": "pypi"}
search_places: 場所・店舗の検索
  {"tool": "search_places", "query": "ラーメン", "location": "渋谷"}
  {"tool": "search_places", "query": "coffee shop", "location": "Yokohama"}
fetch_tech_info: 技術・ガジェット情報（ソース自動選択）
  {"tool": "fetch_tech_info", "query": "Apple Vision Pro 2026"}
  {"tool": "fetch_tech_info", "query": "transformer architecture paper", "source": "arxiv"}
  {"tool": "fetch_tech_info", "query": "rust web framework", "source": "github"}
  {"tool": "fetch_tech_info", "query": "AI gadget news", "source": "hackernews"}
注意:
- 検索結果は参考にするだけで、そのまま実行しない
- web_search の後は必ず run で動作確認すること
- 有効なツール: create_file, edit_file, read_file, append_file, delete_file, make_dir, read_directory, diff_edit, run, run_test, done, ask_user, web_search, fetch_news, fetch_ranking, search_places, fetch_tech_info

You are an autonomous software engineering agent.

Your job is to solve the user's task by planning, writing code, executing commands, and debugging.

==============================
CRITICAL RULES
==============================

1. Respond with ONLY ONE valid raw JSON object.
2. Do NOT wrap JSON in markdown.
3. Do NOT output explanations outside JSON.
4. "thought" must be written in Japanese.
5. Never repeat the same action if the previous result shows success.

==============================
PATH RULES
==============================

- All paths are relative to workspace root.
- NEVER include "workspace/" in paths.
- Do NOT create hidden files.
- Do NOT create filenames starting with "." or "._".

Correct:
    scraper.py

Wrong:
    .scraper.py
    ._scraper.py

==============================
TOOL SELECTION RULES
==============================

create_file
    Use when creating a new file.

edit_file
    Overwrite entire file content.

append_file
    Add content to the end of file.

diff_edit
    Use when modifying a small part of a file.

read_file
    Read file content before editing.

read_directory
    Inspect directory structure.

make_dir
    Create directory.

run
    Execute a command.

done
    Finish the task.

answer
    Provide the final response to the user.

==============================
RUN TOOL
==============================

Use run for commands like:

python script.py
pytest
pip install package
curl https://example.com

Example:

{
 "thought": "yahooにHTTPリクエストを送るためcurlを実行する",
 "tool": "run",
 "command": "curl https://www.yahoo.com"
}

==============================
EXTERNAL TASK CHECKLIST
==============================

- 外部URLやPDF生成タスクでは、実行前に疎通確認（curl -I 等）と出力先の書き込み権限を確認する。
- 成果物は `ls -l` などで存在確認し、タイトル抽出などの内容検証も行う。
- ネットワーク障害時は標準ライブラリやキャッシュへ切り替え、両方失敗した場合は原因を示して次の手段を相談する。

==============================
RESEARCH WORKFLOW
==============================

- 研究ゴールが与えられたら `search_knowledge` で既存知識を先に確認する。
- 研究ゴールが与えられたら `create_research_plan` で 3〜5 件のクエリに分割する。
- 各クエリで `search_web` → `fetch_page` を行い、必要に応じて `extract_text` を使う。
- 収集後は `generate_report` にゴールを渡して統合レポートを作成する。

==============================
WEB RESEARCH WORKFLOW
==============================

If web search is used, follow this pipeline strictly:

search_web
→ fetch_page (top 3 results)
→ extract_text
→ summarize_text
→ generate_report
→ answer

Do NOT call search_web repeatedly for the same query.
When search_web returns results, choose the first valid URL and proceed.
extract_text must only be used on raw HTML, not file paths.
extract_text ONLY accepts the "html" field. Do NOT send "path" or "content".
Never repeat extract_text multiple times.
After summarize_text, finish with answer.

==============================
AUTONOMOUS TASK LOOP
==============================

- ゴールから `run_task_loop` を実行し、タスクキューを処理する。
- 実行中に `discover_subgoals` の結果をキューへ追加し、最大 10 タスクで停止する。
- 最後に統合レポートを生成する。

==============================
LOOP PREVENTION
==============================

Before acting ask yourself:

- Did the previous step already succeed?
- Am I repeating the same action?
- If yes → choose a different tool.

Never repeat identical edits.

==============================
TASK COMPLETION
==============================

Before declaring done, you MUST verify your work:
1. If you created or edited a Python file, run it first: {"tool": "run", "command": "python filename.py"}
2. Confirm the output matches the task requirement.
3. Only AFTER a successful run (exit code 0 with correct output) declare done.

NEVER declare done immediately after creating a file — always run it first.

{
 "thought": "実行して出力を確認したため終了する",
 "tool": "done"
}

==============================
DONE DECLARATION — MANDATORY
==============================

You MUST output {"tool": "done"} immediately when ANY of these conditions is met:
1. The final verification command ran and showed the expected output
2. All tests passed (output contains "OK" or "passed")
3. The file was created and confirmed to work (exit code 0 with correct output)
4. You have run the same verification command twice and it succeeded both times

DO NOT continue with read_file, run, or any other tool after success.
DO NOT wait to complete all plan steps if the goal is already achieved.
Continuing after success wastes compute and is considered a failure.

==============================
OUTPUT FORMAT
==============================

{
 "thought": "日本語の思考",
 "tool": "tool_name",

 "path": "file.py",
 "content": "file content or answer text",

 "old": "old text",
 "new": "new text",

 "command": "shell command"
}

==============================
EXECUTION RULE — MANDATORY
==============================

After creating or editing a Python file, your NEXT action MUST be:
  {"tool": "run", "command": "python <filename>"}

NEVER create a file and then stop or call done without running it first.
If the task asks to "write and run", BOTH steps are required before done.
If the file already exists (Error: File already exists), use edit_file instead.

==============================
VALID TOOL NAMES — USE ONLY THESE
==============================

create_file, edit_file, read_file, append_file, delete_file,
make_dir, read_directory, diff_edit, run, run_test, done, answer

Any other tool name will cause an ERROR. Never invent tool names.
"""


# -------------------------
# CLEAN LLM OUTPUT
# -------------------------

def _clean_llm_output(text: str) -> str:
    """
    LLMの出力からJSONを安全に抽出する。
    JSONラップ用の ```json ... ``` のみ除去する。
    通常のコードブロック（```python 等）は除去しない。
    この関数は ask() / _call_ollama() 経由のみで呼ばれる（JSON応答専用）。
    """
    text = text.strip()

    # ```json のみ除去（JSONのラッパーブロック開始タグ）
    text = re.sub(r"```json\s*", "", text)

    # JSON抽出: { から } の範囲を取り出す
    start = text.find("{")
    end   = text.rfind("}")

    if start == -1 or end == -1:
        # JSONが見つからない場合は末尾の単独 ``` だけ除去して返す
        text = re.sub(r"^```\s*$", "", text, flags=re.MULTILINE)
        return text.strip()

    # JSON外の ``` ラッパーは除去されているので、そのまま返す
    return text[start:end + 1].strip()


# -------------------------
# OLLAMA CALL
# -------------------------

_RETRY_WAITS = [2, 4, 8]  # 指数バックオフ (秒)


def _call_ollama(model: str, prompt: str, system: str = "", label: str = "AGENT") -> str:
    import time

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 16384,
        },
    }

    last_error = ""

    for attempt, wait in enumerate([0] + _RETRY_WAITS):

        if wait:
            print(f"[llm] Ollama接続失敗 → {wait}秒後にリトライ ({attempt}/{len(_RETRY_WAITS)})")
            time.sleep(wait)

        try:
            resp = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=300
            )
            resp.raise_for_status()
            data = resp.json()
            return _clean_llm_output(data["message"]["content"])

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_error = str(e)
            continue

        except Exception as e:
            # 接続・タイムアウト以外は即座に失敗扱い (HTTPエラー等)
            last_error = str(e)
            break

    return json.dumps(
        {
            "thought": f"Ollama接続エラー (3回リトライ後も失敗): {last_error}",
            "tool": "ask_user",
            "question": "Ollama接続に失敗しました。サービスが起動しているか確認してください。",
        }
    )


# -------------------------
# AGENT MODE
# -------------------------

def ask_model(model: str, prompt: str, system: str, label: str) -> str:
    return _call_ollama(
        model=model,
        prompt=prompt,
        system=system,
        label=label
    )


def ask_coder(prompt: str) -> str:
    """
    Agent call (expects JSON).
    """

    return ask_model(
        model=CODER_MODEL,
        prompt=prompt,
        system=SYSTEM_PROMPT,
        label="AGENT THOUGHT"
    )


# -------------------------
# PLAIN MODE (PLANNER)
# -------------------------

def ask_planner(prompt: str) -> str:
    """
    Planner call (plain text).
    """

    system = """
You are a senior software architect.

Respond in Japanese.

Rules:
- Output plain text only
- Do NOT output JSON
- Do NOT output markdown
"""

    result = ask_model(
        model=PLANNER_MODEL,
        prompt=prompt,
        system=system,
        label="PLANNER"
    )

    return result.strip()


# Backward compatibility
def ask(prompt: str) -> str:
    return ask_coder(prompt)


def get_loaded_models() -> list:
    """現在Ollamaにロードされているモデルを取得する"""
    try:
        resp = requests.get(
            "http://localhost:11434/api/ps",
            timeout=5,
        )
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return [m.get("name", "") for m in models]
    except Exception:
        pass
    return []


def unload_model(model: str = None):
    """モデルをアンロードする（ロード済みの場合のみ）"""
    target = model or CODER_MODEL
    loaded = get_loaded_models()
    # ロードされていなければスキップ
    if not any(target.split(":")[0] in m for m in loaded):
        return
    try:
        requests.post(
            "http://localhost:11434/api/chat",
            json={"model": target, "messages": [], "keep_alive": 0},
            timeout=10,
        )
        print(f"  🗑️ アンロード: {target}")
    except Exception:
        pass


def ask_plain(prompt: str, retries: int = 3, timeout: int = 1200, max_tokens: int = 1024) -> str:
    """
    Plain-text generation for articles / planning.
    _call_ollama を経由しないことで _clean_llm_output（コードブロック除去・
    JSON切り取り）を回避する。num_predict=8192 で生成トークン上限を拡張。
    タイムアウト時はモデルアンロード後にリトライする。
    timeout: HTTP タイムアウト秒（デフォルト600。分類など短文生成は30など短縮可）
    """
    import time

    # THINKING_MODELがロード済みの場合のみアンロード
    unload_model(THINKING_MODEL)

    for attempt in range(retries):
        if attempt > 0:
            wait = 10 * attempt  # 10秒・20秒・30秒
            print(f"  ⏳ Ollama待機中 ({wait}秒)...")
            time.sleep(wait)
        try:
            resp = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model":    PLANNER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream":   False,
                    "options": {
                        "temperature": 0.7,
                        "num_ctx":     max(4096, max_tokens + 512),
                        "num_predict": max_tokens,
                    },
                    "keep_alive": 120,
                },
                timeout=(10, timeout),
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
        except requests.exceptions.Timeout:
            print(f"  ⚠️ Ollamaタイムアウト (試行 {attempt+1}/{retries})")
            try:
                unload_model(PLANNER_MODEL)
                time.sleep(5)
            except Exception:
                pass
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"[llm] ask_plain 接続失敗 → リトライ ({attempt+1}/{retries}): {e}")
        except Exception as e:
            print(f"  ⚠️ Ollama接続エラー: {e} (試行 {attempt+1}/{retries})")
            time.sleep(5)

    print(f"[llm] ask_plain 全リトライ失敗 → ask_planner にフォールバック")
    return ask_planner(prompt)


# --- DUAL MODEL START ---
# 思考型モデル（深い推論が必要な場面のみ使用）
THINKING_MODEL = "qwen3:14b"


def ask_thinking(prompt: str, label: str = "THINKING") -> str:
    """
    深い推論が必要な場面でのみ呼ぶ。
    通常の ask() より遅いが、複雑な問題に強い。
    使用場面:
    - 複雑なタスクの初回プラン生成
    - 何度修復しても失敗するタスクの根本原因分析
    - アーキテクチャ設計の相談
    """
    import time as _time

    # CODER_MODELがロード済みの場合のみアンロード
    unload_model(CODER_MODEL)
    _time.sleep(2)

    payload = {
        "model":    THINKING_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream":   False,
        "think":    False,  # thinkingモード無効（トップレベルに置く必要あり）
        "options": {
            "temperature": 0.6,
            "num_ctx":     8192,
            "num_predict": 512,   # レビュー回答は短い（SCORE/ISSUES/VERDICT/FEEDBACK）
        },
        "keep_alive": 0,  # 使用後即アンロード
    }
    try:
        import requests as _req
        print(f"  🧠 Thinking ({THINKING_MODEL})...", end=" ", flush=True)
        t0 = _time.time()
        resp = _req.post(OLLAMA_URL, json=payload, timeout=600)
        resp.raise_for_status()
        data = resp.json()
        elapsed = _time.time() - t0
        print(f"done ({elapsed:.1f}s)")
        result = data["message"]["content"].strip()
        clean = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL)
        return clean.strip() or result.strip()
    except requests.exceptions.Timeout:
        print(f"タイムアウト → ask_plainにフォールバック")
        return ask_plain(prompt)
    except Exception as e:
        print(f"  ⚠️ thinking model失敗 ({e}) → 通常モデルにフォールバック")
        return ask_plain(prompt)
# --- DUAL MODEL END ---


def ask_finance(prompt: str, max_tokens: int = 4000, retries: int = 3) -> str:
    """
    投資記事生成専用。qwen3:14bを使用。
    qwen2.5-coder:14bは中国語混入・架空補完が多いため
    汎用モデルのqwen3:14bを使用する。
    max_tokens: 生成トークン上限（Ollamaのnum_predictに渡す）
    """
    import time

    # 言語強制: systemプロンプトで中国語・韓国語を禁止 + 免責事項の挿入を義務付け
    _system = (
        "You must respond in Japanese only. "
        "Do not use Chinese characters (简体字/繁體字), Korean, "
        "or any language other than Japanese. "
        "Do not output your thinking process. "
        "記事の末尾に必ず以下の免責事項を追加してください: "
        "「※本記事は情報提供を目的としており、投資の推奨・勧誘を行うものではありません。"
        "投資に関する最終判断はご自身の責任でお願いいたします。」"
    )

    unload_model(PLANNER_MODEL)  # qwen2.5-coder:14bをアンロードしてqwen3:14b用にVRAM確保
    time.sleep(2)
    for attempt in range(retries):
        try:
            if attempt > 0:
                wait = 10 * attempt
                print(f"  ⏳ Ollama待機中 ({wait}秒)...")
                time.sleep(wait)
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model":    THINKING_MODEL,  # qwen3:14b
                    "messages": [
                        {"role": "system", "content": _system},
                        {"role": "user",   "content": prompt},
                    ],
                    "stream":   False,
                    "think":    False,  # thinkingモード無効（トップレベルに置く必要あり）
                    "options": {
                        "temperature": 0.5,
                        "num_ctx":     max(8192, max_tokens + 512),
                        "num_predict": max_tokens,
                    },
                    "keep_alive": 60,
                },
                timeout=600,
            )
            response.raise_for_status()
            raw = response.json()["message"]["content"]
            # <think>...</think> タグを除去
            clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            return clean.strip() or raw.strip()
        except requests.exceptions.Timeout:
            print(f"  ⚠️ タイムアウト (試行 {attempt+1}/{retries})")
            unload_model(THINKING_MODEL)
            time.sleep(5)
        except Exception as e:
            print(f"  ⚠️ エラー: {e} (試行 {attempt+1}/{retries})")
            time.sleep(5)
    print("[llm] ask_finance 全リトライ失敗 → ask_plain にフォールバック")
    return ask_plain(prompt)


# -------------------------
# AI STOCK ANALYSIS
# -------------------------

def _find_news_for_stock(stock_name: str, news_list: list) -> str:
    """
    銘柄名に関連するニュースを検索する。
    株式会社等の一般語を除去した名称で部分一致検索する。
    見つかった場合はタイトルを最大2件返す。見つからない場合は空文字を返す。
    """
    name_clean = re.sub(r'[（(）)株式会社ホールディングスグループ]', '', stock_name).strip()
    # 短すぎる名前は誤マッチ防止のため検索しない
    if len(name_clean) < 2:
        return ""
    found = []
    for item in news_list:
        title = item.get("title", "") + " " + item.get("summary", "")
        if name_clean in title:
            found.append(item.get("title", ""))
    return "、".join(found[:2]) if found else ""


def analyze_stock_background(stocks: list, market_context: dict) -> dict:
    """
    ランキング上位銘柄の値動き背景をAIで推定する。
    確認できない理由は創作せず「個別材料は確認されていません」と明記させる。
    stocks: ["1. 企業名 (+21.38%)", ...] 形式のリスト
    market_context: finance_data dict（market_summary / macro 等を含む）
    Returns: {"銘柄名": "背景テキスト", ...}
    """
    if not stocks:
        return {}

    market_summary = market_context.get("market_summary", {})
    macro  = market_context.get("macro", {})
    forex  = macro.get("forex", {})
    us     = macro.get("us_stocks", {})
    comm   = macro.get("commodities", {})

    nikkei        = market_summary.get("nikkei_price", "N/A")
    nikkei_change = market_summary.get("nikkei_change", "")
    usd_jpy       = forex.get("USD/JPY", {}).get("price", "N/A")
    sp500         = us.get("S&P500", {}).get("price", "N/A")
    vix_price     = us.get("VIX", {}).get("price", "N/A")
    vix_chg       = us.get("VIX", {}).get("change_pct") or 0.0
    wti           = comm.get("WTI原油", {}).get("price", "N/A")

    # 日経変動方向
    try:
        m = re.search(r'([+-]?\d+\.?\d*)', str(nikkei_change))
        nikkei_chg_val = float(m.group(1)) if m else 0.0
    except Exception:
        nikkei_chg_val = 0.0
    market_mood = "上昇" if nikkei_chg_val >= 0 else "下落"

    # VIX方向
    try:
        vix_float = float(vix_price)
    except Exception:
        vix_float = 20.0
    vix_dir = "上昇（リスクオフ）" if float(vix_chg) > 0 else "低下（リスクオン）"

    # USD/JPY float
    try:
        usdjpy_float = float(str(usd_jpy).replace(",", ""))
    except Exception:
        usdjpy_float = 0.0

    # ニュース一覧（フィルタ済み優先）
    news_all = market_context.get("news_filtered") or market_context.get("news", [])

    # ニュース見出し一覧（プロンプト用）
    news_summary_lines = [f"- {n.get('title', '')}" for n in news_all[:8] if n.get("title")]
    news_summary = "\n".join(news_summary_lines) if news_summary_lines else "（本日のニュース情報なし）"

    # 銘柄ごとにニュース照合を実施してプロンプトに含める
    stocks_lines = []
    for s in stocks:
        m2 = re.match(r'^\d+\.\s*(.+?)\s*\(', s)
        raw_name = m2.group(1).strip() if m2 else s
        related = _find_news_for_stock(raw_name, news_all)
        entry = s
        if related:
            entry += f"\n  関連ニュース: {related}"
        stocks_lines.append(entry)
    stocks_text = "\n".join(stocks_lines)

    prompt = f"""/no_think
本日の日本株市場で以下の銘柄が急騰・急落しました。
各銘柄の背景を分析してください。

【重要なルール】
- 本日のニュース・適時開示に記載がない理由は書かない
- 確認できない場合は「個別材料は確認されていません」と書く
- 「業績悪化」「競争激化」「収益性低下」等の中長期要因をその日の急騰・急落理由として書かない
- セクター全体の動きや需給・マクロから推定できる場合のみ推定を記述する
- 推定する場合は必ず「〜の可能性があります」「〜と見られます」と断定を避ける
- 各銘柄「関連ニュース」の記載があればそれを優先して根拠に使う

【本日の市場環境】
日経平均: {nikkei}円 ({nikkei_change}、{market_mood})
VIX: {vix_float:.2f}（{vix_dir}）
USD/JPY: {usdjpy_float:.3f}円
S&P500: {sp500} / WTI原油: {wti}

【本日の主要ニュース（適時開示・ニュース）】
{news_summary}

【対象銘柄】
{stocks_text}

【出力形式】（各銘柄1行、パイプ区切り）
銘柄名 | 背景（確認できた場合のみ。不明なら「個別材料は確認されていません。需給主導の動きと見られます。」） | 注意点

例（確認できない場合）:
はてな(株) | 個別材料は確認されていません。需給主導の動きと見られます。 | 急落後の反発に注意
中外製薬(株) | 個別材料は確認されていません。セクター全体の動きと見られます。 | 中期保有者は様子見を

例（確認できた場合）:
○○(株) | 本日の適時開示で下方修正を発表。業績懸念による売りと見られます。 | 続落リスクあり"""

    try:
        result = ask_plain(prompt, max_tokens=768, timeout=120)
        backgrounds = {}
        for line in result.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-") or line.startswith("例"):
                continue
            if "|" in line:
                parts = line.split("|")
                name = parts[0].strip().lstrip("0123456789. 　")
                bg   = parts[1].strip() if len(parts) > 1 else ""
            elif ":" in line:
                # 旧形式フォールバック
                parts = line.split(":", 1)
                name = parts[0].strip().lstrip("0123456789. 　")
                bg   = parts[1].strip()
            else:
                continue
            if name and bg and len(name) < 30:
                backgrounds[name] = bg
        return backgrounds
    except Exception as e:
        print(f"  ⚠️ 銘柄背景推定失敗: {e}")
        return {}


_FINANCE_KEYWORDS = [
    "株", "円", "経済", "日銀", "金利", "企業", "決算",
    "半導体", "AI", "輸出", "原油", "為替", "投資", "市場",
    "上場", "株価", "利下げ", "利上げ", "景気", "物価",
]


def _keyword_fallback(news_list: list, max_count: int) -> list:
    """
    キーワードベースで経済・投資関連ニュースを優先選択する。
    AIフィルタリングが0件を返した場合のフォールバック。
    """
    priority = []
    rest     = []
    for n in news_list:
        title = n.get("title", "")
        if any(kw in title for kw in _FINANCE_KEYWORDS):
            priority.append(n)
        else:
            rest.append(n)
    selected = (priority + rest)[:max_count]
    print(f"  🔄 キーワードフォールバック: {len(priority)}件優先 → {len(selected)}件選択")
    return selected


def filter_investment_news(news_list: list, max_count: int = 5) -> list:
    """
    ニュース一覧から日本株市場に最も関連するものをAIで選択する。
    news_list: [{"title": ..., "summary": ..., "source": ...}, ...] 形式
    Returns: 選択されたニュースdictのリスト
    フォールバック順: キーワード優先選択 → 先頭max_count件
    """
    if not news_list:
        return []

    # 候補がmax_count以下ならAIフィルタリング不要
    if len(news_list) <= max_count:
        return news_list

    candidates = news_list[:20]  # 最大20件を候補に
    news_lines = []
    for i, n in enumerate(candidates):
        title   = n.get("title", "")
        summary = n.get("summary", "")[:80]
        news_lines.append(f"{i + 1}. {title}（{summary}）")
    news_str = "\n".join(news_lines)

    prompt = f"""/no_think
以下のニュース一覧から、本日の日本株市場に最も関連するニュースを{max_count}件選んでください。

【ニュース一覧】
{news_str}

【選択基準】
1. 日本の上場企業に直接影響するニュース
2. 為替・金利・原油などマクロ要因
3. 政府の経済政策・規制
4. 米国株・中国経済の動向

選んだニュースの番号のみを改行区切りで出力してください（例）:
1
3
7"""

    try:
        result  = ask_plain(prompt, max_tokens=64, timeout=60)
        indices = []
        for line in result.strip().split("\n"):
            m = re.search(r'\d+', line.strip())
            if m:
                idx = int(m.group()) - 1  # 0-indexed
                if 0 <= idx < len(candidates):
                    indices.append(idx)
        # 重複除去・挿入順維持
        seen, unique = set(), []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                unique.append(idx)
        selected = [candidates[i] for i in unique[:max_count]]

        # AIが0件を返した場合はキーワードフォールバック
        if not selected:
            print("  ⚠️ AIフィルタが0件返却 → キーワードフォールバック")
            return _keyword_fallback(news_list, max_count)

        return selected
    except Exception as e:
        print(f"  ⚠️ ニュースフィルタリング失敗: {e}")
        return _keyword_fallback(news_list, max_count)
