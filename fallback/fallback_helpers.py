"""
fallback/fallback_helpers.py — 共有ヘルパー関数
offline_fallback.py の全てのハンドラーが使う共通ユーティリティ
"""

import re
import os
from typing import Dict, List, Optional


# -------------------------
# TASK PARSING
# -------------------------

def _extract_filename(task: str) -> Optional[str]:
    if not task:
        return None
    paths = _extract_all_paths(task)
    if paths:
        return paths[0]
    candidates = re.findall(r"\b[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+\b", task)
    for name in candidates:
        if name.startswith("."):
            continue
        if name.startswith("._"):
            continue
        return name
    return None


def _extract_all_paths(task: str) -> List[str]:
    if not task:
        return []
    scrubbed = re.sub(r"https?://[^\s'\"）)]+", "", task)
    candidates = re.findall(r"[A-Za-z0-9_./-]+\.py", scrubbed)
    clean: List[str] = []
    for raw in candidates:
        path = raw.replace("\\\\", "/")
        if path.startswith("workspace/"):
            path = path[len("workspace/"):]
        if path.startswith("./"):
            path = path[2:]
        base = os.path.basename(path)
        if base.startswith(".") or base.startswith("._"):
            continue
        if base.startswith("www."):
            continue
        if path not in clean:
            clean.append(path)
    return clean


def _extract_file_candidates(task: str) -> List[str]:
    if not task:
        return []
    scrubbed = re.sub(r"https?://[^\s'\"）)]+", "", task)
    candidates = re.findall(r"[A-Za-z0-9_./-]+\.[A-Za-z0-9]+", scrubbed)
    clean: List[str] = []
    for raw in candidates:
        path = raw.replace("\\\\", "/")
        if path.startswith("workspace/"):
            path = path[len("workspace/"):]
        if path.startswith("./"):
            path = path[2:]
        base = os.path.basename(path)
        if base.startswith(".") or base.startswith("._"):
            continue
        if path not in clean:
            clean.append(path)
    return clean


def _extract_pdf_paths(task: str) -> List[str]:
    if not task:
        return []
    scrubbed = re.sub(r"https?://[^\s'\"）)]+", "", task)
    candidates = re.findall(r"[A-Za-z0-9_./-]+\.pdf", scrubbed)
    clean: List[str] = []
    for raw in candidates:
        path = raw.replace("\\", "/")
        if path.startswith("workspace/"):
            path = path[len("workspace/"):]
        if path.startswith("./"):
            path = path[2:]
        base = os.path.basename(path)
        if base.startswith(".") or base.startswith("._"):
            continue
        if path not in clean:
            clean.append(path)
    return clean


def _extract_urls(task: str) -> List[str]:
    if not task:
        return []
    urls = re.findall(r"https?://[^\s'\"）)]+", task)
    cleaned: List[str] = []
    for u in urls:
        u = u.rstrip(".,;。)")
        if u not in cleaned:
            cleaned.append(u)
    return cleaned


def _extract_output_dir(task: str) -> str:
    if not task:
        return ""
    m = re.findall(r"(?:workspace/)?([A-Za-z0-9_./-]+/)", task)
    if not m:
        return ""
    for cand in m:
        if "http" in cand or "www." in cand:
            continue
        if re.match(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}/", cand):
            continue
        if "output" in cand or "download" in cand:
            return cand
        if "archive" in cand:
            return cand
        if "report" in cand:
            return cand
    for cand in m:
        if "http" in cand or "www." in cand:
            continue
        if re.match(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}/", cand):
            continue
        return cand
    return ""


def _slugify(text: str) -> str:
    if not text:
        return "output"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return slug or "output"


def _infer_basename(url: str, task_lower: str) -> str:
    if url:
        host = re.sub(r"^https?://", "", url)
        host = host.split("/")[0]
        host = host.replace("www.", "")
        host = host.replace(".", "_")
        return _slugify(host)
    if "python" in task_lower and "news" in task_lower:
        return "python_news"
    if "yahoo" in task_lower:
        return "yahoo_news"
    if "google" in task_lower:
        return "google"
    return "result"


def _resolve_output_paths(task: str, url: str) -> Dict[str, str]:
    task_lower = task.lower() if task else ""
    out_dir = _extract_output_dir(task)
    if out_dir.startswith("workspace/"):
        out_dir = out_dir[len("workspace/"):]
    basename = _infer_basename(url, task_lower)
    pdf_paths = _extract_pdf_paths(task)
    if pdf_paths:
        pdf_path = pdf_paths[0]
        dirname = os.path.dirname(pdf_path)
        if dirname:
            out_dir = dirname + "/"
    else:
        if out_dir:
            pdf_path = f"{out_dir}{basename}.pdf"
        else:
            pdf_path = f"{basename}.pdf"
    html_path = pdf_path.rsplit(".", 1)[0] + ".html" if ".pdf" in pdf_path else pdf_path + ".html"
    if out_dir.startswith("workspace/"):
        out_dir = out_dir[len("workspace/"):]
    if out_dir and not out_dir.endswith("/"):
        out_dir = out_dir + "/"
    return {
        "out_dir": out_dir,
        "pdf_path": pdf_path,
        "html_path": html_path,
        "basename": basename,
    }


