"""
Toolkit Manager。
同じカテゴリのツールを1つのtoolkitファイルに統合管理する。

構造:
  tools/toolkits/pdf_toolkit.py
    - tool_pdf_split()
    - tool_pdf_merge()
    - tool_pdf_watermark()

新しいPDF機能が来たら pdf_toolkit.py に追記するだけ。
"""
import re
import shutil
from pathlib import Path
from datetime import datetime

AGENT_ROOT   = Path(__file__).parent
EVOLVED_DIR  = AGENT_ROOT / "tools" / "evolved"
TOOLKITS_DIR = AGENT_ROOT / "tools" / "toolkits"


# =====================================================
# カテゴリ定義
# =====================================================

TOOLKIT_CATEGORIES = {
    "pdf":    ["pdf", "pypdf", "reportlab", "pdfplumber"],
    "excel":  ["excel", "xlsx", "openpyxl", "spreadsheet"],
    "image":  ["image", "pillow", "PIL", "draw", "picture"],
    "csv":    ["csv", "tsv", "dataframe"],
    "web":    ["http", "requests", "httpx", "scraping", "fetch"],
    "text":   ["text", "string", "markdown", "docx", "word"],
    "system": ["file", "directory", "path", "zip", "compress"],
    "data":   ["json", "xml", "yaml", "toml", "config"],
    "cli":    ["cli", "terminal", "typer", "argparse", "rich"],
    "ai":     ["transformers", "llm", "model", "inference"],
}


def detect_category(tool_name: str, code: str = "") -> str:
    """ツール名とコードからカテゴリを判定する"""
    combined = (tool_name + " " + code).lower()
    for category, keywords in TOOLKIT_CATEGORIES.items():
        if any(kw in combined for kw in keywords):
            return category
    return "general"


def get_toolkit_path(category: str) -> Path:
    """カテゴリのtoolkitファイルパスを返す"""
    TOOLKITS_DIR.mkdir(parents=True, exist_ok=True)
    return TOOLKITS_DIR / f"{category}_toolkit.py"


# =====================================================
# ツール統合
# =====================================================

def integrate_tool(tool_name: str, code: str, description: str = "") -> str:
    """
    新しいツール関数を適切なtoolkitに統合する。

    Args:
        tool_name:   関数名（例: tool_pdf_split）
        code:        Pythonコード（関数定義から）
        description: 説明

    Returns:
        統合先のtoolkitパス文字列
    """
    category     = detect_category(tool_name, code)
    toolkit_path = get_toolkit_path(category)

    # 既存toolkitに同名関数があるか確認
    if toolkit_path.exists():
        existing = toolkit_path.read_text(encoding="utf-8")
        if f"def {tool_name}(" in existing:
            print(f"  ℹ️  既存関数を更新: {tool_name} in {toolkit_path.name}")
            updated = _replace_function(existing, tool_name, code)
            toolkit_path.write_text(updated, encoding="utf-8")
            return str(toolkit_path)

    # toolkitに追記
    _append_to_toolkit(toolkit_path, tool_name, code, description, category)
    print(f"  ✅ 統合: {tool_name} → {toolkit_path.name}")
    return str(toolkit_path)


def _append_to_toolkit(
    toolkit_path: Path,
    tool_name: str,
    code: str,
    description: str,
    category: str,
):
    """toolkitファイルに関数を追記する"""
    if not toolkit_path.exists():
        header = f'"""\n{category.upper()} Toolkit\n自動生成・統合ツール集。\nカテゴリ: {category}\n作成日: {datetime.now().strftime("%Y-%m-%d")}\n収録ツール:\n- {tool_name}: {description}\n"""\nfrom pathlib import Path\n'
        toolkit_path.write_text(header, encoding="utf-8")
    else:
        # ヘッダーの収録ツールリストを更新
        content = toolkit_path.read_text(encoding="utf-8")
        if "収録ツール:" in content and f"- {tool_name}:" not in content:
            content = content.replace(
                "収録ツール:",
                f"収録ツール:\n- {tool_name}: {description}"
            )
            toolkit_path.write_text(content, encoding="utf-8")

    separator = f"\n\n# {'='*50}\n# {tool_name}\n# {'='*50}\n\n"
    with open(toolkit_path, "a", encoding="utf-8") as f:
        f.write(separator)
        f.write(code)
        f.write("\n")


