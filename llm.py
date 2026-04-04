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


def ask_plain(prompt: str, retries: int = 3, timeout: int = 1200) -> str:
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
                        "num_ctx":     4096,
                        "num_predict": 1024,
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
        "options": {
            "temperature": 0.6,
            "num_ctx":     8192,
            "num_predict": 4096,
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


# -------------------------
# LLM-JP-4 (llama.cpp server)
# -------------------------

LLAMA_CPP_BIN    = os.path.expanduser("~/llama.cpp/build/bin/llama-server")
LLM_JP4_MODEL    = (
    "/Volumes/ESD-EHA/Ollama/models/blobs/"
    "sha256-71db039fff933c395fefe5cdbc10f1ba1dce677e5772eacf64f61b287d9b440b"
)
LLAMA_SERVER_PORT = 8080

# ollama バイナリのフルパス（PATH未設定環境対応）
_OLLAMA_BIN = next(
    (p for p in [
        "/opt/homebrew/Cellar/ollama/0.18.0/bin/ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
        "/usr/local/bin/ollama",
        "/opt/homebrew/bin/ollama",
    ] if os.path.exists(p)),
    "ollama",  # フォールバック: PATHに任せる
)

_llama_server_proc = None


def start_llm_jp4() -> bool:
    """llama.cppサーバーをllm-jp-4で起動する。Ollamaを先に停止する。"""
    global _llama_server_proc

    # Ollama確実停止（SIGTERM → SIGKILL の2段階）
    print("  🔄 Ollama停止中...")
    subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", "ollama serve"], capture_output=True)
    time.sleep(5)  # メモリ解放を待つ

    # llama.cppサーバー起動
    print("  🚀 llm-jp-4 起動中...")
    _llama_server_proc = subprocess.Popen(
        [
            LLAMA_CPP_BIN,
            "-m", LLM_JP4_MODEL,
            "--port", str(LLAMA_SERVER_PORT),
            "--ctx-size", "4096",
            "--n-predict", "2048",
            "--host", "127.0.0.1",
            "--chat-template", "chatml",
            "--no-mmap",
            "-ngl", "99",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # ヘルスチェック（最大60秒待機）
    for _ in range(60):
        try:
            r = requests.get(
                f"http://127.0.0.1:{LLAMA_SERVER_PORT}/health", timeout=1
            )
            if r.status_code == 200:
                print("  ✅ llm-jp-4 起動完了")
                return True
        except Exception:
            pass
        time.sleep(1)

    print("  ❌ llm-jp-4 起動失敗（タイムアウト）")
    return False


def stop_llm_jp4():
    """llama.cppサーバーを停止してOllamaを再起動する。"""
    global _llama_server_proc

    if _llama_server_proc:
        print("  🔄 llm-jp-4 停止中...")
        _llama_server_proc.terminate()
        _llama_server_proc.wait()
        _llama_server_proc = None
        time.sleep(2)

    # Ollama再起動
    print("  🚀 Ollama再起動中...")
    subprocess.Popen(
        [_OLLAMA_BIN, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    print("  ✅ Ollama起動完了")


def ask_finance_llmjp4(prompt: str, system_msg: str = "") -> str:
    """llm-jp-4（llama.cppサーバー）でテキスト生成する。"""
    if not system_msg:
        system_msg = (
            "あなたは日本語の投資記事を書く専門家です。"
            "ですます体で、事実のみを記述してください。"
            "中国語・韓国語は使用禁止です。"
        )
    try:
        response = requests.post(
            f"http://127.0.0.1:{LLAMA_SERVER_PORT}/v1/chat/completions",
            json={
                "model": "llm-jp-4",
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": prompt},
                ],
                "max_tokens": 2048,
                "temperature": 0.7,
            },
            timeout=300,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        # 特殊トークン・重複出力を除去
        text = re.sub(r"<\|im_(end|start)\|>.*", "", text, flags=re.DOTALL)
        text = re.sub(r"<\|[^|]+\|>", "", text)  # 残存特殊トークン
        return text.strip()
    except Exception as e:
        print(f"  ❌ llm-jp-4生成失敗: {e}")
        return ""


def ask_finance(prompt: str, retries: int = 3) -> str:
    """
    投資記事生成専用。qwen3:14bを使用。
    qwen2.5-coder:14bは中国語混入・架空補完が多いため
    汎用モデルのqwen3:14bを使用する。
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

    unload_model(CODER_MODEL)
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
                    "options": {
                        "temperature": 0.5,
                        "num_ctx":     4096,
                        "num_predict": 1024,
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