def _extract_all_quoted(task: str) -> List[str]:
    if not task:
        return []
    items: List[str] = []
    i = 0
    while i < len(task):
        ch = task[i]
        if ch in ("\"", "'", "`"):
            quote = ch
            i += 1
            buf = []
            escape = False
            while i < len(task):
                c = task[i]
                if escape:
                    buf.append(c)
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == quote:
                    items.append("".join(buf))
                    break
                else:
                    buf.append(c)
                i += 1
        i += 1
    return items


def _extract_quoted_text(task: str) -> Optional[str]:
    quoted = _extract_all_quoted(task)
    if quoted:
        return quoted[0]
    return None


def _line_with_newline(text: str) -> str:
    if text.endswith("\n"):
        return text
    return text + "\n"


# -------------------------
# SUCCESS / ERROR DETECTION
# -------------------------

def _looks_like_success(result: str) -> bool:
    if not result:
        return False
    lowered = result.lower()
    if "error" in lowered:
        return False
    if "not allowed" in lowered:
        return False
    if "invalid tool" in lowered:
        return False
    if "tool error" in lowered:
        return False
    return True


# -------------------------
# HISTORY QUERY HELPERS
# -------------------------

def _history_has_tool(history: List[Dict], tool: str, path: Optional[str] = None) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != tool:
            continue
        if path and action.get("path") != path:
            continue
        return True
    return False


def _history_has_move(history: List[Dict], source: str, destination: str) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "move_file":
            continue
        if action.get("source") == source and action.get("destination") == destination:
            return True
    return False


def _history_has_delete(history: List[Dict], path: str) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != "delete_file":
            continue
        if action.get("path") == path:
            return True
    return False


def _last_read_content(history: List[Dict], path: Optional[str]) -> str:
    if not path:
        return ""
    for h in reversed(history):
        action = h.get("action", {})
        if action.get("tool") == "read_file" and action.get("path") == path:
            return str(h.get("result", ""))
    return ""


def _history_success(history: List[Dict], tool: str, path: Optional[str] = None) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("tool") != tool:
            continue
        if path and action.get("path") != path:
            continue
        result = str(h.get("result", ""))
        if _looks_like_success(result):
            return True
    return False


def _history_exit_code_zero(history: List[Dict], tool: str) -> bool:
    for h in reversed(history):
        action = h.get("action", {})
        if action.get("tool") != tool:
            continue
        result = str(h.get("result", ""))
        return "[exit code 0]" in result
    return False


def _last_result_for_tool(history: List[Dict], tool: str, path: Optional[str] = None) -> str:
    for h in reversed(history):
        action = h.get("action", {})
        if action.get("tool") != tool:
            continue
        if path and action.get("path") != path:
            continue
        return str(h.get("result", ""))
    return ""


def _last_index(history: List[Dict], tool: str, path: Optional[str] = None) -> int:
    for i in range(len(history) - 1, -1, -1):
        action = history[i].get("action", {})
        if action.get("tool") != tool:
            continue
        if path and action.get("path") != path:
            continue
        return i
    return -1


def _last_run_command_index(history: List[Dict], needle: str) -> int:
    for i in range(len(history) - 1, -1, -1):
        action = history[i].get("action", {})
        if action.get("tool") != "run":
            continue
        cmd = str(action.get("command", ""))
        if needle in cmd:
            return i
    return -1


def _last_run_result(history: List[Dict], command: str) -> str:
    idx = _last_run_command_index(history, command)
    if idx == -1:
        return ""
    return str(history[idx].get("result", ""))


def _history_has_script_marker(history: List[Dict], path: str, marker: str) -> bool:
    for h in history:
        action = h.get("action", {})
        if action.get("path") != path:
            continue
        if action.get("tool") not in ("create_file", "edit_file"):
            continue
        if not _looks_like_success(str(h.get("result", ""))):
            continue
        content = str(action.get("content", ""))
        if marker in content:
            return True
    return False


def _ls_size_zero(result: str) -> bool:
    if not result:
        return False
    m = re.search(r"\s(\d+)\s+[A-Za-z]{3}\s+\d{1,2}\s+", result)
    if not m:
        return False
    try:
        return int(m.group(1)) == 0
    except Exception:
        return False


