"""
fallback/fallback_shell.py — シェル・コマンド実行系フォールバックハンドラー
web2pdf スクリプト生成・実行・検証を処理する (PDF/HTML 出力を含む)
"""

from typing import Dict, List

from fallback.fallback_helpers import (
    _extract_all_paths,
    _extract_urls,
    _extract_line_value,
    _force_html,
    _history_has_script_marker,
    _history_has_tool,
    _history_success,
    _last_result_for_tool,
    _last_run_command_index,
    _last_run_result,
    _ls_size_zero,
    _needs_package_install,
    _pdf_validation_failed,
    _pip_install_attempted,
    _pip_install_denied,
    _preflight_write_failed,
    _reportlab_failed,
    _requests_failed,
    _resolve_output_paths,
    _source_value,
)


def handle_pdf(task: str, history: List[Dict]) -> Dict:
    task_lower = task.lower()

    paths = _extract_all_paths(task)
    urls = _extract_urls(task)

    script_path = paths[0] if paths else "web2pdf.py"
    url = urls[0] if urls else "https://example.com"
    out_paths = _resolve_output_paths(task, url)
    pdf_path = out_paths["pdf_path"]
    html_path = out_paths["html_path"]
    out_dir = out_paths["out_dir"]
    force_html = _force_html(task_lower)

    wants_title = "title" in task_lower or "タイトル" in task_lower
    wants_create = any(
        k in task_lower
        for k in ["作成", "create", "write", "make", "新規", "追加"]
    )

    if "workspace/" in script_path:
        script_path = script_path.replace("workspace/", "", 1)

    run_cmd = f"python {script_path}"
    last_run_idx = _last_run_command_index(history, run_cmd)
    last_run_result_str = _last_run_result(history, run_cmd)

    validation_failed = _pdf_validation_failed(last_run_result_str)
    if validation_failed:
        force_html = True

    use_requests = not _requests_failed(history)
    use_reportlab = not (_reportlab_failed(history) or _pip_install_denied(history, "reportlab") or force_html)

    if _source_value(last_run_result_str) == "ERROR" and "FETCH_LIB=REQUESTS" in last_run_result_str:
        use_requests = False

    mode_marker = "MODE_HTML" if not use_reportlab else "MODE_PDF"
    fetch_marker = "FETCH_URLLIB" if not use_requests else "FETCH_REQUESTS"

    code_lines = [
        f"# {mode_marker}",
        f"# {fetch_marker}",
        "# TITLE_LIST",
        "# CACHE_SUPPORT",
        "import os",
        "import re",
        "import socket",
        "import urllib.parse",
    ]

    if use_requests:
        code_lines.append("import requests")
    else:
        code_lines.append("import urllib.request")

    if use_reportlab:
        code_lines.append("from reportlab.pdfgen import canvas")
        out_path = pdf_path
        out_mode = "PDF"
    else:
        out_path = html_path
        out_mode = "HTML"

    code_lines += [
        "",
        f"URL = \"{url}\"",
        f"OUT_PATH = \"{out_path}\"",
        f"CACHE_DIR = \"cache\"",
        f"CACHE_PATH = os.path.join(CACHE_DIR, \"{out_paths['basename']}.html\")",
        "",
        "def extract_title(html: str) -> str:",
        "    m = re.search(r\"<title>(.*?)</title>\", html, re.IGNORECASE | re.DOTALL)",
        "    if m:",
        "        return re.sub(r\"\\s+\", \" \", m.group(1)).strip()",
        "    return html.strip()[:120]",
        "",
        "def extract_titles(html: str) -> list:",
        "    titles = []",
        "    patterns = [",
        "        r\"<h1[^>]*>(.*?)</h1>\",",
        "        r\"<h2[^>]*>(.*?)</h2>\",",
        "        r\"<h3[^>]*>(.*?)</h3>\",",
        "    ]",
        "    for p in patterns:",
        "        for m in re.findall(p, html, re.IGNORECASE | re.DOTALL):",
        "            t = re.sub(r\"<.*?>\", \"\", m)",
        "            t = re.sub(r\"\\s+\", \" \", t).strip()",
        "            if t and t not in titles and len(t) < 120:",
        "                titles.append(t)",
        "    if not titles:",
        "        titles = [extract_title(html)]",
        "    return titles[:10]",
        "",
        "def preflight():",
        "    net_status = \"SKIPPED\"",
        "    try:",
        "        host = urllib.parse.urlparse(URL).hostname or \"\"",
        "        if host:",
        "            socket.gethostbyname(host)",
        "            net_status = \"OK\"",
        "        else:",
        "            net_status = \"NOHOST\"",
        "    except Exception as e:",
        "        net_status = f\"FAIL:{e}\"",
        "    write_status = \"OK\"",
        "    try:",
        "        out_dir = os.path.dirname(OUT_PATH) or \".\"",
        "        os.makedirs(out_dir, exist_ok=True)",
        "        test_path = os.path.join(out_dir, \".write_test\")",
        "        with open(test_path, \"w\", encoding=\"utf-8\") as f:",
        "            f.write(\"ok\")",
        "        os.remove(test_path)",
        "    except Exception as e:",
        "        write_status = f\"FAIL:{e}\"",
        "    print(f\"PREFLIGHT_NET={net_status}\")",
        "    print(f\"PREFLIGHT_WRITE={write_status}\")",
        "",
        "def fetch_text() -> tuple:",
        "    source = \"NETWORK\"",
        "    error = \"\"",
        "    try:",
    ]

    if use_requests:
        code_lines += [
            "        resp = requests.get(URL, timeout=10)",
            "        resp.raise_for_status()",
            "        html = resp.text.strip()",
            "        if html:",
            "            os.makedirs(CACHE_DIR, exist_ok=True)",
            "            with open(CACHE_PATH, \"w\", encoding=\"utf-8\") as f:",
            "                f.write(html)",
            "        return html, source, error",
        ]
    else:
        code_lines += [
            "        with urllib.request.urlopen(URL, timeout=10) as r:",
            "            html = r.read().decode('utf-8', errors='replace')",
            "        if html:",
            "            os.makedirs(CACHE_DIR, exist_ok=True)",
            "            with open(CACHE_PATH, \"w\", encoding=\"utf-8\") as f:",
            "                f.write(html)",
            "        return html, source, error",
        ]

    code_lines += [
        "    except Exception as e:",
        "        error = str(e)",
        "        if os.path.exists(CACHE_PATH):",
        "            try:",
        "                with open(CACHE_PATH, \"r\", encoding=\"utf-8\") as f:",
        "                    html = f.read()",
        "                source = \"CACHE\"",
        "                return html, source, error",
        "            except Exception as e2:",
        "                error = f\"{error}; cache read failed: {e2}\"",
        "        source = \"ERROR\"",
        "        return \"\", source, error",
        "",
        "def main():",
        "    preflight()",
        "    html, source, error = fetch_text()",
        "    if error:",
        "        print(f\"ERROR_MSG={error}\")",
        "    if html:",
        "        titles = extract_titles(html)",
        "    else:",
        "        titles = []",
        "    for t in titles:",
        "        print(f\"TITLE:{t}\")",
        "    print(f\"TITLE_COUNT={len(titles)}\")",
        "    text = \"\\n\".join(titles)",
        "    if not text and error:",
        "        text = error",
    ]

    if wants_title:
        code_lines.append("    text = extract_title(text)")

    if use_reportlab:
        code_lines += [
            "    c = canvas.Canvas(OUT_PATH)",
            "    text_obj = c.beginText(72, 720)",
            "    if text:",
            "        for line in text.splitlines():",
            "            text_obj.textLine(line)",
            "    else:",
            "        text_obj.textLine(\"(no data)\")",
            "    c.drawText(text_obj)",
            "    c.save()",
            "    matches = 0",
            "    try:",
            "        with open(OUT_PATH, \"rb\") as f:",
            "            data = f.read()",
            "        for t in titles:",
            "            if t and t.encode(\"utf-8\") in data:",
            "                matches += 1",
            "    except Exception as e:",
            "        print(f\"PDF_VALIDATE_ERROR={e}\")",
            "    print(f\"PDF_TITLE_MATCHES={matches}\")",
        ]
    else:
        code_lines += [
            "    html = \"<html><body><h1>Result</h1><pre>\" + text + \"</pre></body></html>\"",
            "    with open(OUT_PATH, \"w\", encoding=\"utf-8\") as f:",
            "        f.write(html)",
        ]

    code_lines += [
        f"    print(\"OUTPUT_FORMAT={out_mode}\")",
        f"    print(\"FETCH_LIB={'REQUESTS' if use_requests else 'URLLIB'}\")",
        "    print(f\"SOURCE={source}\")",
        "",
        "if __name__ == \"__main__\":",
        "    main()",
        "",
    ]

    code_content = "\n".join(code_lines)

    code_ready = (
        _history_success(history, "create_file", script_path)
        or _history_success(history, "edit_file", script_path)
    )

    marker_ok = (
        _history_has_script_marker(history, script_path, mode_marker)
        and _history_has_script_marker(history, script_path, fetch_marker)
        and _history_has_script_marker(history, script_path, "TITLE_LIST")
        and _history_has_script_marker(history, script_path, "CACHE_SUPPORT")
    )
    marker_seen = marker_ok

    if out_dir and not _history_has_tool(history, "make_dir", out_dir.rstrip("/")):
        return {
            "thought": "出力先ディレクトリを作成する",
            "tool": "make_dir",
            "path": out_dir.rstrip("/")
        }

    if (wants_create or not code_ready or not marker_ok) and not marker_seen:
        if not use_reportlab:
            if validation_failed:
                reason = "PDF 内容検証が不十分なため HTML 出力へ切り替える"
            elif force_html:
                reason = "PDF 出力が制約されているため HTML 出力へ切り替える"
            else:
                reason = "reportlab が導入できないため HTML 出力へ切り替える"
        else:
            reason = "スクリプトを作成する"
        last_create = _last_result_for_tool(history, "create_file", script_path).lower()
        if "already exists" in last_create or "exists" in last_create:
            return {
                "thought": reason,
                "tool": "edit_file",
                "path": script_path,
                "content": code_content
            }
        if not _history_has_tool(history, "create_file", script_path):
            return {
                "thought": reason,
                "tool": "create_file",
                "path": script_path,
                "content": code_content
            }

    if not wants_create and not code_ready:
        return {
            "thought": "スクリプトを作成する",
            "tool": "create_file",
            "path": script_path,
            "content": code_content
        }

    if _needs_package_install(history, "requests"):
        return {
            "thought": "requests が不足しているためインストールする",
            "tool": "run",
            "command": "pip install requests"
        }

    if force_html and not _pip_install_attempted(history, "reportlab"):
        return {
            "thought": "reportlab の導入可否を確認する",
            "tool": "run",
            "command": "pip install reportlab"
        }

    if _needs_package_install(history, "reportlab"):
        return {
            "thought": "reportlab が不足しているためインストールする",
            "tool": "run",
            "command": "pip install reportlab"
        }

    req_idx = _last_run_command_index(history, "pip install requests")
    req_idx2 = _last_run_command_index(history, "python -m pip install requests")
    last_req_idx = max(req_idx, req_idx2)
    req_succeeded = last_req_idx != -1 and "[exit code 0]" in str(history[last_req_idx].get("result", ""))

    rep_idx = _last_run_command_index(history, "pip install reportlab")
    rep_idx2 = _last_run_command_index(history, "python -m pip install reportlab")
    last_rep_idx = max(rep_idx, rep_idx2)
    rep_succeeded = last_rep_idx != -1 and "[exit code 0]" in str(history[last_rep_idx].get("result", ""))

    if last_run_idx == -1 or (req_succeeded and last_req_idx > last_run_idx) or (rep_succeeded and last_rep_idx > last_run_idx):
        return {
            "thought": "スクリプトを実行する",
            "tool": "run",
            "command": run_cmd
        }

    if _source_value(last_run_result_str) == "ERROR" and "FETCH_LIB=REQUESTS" in last_run_result_str:
        if _history_has_script_marker(history, script_path, "FETCH_URLLIB"):
            return {
                "thought": "urllib で再実行する",
                "tool": "run",
                "command": run_cmd
            }

    if "[exit code 0]" in last_run_result_str:
        primary = pdf_path if use_reportlab else html_path
        fallback = html_path if use_reportlab else pdf_path
        ls_cmd = f"ls -l {primary}"
        if _last_run_command_index(history, ls_cmd) == -1:
            return {
                "thought": "生成された出力を確認する",
                "tool": "run",
                "command": ls_cmd
            }
        ls_result = _last_run_result(history, ls_cmd)
        if _ls_size_zero(ls_result):
            return {
                "thought": "出力サイズが0のため終了する",
                "tool": "done"
            }
        if "No such file" in ls_result or "not found" in ls_result:
            ls_cmd2 = f"ls -l {fallback}"
            if _last_run_command_index(history, ls_cmd2) == -1:
                return {
                    "thought": "代替出力を確認する",
                    "tool": "run",
                    "command": ls_cmd2
                }
            ls_result2 = _last_run_result(history, ls_cmd2)
            if _ls_size_zero(ls_result2):
                return {
                    "thought": "代替出力サイズが0のため終了する",
                    "tool": "done"
                }
            if "No such file" in ls_result2 or "not found" in ls_result2:
                return {
                    "thought": "出力が見つからないため終了する",
                    "tool": "done"
                }
        if _preflight_write_failed(last_run_result_str):
            return {
                "thought": "書き込み権限の事前チェックに失敗したため終了する",
                "tool": "done"
            }
        if _source_value(last_run_result_str) == "ERROR":
            err = _extract_line_value(last_run_result_str, "ERROR_MSG=")
            msg = "ネットワーク取得に失敗したため終了する。オフライン入力やキャッシュ提供を検討してほしい"
            if err:
                msg = f"ネットワーク取得に失敗したため終了する: {err}。オフライン入力やキャッシュ提供を検討してほしい"
            return {
                "thought": msg,
                "tool": "done"
            }
        if _source_value(last_run_result_str) == "ERROR" and "FETCH_LIB=URLLIB" in last_run_result_str:
            return {
                "thought": "ネットワーク取得に失敗したため終了する",
                "tool": "done"
            }
        if "TITLE_COUNT=0" in last_run_result_str or "TITLE:" not in last_run_result_str:
            return {
                "thought": "タイトル抽出が不十分なため終了する",
                "tool": "done"
            }
        return {
            "thought": "出力の生成が確認できたため終了する",
            "tool": "done"
        }

    return {
        "thought": "スクリプト実行に失敗したため終了する",
        "tool": "done"
    }
