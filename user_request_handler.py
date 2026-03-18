"""
ユーザーリクエストハンドラー。

ユーザーの自然言語リクエストを受け取り:
1. 既存ツールで対応可能か判断
2. 不足情報を選択式で収集
3. 必要ならツールを自動生成
4. タスクを実行して結果を返す
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

AGENT_ROOT   = Path(__file__).parent
EVOLVED_DIR  = AGENT_ROOT / "tools" / "evolved"
WORKSPACE    = AGENT_ROOT / "workspace"


# =====================================================
# メインエントリ
# =====================================================

def handle_user_request(user_input: str) -> str:
    """
    ユーザーリクエストを処理する。

    Args:
        user_input: ユーザーの自然言語リクエスト

    Returns:
        実行結果のメッセージ
    """
    print(f"\n{'='*50}")
    print(f"  リクエスト: {user_input}")
    print(f"{'='*50}")

    # Step1: リクエストを分析
    analysis = _analyze_request(user_input)
    print(f"\n📋 分析結果:")
    print(f"  タスク種別: {analysis['task_type']}")
    print(f"  必要なツール: {analysis['tool_needed']}")
    print(f"  対象ファイル: {analysis['target_file'] or '未指定'}")

    # Step2: 既存ツールを確認
    existing_tool = _find_existing_tool(analysis['tool_needed'])
    if existing_tool:
        print(f"\n✅ 既存ツール使用: {existing_tool}")
    else:
        print(f"\n🔨 新規ツール生成が必要: {analysis['tool_needed']}")

    # Step3: 不足情報を収集（選択式）
    params = _collect_parameters(analysis, user_input)
    if params is None:
        return "キャンセルしました。"

    # Step4: ツール生成（必要な場合）
    if not existing_tool:
        tool_path = _generate_tool(analysis, params)
        if not tool_path:
            return "ツールの生成に失敗しました。"
        existing_tool = tool_path

    # Step5: タスク実行
    result = _execute_task(existing_tool, analysis, params)
    return result


# =====================================================
# Step1: リクエスト分析
# =====================================================

def _analyze_request(user_input: str) -> dict:
    """ユーザーリクエストを分析してタスク情報を抽出する"""
    from llm import ask_plain

    prompt = f"""以下のユーザーリクエストを分析してください。

リクエスト: {user_input}