def _extract_line_value(result: str, prefix: str) -> str:
    if not result:
        return ""
    for line in result.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _source_value(result: str) -> str:
    return _extract_line_value(result, "SOURCE=")


def _pdf_validation_failed(result: str) -> bool:
    if _extract_line_value(result, "OUTPUT_FORMAT=") != "PDF":
        return False
    if _source_value(result) == "ERROR":
        return False
    matches = _extract_line_value(result, "PDF_TITLE_MATCHES=")
    if not matches:
        return False
    try:
        matches_i = int(matches)
    except Exception:
        return False
    title_count = _extract_line_value(result, "TITLE_COUNT=")
    if title_count:
        try:
            tc = int(title_count)
        except Exception:
            tc = 0
        if tc > 0 and matches_i == 0:
            return True
        if tc > 0 and matches_i < tc:
            return True
    return matches_i == 0


def _preflight_write_failed(result: str) -> bool:
    val = _extract_line_value(result, "PREFLIGHT_WRITE=")
    return bool(val) and val.startswith("FAIL")


# -------------------------
# TASK TYPE DETECTION
# -------------------------

def _needs_time_code(task_lower: str) -> bool:
    if "現在時刻" in task_lower or "current time" in task_lower:
        return True
    if ("時刻" in task_lower or "日時" in task_lower) and ("表示" in task_lower or "出力" in task_lower or "追加" in task_lower):
        return True
    return False


def _extract_function_name(task: str) -> str:
    m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*[^)]*\)", task)
    if m:
        return m.group(1)
    return "add"


def _is_test_task(task_lower: str) -> bool:
    return any(k in task_lower for k in ["テスト", "test", "pytest", "unit test", "ユニット"])


def _is_pdf_task(task_lower: str) -> bool:
    return any(k in task_lower for k in ["pdf", "reportlab"])


def _force_html(task_lower: str) -> bool:
    reasons = ["使えない", "導入できない", "禁止", "不可能", "制約"]
    if "pdf" in task_lower and any(r in task_lower for r in reasons):
        return True
    if "reportlab" in task_lower and any(r in task_lower for r in reasons):
        return True
    return False


def _is_bank_task(task_lower: str) -> bool:
    return any(k in task_lower for k in ["bank", "bankaccount", "bank account", "口座", "銀行"])


# -------------------------
# PIP / PACKAGE HELPERS
# -------------------------

def _needs_pytest_install(history: List[Dict]) -> bool:
    result = _last_result_for_tool(history, "run_test")
    if not result:
        return False
    needs = False
    if "No module named pytest" in result:
        needs = True
    if "ModuleNotFoundError" in result and "pytest" in result:
        needs = True
    if "pytest: command not found" in result:
        needs = True
    if not needs:
        return False
    if _last_run_command_index(history, "pip install pytest") != -1:
        return False
    if _last_run_command_index(history, "python -m pip install pytest") != -1:
        return False
    return True


def _pip_install_attempted(history: List[Dict], package: str) -> bool:
    return (
        _last_run_command_index(history, f"pip install {package}") != -1
        or _last_run_command_index(history, f"python -m pip install {package}") != -1
    )


def _pip_install_succeeded(history: List[Dict], package: str) -> bool:
    idx = _last_run_command_index(history, f"pip install {package}")
    idx2 = _last_run_command_index(history, f"python -m pip install {package}")
    last_idx = max(idx, idx2)
    if last_idx == -1:
        return False
    result = str(history[last_idx].get("result", ""))
    return "[exit code 0]" in result


def _pip_install_failed(history: List[Dict], package: str) -> bool:
    return _pip_install_attempted(history, package) and not _pip_install_succeeded(history, package)


def _reportlab_failed(history: List[Dict]) -> bool:
    return _pip_install_failed(history, "reportlab")


def _requests_failed(history: List[Dict]) -> bool:
    return _pip_install_failed(history, "requests")


def _needs_package_install(history: List[Dict], package: str) -> bool:
    result = _last_result_for_tool(history, "run")
    if not result:
        return False
    needs = False
    if f"No module named {package}" in result:
        needs = True
    if "ModuleNotFoundError" in result and package in result:
        needs = True
    if not needs:
        return False
    if _pip_install_attempted(history, package):
        return False
    return True


def _pip_install_denied(history: List[Dict], package: str) -> bool:
    for h in reversed(history):
        action = h.get("action", {})
        if action.get("tool") != "run":
            continue
        cmd = str(action.get("command", ""))
        if f"pip install {package}" not in cmd and f"python -m pip install {package}" not in cmd:
            continue
        result = str(h.get("result", ""))
        if "not allowed" in result or "Allowed:" in result:
            return True
        return False
    return False