def _replace_function(content: str, func_name: str, new_code: str) -> str:
    """既存関数をセクション区切りごと新しいコードで置き換える"""
    pattern = (
        r"(# =+\n# " + re.escape(func_name) + r"\n# =+\n\n)"
        r"(.*?)"
        r"(?=\n\n# =|\Z)"
    )
    replacement = (
        f"# {'='*50}\n# {func_name}\n# {'='*50}\n\n{new_code}\n"
    )
    result, n = re.subn(pattern, replacement, content, flags=re.DOTALL)
    if n == 0:
        # セクションが見つからなければ末尾に追記
        result = content + f"\n\n# {'='*50}\n# {func_name}\n# {'='*50}\n\n{new_code}\n"
    return result


# =====================================================
# 既存ツールの統合
# =====================================================

def consolidate_existing_tools() -> dict:
    """
    tools/evolved/ の既存ツールを全てtoolkitに統合する。
    統合後は元ファイルをarchived/に移動する。
    """
    EVOLVED_DIR.mkdir(parents=True, exist_ok=True)
    archive_dir = EVOLVED_DIR / "archived"
    archive_dir.mkdir(exist_ok=True)

    results = {"integrated": [], "skipped": [], "archived": []}

    for tool_file in sorted(EVOLVED_DIR.glob("*.py")):
        if tool_file.stem.startswith("_") or tool_file.stem.startswith("."):
            continue

        code = tool_file.read_text(encoding="utf-8")

        # 関数名を抽出
        func_match = re.search(r"def (tool_\w+)\(", code)
        if not func_match:
            results["skipped"].append(tool_file.name)
            continue

        tool_name = func_match.group(1)

        # 説明を抽出（ファイルヘッダーの「目的:」行）
        desc_match = re.search(r"目的:\s*(.+)", code)
        description = desc_match.group(1).strip() if desc_match else ""

        # 関数コードのみ抽出（def 以降）
        func_start = code.find(f"def {tool_name}(")
        if func_start == -1:
            results["skipped"].append(tool_file.name)
            continue
        func_code = code[func_start:].strip()

        # toolkit に統合
        integrate_tool(tool_name, func_code, description)
        results["integrated"].append(tool_name)

        # 元ファイルをアーカイブ
        shutil.move(str(tool_file), str(archive_dir / tool_file.name))
        results["archived"].append(tool_file.name)

    return results


# =====================================================
# 検索・一覧
# =====================================================

def list_toolkit_functions() -> dict:
    """全toolkitの収録関数一覧を返す"""
    result = {}
    if not TOOLKITS_DIR.exists():
        return result
    for toolkit in sorted(TOOLKITS_DIR.glob("*_toolkit.py")):
        if toolkit.name.startswith("."):
            continue
        try:
            content = toolkit.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        funcs = re.findall(r"def (tool_\w+)\(", content)
        if funcs:
            result[toolkit.stem] = funcs
    return result


def find_tool_in_toolkits(tool_name: str) -> tuple:
    """
    toolkitから指定の関数を探す。

    Returns:
        (toolkit_path_str, toolkit_content) または (None, None)
    """
    if not TOOLKITS_DIR.exists():
        return None, None
    for toolkit in TOOLKITS_DIR.glob("*_toolkit.py"):
        if toolkit.name.startswith("."):
            continue
        try:
            content = toolkit.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if f"def {tool_name}(" in content:
            return str(toolkit), content
    return None, None