以下の形式で回答してください:
TASK_TYPE: ファイル操作の種別（例: pdf_split, pdf_merge, pdf_watermark, excel_convert等）
TOOL_NEEDED: 必要なツール関数名（tool_で始まる、例: tool_pdf_split）
TARGET_FILE: 対象ファイルのパスまたは種類（不明な場合はunknown）
OPERATION: 具体的な操作内容（1行）
REQUIRES_PARAMS: 追加で必要な情報のリスト（カンマ区切り、不要ならnone）
"""
    response = ask_plain(prompt)

    task_type   = re.search(r"TASK_TYPE:\s*(\S+)",      response)
    tool_needed = re.search(r"TOOL_NEEDED:\s*(\S+)",    response)
    target_file = re.search(r"TARGET_FILE:\s*(.+)",     response)
    operation   = re.search(r"OPERATION:\s*(.+)",       response)
    req_params  = re.search(r"REQUIRES_PARAMS:\s*(.+)", response)

    return {
        "task_type":   task_type.group(1).strip()   if task_type   else "unknown",
        "tool_needed": tool_needed.group(1).strip() if tool_needed else "tool_custom",
        "target_file": target_file.group(1).strip() if target_file else None,
        "operation":   operation.group(1).strip()   if operation   else user_input,
        "requires_params": [
            p.strip() for p in req_params.group(1).split(",")
        ] if req_params and req_params.group(1).lower() != "none" else [],
    }


# =====================================================
# Step2: 既存ツールの検索
# =====================================================

def _find_existing_tool(tool_name: str) -> str | None:
    """既存ツールを検索する（部分一致も対応）"""
    if EVOLVED_DIR.exists():
        exact = EVOLVED_DIR / f"{tool_name}.py"
        if exact.exists():
            return str(exact)
        for f in EVOLVED_DIR.glob("*.py"):
            if tool_name.replace("tool_", "") in f.stem:
                return str(f)

    tools_dir = AGENT_ROOT / "tools"
    for f in tools_dir.glob("*.py"):
        if tool_name.replace("tool_", "") in f.stem:
            return str(f)

    return None


# =====================================================
# Step3: パラメータ収集（選択式UI）
# =====================================================

PARAMETER_OPTIONS = {
    "font": {
        "question": "使用するフォントを選択してください:",
        "options": [
            "1. Helvetica（英数字のみ・シンプル）",
            "2. Times-Roman（英数字のみ・書体）",
            "3. IPAゴシック（日本語対応）",
            "4. IPAex明朝（日本語対応）",
            "5. NotoSansCJK（日本語・中国語・韓国語対応）",
        ],
        "values": ["Helvetica", "Times-Roman", "IPAGothic", "IPAexMincho", "NotoSansCJK"],
    },
    "font_size": {
        "question": "フォントサイズを選択してください:",
        "options": ["1. 8pt（小）", "2. 10pt（標準）", "3. 12pt（やや大）",
                    "4. 14pt（大）", "5. 18pt（特大）"],
        "values": [8, 10, 12, 14, 18],
    },
    "color": {
        "question": "文字色を選択してください:",
        "options": ["1. 黒", "2. グレー", "3. 赤", "4. 青", "5. カスタム（RGB入力）"],
        "values": [(0, 0, 0), (0.5, 0.5, 0.5), (1, 0, 0), (0, 0, 1), "custom"],
    },
    "position": {
        "question": "テキストの位置を選択してください:",
        "options": ["1. 右上", "2. 左上", "3. 中央上", "4. 右下", "5. 中央"],
        "values": ["top_right", "top_left", "top_center", "bottom_right", "center"],
    },
    "split_method": {
        "question": "分割方法を選択してください:",
        "options": ["1. 1ページずつ分割", "2. 指定ページ数ごとに分割",
                    "3. ページ番号を指定して分割"],
        "values": ["single", "chunk", "specific"],
    },
    "output_format": {
        "question": "出力形式を選択してください:",
        "options": ["1. PDF", "2. PNG（画像）", "3. テキスト", "4. Excel"],
        "values": ["pdf", "png", "text", "excel"],
    },
}


def _collect_parameters(analysis: dict, user_input: str) -> dict | None:
    """
    タスクに必要なパラメータを選択式UIで収集する。
    """
    params = {}
    task_type = analysis["task_type"]

    # 対象ファイルの確認
    target = analysis.get("target_file", "unknown")
    if not target or target in ("unknown", "None"):
        print("\n📁 対象ファイルを指定してください:")
        file_input = input("  ファイルパス > ").strip()
        if not file_input:
            return None
        params["input_file"] = file_input
    else:
        params["input_file"] = target

    # タスク種別に応じたパラメータ収集
    task_param_map = {
        "pdf_split":     ["split_method"],
        "pdf_merge":     [],
        "pdf_watermark": ["position", "font", "font_size", "color"],
        "pdf_convert":   ["output_format"],
        "excel_convert": ["output_format"],
    }

    required = task_param_map.get(task_type, analysis.get("requires_params", []))

    for param_key in required:
        if param_key in PARAMETER_OPTIONS:
            value = _ask_selection(param_key)
            if value is None:
                return None
            params[param_key] = value

            # カスタムカラーの場合
            if param_key == "color" and value == "custom":
                print("  RGB値を入力してください（例: 255 0 0 で赤）:")
                rgb_input = input("  R G B > ").strip().split()
                if len(rgb_input) == 3:
                    params["color"] = tuple(int(v) / 255 for v in rgb_input)

    # ウォーターマーク系はテキスト入力が必要
    if "watermark" in task_type or "stamp" in user_input or "印字" in user_input:
        print("\n✏️  入力するテキストを教えてください:")
        text_input = input("  テキスト > ").strip()
        params["text"] = text_input

    # 出力先
    print(f"\n📂 出力先フォルダ（Enterでworkspaceに保存）:")
    output_dir = input("  > ").strip()
    params["output_dir"] = output_dir if output_dir else str(WORKSPACE)

    return params


def _ask_selection(param_key: str):
    """選択式UIを表示してユーザーの選択を受け取る"""
    option_def = PARAMETER_OPTIONS[param_key]
    print(f"\n{option_def['question']}")
    for opt in option_def["options"]:
        print(f"  {opt}")

    while True:
        choice = input("  番号を入力 > ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(option_def["values"]):
                selected = option_def["values"][idx]
                print(f"  ✅ 選択: {option_def['options'][idx]}")
                return selected
        if choice.lower() in ("q", "quit", "cancel"):
            return None
        print("  ⚠️  正しい番号を入力してください")


# =====================================================
# Step4: ツール自動生成
# =====================================================

def _generate_tool(analysis: dict, params: dict) -> str | None:
    """
    リクエストに応じたツールを自動生成する。
    """
    task_type   = analysis["task_type"]
    tool_needed = analysis["tool_needed"]
    operation   = analysis["operation"]

    print(f"\n🔨 ツール生成中: {tool_needed}")

    library_map = {
        "pdf":   "pypdf または reportlab または pdfplumber",
        "excel": "openpyxl または pandas",
        "image": "Pillow",
        "csv":   "pandas",
        "word":  "python-docx",
        "zip":   "zipfile（標準ライブラリ）",
    }
    lib_hint = next(
        (f"推奨ライブラリ: {lib}" for key, lib in library_map.items() if key in task_type),
        ""
    )

    from llm import ask_plain
    prompt = f"""以下のPythonツール関数を実装してください。

ツール名: {tool_needed}
操作: {operation}
パラメータ例: {json.dumps(params, ensure_ascii=False, indent=2)}
{lib_hint}

実装要件:
1. 関数名は {tool_needed} とする
2. 引数は全て文字列型（必要に応じてキャスト）
3. 戻り値は str 型（成功/失敗メッセージ）
4. エラー時は "ERROR: ..." を返す
5. 実際に動作するコードを書く
6. __main__ ブロックでサンプル動作を確認する
7. 全角文字・全角括弧を使わない

出力形式:
TOOL_NAME: {tool_needed}
REQUIRES: pip install xxx（不要ならnone）
CODE:
（完全なPythonコード）
END_CODE
"""
    response = ask_plain(prompt)

    code_m     = (
        re.search(r"CODE:\s*\n(.*?)END_CODE", response, re.DOTALL | re.IGNORECASE)
        or re.search(r"```python\s*\n(.*?)```", response, re.DOTALL)
        or re.search(r"```\s*\n(.*?)```",       response, re.DOTALL)
    )
    requires_m = re.search(r"REQUIRES:\s*(.+)", response, re.IGNORECASE)

    if not code_m:
        print(f"  ❌ コード抽出失敗: {repr(response[:200])}")
        return None

    code     = code_m.group(1).strip()
    requires = requires_m.group(1).strip() if requires_m else "none"

    # 全角文字を半角に変換
    for full, half in [('（', '('), ('）', ')'), ('：', ':'), ('　', ' '),
                       ('｛', '{'), ('｝', '}'), ('，', ','), ('。', '.')]:
        code = code.replace(full, half)

    # REQUIRES 正規化（"pip install xxx" → "xxx"、"none（...）" → "none"）
    requires = re.sub(r"pip\s+install\s+", "", requires, flags=re.IGNORECASE).strip()
    req_first = requires.split()[0] if requires.split() else "none"
    requires  = "none" if req_first.lower().startswith("none") else req_first

    # 構文チェック
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        print(f"  ❌ 構文エラー: {e}")
        return None

    # 依存ライブラリインストール
    if requires.lower() != "none":
        print(f"  📦 インストール: {requires}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", requires],
            capture_output=True,
        )

    # ファイル保存
    EVOLVED_DIR.mkdir(parents=True, exist_ok=True)
    tool_path = EVOLVED_DIR / f"{tool_needed}.py"
    tool_path.write_text(
        f'"""\n自動生成ツール: {tool_needed}\n目的: {operation}\n'
        f'生成日: {datetime.now().strftime("%Y-%m-%d")}\n"""\n\n' + code,
        encoding="utf-8",
    )
    print(f"  ✅ ツール生成完了: {tool_path.name}")

    # skill_db に登録
    try:
        from skill_extractor import save_skill, Skill
        save_skill(Skill(
            name=tool_needed,
            task_example=f"[オンデマンド生成] {operation}",
            summary=f"ユーザーリクエストにより自動生成。分野: {task_type}",
            keywords=[task_type] + tool_needed.split("_"),
            tools_used=["evolved_tool"],
            key_imports=[requires] if requires != "none" else [],
            success_count=1,
            last_used=datetime.now(timezone.utc).isoformat(),
        ))
    except Exception:
        pass

    return str(tool_path)


# =====================================================
# Step5: タスク実行
# =====================================================

def _execute_task(tool_path: str, analysis: dict, params: dict) -> str:
    """生成したツールを使ってタスクを実行する"""
    import importlib.util

    print(f"\n▶ タスク実行中...")

    try:
        spec   = importlib.util.spec_from_file_location("evolved_tool", tool_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        tool_name = analysis["tool_needed"]
        tool_func = getattr(module, tool_name, None)

        if not tool_func:
            return f"ERROR: ツール関数 {tool_name} が見つかりません"

        # 文字列に変換して呼び出す
        str_params = {k: str(v) for k, v in params.items()}
        result = tool_func(**str_params)

        print(f"\n✅ 完了: {result}")
        return result

    except TypeError:
        # 引数が合わない場合は input_file + output_dir で再試行
        try:
            tool_func = getattr(module, analysis["tool_needed"])
            result = tool_func(
                params.get("input_file", ""),
                params.get("output_dir", str(WORKSPACE)),
            )
            return result
        except Exception as e2:
            return f"ERROR: {e2}"
    except Exception as e:
        return f"ERROR: {e}"


# =====================================================
# CLI インターフェース
# =====================================================

def interactive_mode():
    """インタラクティブモードで起動する"""
    print("=" * 50)
    print("  AIアシスタント（オンデマンドツール生成）")
    print("  終了: 'quit' または Ctrl+C")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n何をしますか？ > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "終了"):
                print("終了します。")
                break

            result = handle_user_request(user_input)
            print(f"\n結果: {result}")

        except KeyboardInterrupt:
            print("\n終了します。")
            break
        except Exception as e:
            print(f"エラー: {e}")


if __name__ == "__main__":
    interactive_mode()
