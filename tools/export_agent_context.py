import os
import re
import ast
import datetime


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_FILE = os.path.join(ROOT, "agent_context_for_claude.md")

EXCLUDE_DIRS = {"venv", "__pycache__", ".git", ".claude", "workspace"}
EXCLUDE_NAME_PREFIXES = ("._",)

LOCAL_MODULES = None  # populated lazily


def _should_skip_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS


def _should_skip_file(name: str) -> bool:
    for pfx in EXCLUDE_NAME_PREFIXES:
        if name.startswith(pfx):
            return True
    return False


# -------------------------
# DIRECTORY TREE
# -------------------------

def _list_dir(path: str):
    entries = []
    try:
        for name in os.listdir(path):
            if name in EXCLUDE_DIRS or _should_skip_file(name):
                continue
            entries.append(name)
    except Exception:
        return []
    return sorted(entries)


def _build_tree(path: str, prefix: str = "") -> str:
    lines = []
    entries = _list_dir(path)
    for i, name in enumerate(entries):
        full = os.path.join(path, name)
        is_last = i == len(entries) - 1
        branch = "└── " if is_last else "├── "
        lines.append(prefix + branch + name)
        if os.path.isdir(full) and not _should_skip_dir(name):
            extension = "    " if is_last else "│   "
            lines.extend(_build_tree(full, prefix + extension).splitlines())
    return "\n".join([l for l in lines if l])


# -------------------------
# COLLECT ALL PROJECT .PY FILES
# -------------------------

def _collect_all_py_files():
    """Return all .py files in the project (excluding venv, __pycache__, workspace)."""
    result = []
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = sorted([d for d in dirs if d not in EXCLUDE_DIRS])
        for name in sorted(files):
            if _should_skip_file(name):
                continue
            if not name.endswith(".py"):
                continue
            result.append(os.path.join(root, name))
    return result


def _build_local_module_set(all_py_files):
    """Build set of local module names (without .py) for import graph."""
    names = set()
    for path in all_py_files:
        rel = os.path.relpath(path, ROOT)
        base = os.path.basename(path)[:-3]  # strip .py
        names.add(base)
        # also add dotted path (e.g. tools.ast_editor)
        dot_path = rel[:-3].replace(os.sep, ".")
        names.add(dot_path)
    return names


# -------------------------
# MODEL EXTRACTION
# -------------------------

def _extract_models():
    """Extract model name constants from llm.py."""
    llm_path = os.path.join(ROOT, "llm.py")
    models = {}
    try:
        with open(llm_path, "r", encoding="utf-8") as f:
            content = f.read()
        for const in ("PLANNER_MODEL", "CODER_MODEL", "MODEL", "MODEL_CODER",
                      "MODEL_PLANNER", "OLLAMA_URL"):
            m = re.search(rf'^{const}\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if m:
                models[const] = m.group(1)
    except Exception:
        pass
    return models


def _has_system_prompt():
    llm_path = os.path.join(ROOT, "llm.py")
    try:
        with open(llm_path, "r", encoding="utf-8") as f:
            return "SYSTEM_PROMPT" in f.read()
    except Exception:
        return False


# -------------------------
# FILE FUNCTIONS
# -------------------------

def _find_functions(text: str):
    return re.findall(r"^def\s+(\w+)\(", text, flags=re.MULTILINE)


def _count_lines(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _purpose_for(rel: str, base: str) -> str:
    known = {
        "main.py": "Main agent loop — task intake, step loop, loop detection, history",
        "executor.py": "Tool routing and execution — maps tool names to handler functions",
        "llm.py": "LLM client — Ollama API calls, SYSTEM_PROMPT, model routing",
        "planner.py": "Original planner (may be superseded by planner_light)",
        "planner_light.py": "Lightweight planner — breaks task into bullet steps",
        "debug_loop.py": "Auto-debug loop — detects errors and suggests fixes",
        "project_map.py": "Workspace scanner — safe_path(), scan_project(), AST symbols",
        "memory.py": "Session persistence — load/save agent_memory.json",
        "parser.py": "JSON extraction — handles markdown blocks, malformed JSON, fallback",
        "offline_fallback.py": "Fallback actions when Ollama is down or parse fails",
        "reflection.py": "Post-step reflection — auto-install missing modules, etc.",
        "tool_learning.py": "Tool pattern storage for reinforcement",
        "tool_registry.py": "Tool registration registry",
        "vector_store.py": "Root-level vector store (may duplicate tools/vector_store.py)",
        "agent.py": "DEAD CODE — legacy agent loop with critical indentation bug",
        "code_indexer.py": "Code index builder",
        "code_search.py": "Code semantic search",
        "llm_router.py": "LLM routing (plan/code split)",
        "error_fix_agent.py": "Error fix automation agent",
        "test_generator.py": "Test stub/file generator",
    }
    if base in known:
        return known[base]
    if rel.startswith("tools" + os.sep):
        return "Tool module"
    if rel.startswith("cognition" + os.sep):
        return "Cognition module"
    if rel.startswith("memory" + os.sep):
        return "Memory data file"
    return "Module"


def _summarize_file(path: str):
    rel = os.path.relpath(path, ROOT)
    base = os.path.basename(path)
    content = _read_file(path)
    line_count = _count_lines(path)
    purpose = _purpose_for(rel, base)
    functions = _find_functions(content)
    return rel, purpose, functions, line_count


def _collect_main_files():
    """Priority files listed first, then tools/, then cognition/."""
    important = [
        "main.py", "executor.py", "llm.py", "planner_light.py", "planner.py",
        "debug_loop.py", "project_map.py", "memory.py", "parser.py",
        "offline_fallback.py", "reflection.py", "tool_learning.py",
        "tool_registry.py", "llm_router.py", "agent.py",
        "code_indexer.py", "code_search.py", "vector_store.py",
        "error_fix_agent.py", "test_generator.py",
    ]
    files = []
    for name in important:
        path = os.path.join(ROOT, name)
        if os.path.exists(path):
            files.append(path)

    for subdir in ("tools", "cognition"):
        d = os.path.join(ROOT, subdir)
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if _should_skip_file(name) or not name.endswith(".py"):
                    continue
                files.append(os.path.join(d, name))
    return files


# -------------------------
# IMPORT DEPENDENCY GRAPH
# -------------------------

def _extract_local_imports(content: str, local_modules: set) -> list:
    """Extract local module imports from a file's source."""
    imports = set()

    # import xxx
    for m in re.finditer(r"^import\s+([\w.]+)", content, re.MULTILINE):
        mod = m.group(1)
        base = mod.split(".")[0]
        if base in local_modules or mod in local_modules:
            imports.add(base)

    # from xxx import yyy
    for m in re.finditer(r"^from\s+([\w.]+)\s+import", content, re.MULTILINE):
        mod = m.group(1)
        base = mod.split(".")[0]
        if base in local_modules or mod in local_modules:
            imports.add(base if not mod.startswith("tools") else mod.replace(".", os.sep))

    return sorted(imports)


def _build_dependency_graph(all_py_files: list) -> str:
    local_modules = _build_local_module_set(all_py_files)
    lines = []

    # Only show root-level and first-level files (not venv)
    target_files = [f for f in all_py_files
                    if not f.endswith("export_agent_context.py")]

    for path in target_files:
        rel = os.path.relpath(path, ROOT)
        content = _read_file(path)
        deps = _extract_local_imports(content, local_modules)
        if deps:
            lines.append(f"{rel}")
            lines.append("  └─→ " + ", ".join(deps))
    return "\n".join(lines) if lines else "(no local imports detected)"


# -------------------------
# TODO / FIXME / HACK SCAN
# -------------------------

def _scan_todos(all_py_files: list) -> list:
    """Scan all project .py files for TODO, FIXME, HACK comments."""
    results = []
    for path in all_py_files:
        rel = os.path.relpath(path, ROOT)
        content = _read_file(path)
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            for marker in ("# TODO", "# FIXME", "# HACK"):
                if stripped.startswith(marker) or f" {marker}" in stripped:
                    results.append(f"- {rel}:{i} `{stripped}`")
    return results


# -------------------------
# REPORT BUILDER
# -------------------------

def build_report():
    all_py_files = _collect_all_py_files()
    models = _extract_models()
    has_system_prompt = _has_system_prompt()

    planner_model = models.get("PLANNER_MODEL", "unknown")
    coder_model = models.get("CODER_MODEL", models.get("MODEL", "unknown"))
    ollama_url = models.get("OLLAMA_URL", "http://localhost:11434/api/generate")

    tree = _build_tree(ROOT)
    summaries = [_summarize_file(p) for p in _collect_main_files()]

    todos = _scan_todos(all_py_files)
    dep_graph = _build_dependency_graph(all_py_files)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []

    # ---- Section 1: PROJECT OVERVIEW ----
    lines.append("# Agent Context Report")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## 1. PROJECT OVERVIEW")
    lines.append("")
    lines.append("This project is an autonomous coding agent that:")
    lines.append("- Plans tasks using a dedicated planner LLM")
    lines.append("- Writes code via a coder LLM")
    lines.append("- Executes tools (file I/O, shell, web, AST editing)")
    lines.append("- Debugs errors automatically")
    lines.append("- Persists session memory across runs")
    lines.append("- Uses Tree-of-Thoughts for candidate action selection")
    lines.append("")
    lines.append(f"All LLM calls go to Ollama at: `{ollama_url}`")
    lines.append(f"SYSTEM_PROMPT defined: {'Yes' if has_system_prompt else 'No'}")
    lines.append("")
    lines.append("**Models used** (from llm.py):")
    lines.append(f"- Planner model (`PLANNER_MODEL`): `{planner_model}`")
    lines.append(f"- Coder model (`CODER_MODEL`): `{coder_model}`")
    if "MODEL_CODER" in models:
        lines.append(f"- MODEL_CODER: `{models['MODEL_CODER']}`")
    if "MODEL_PLANNER" in models:
        lines.append(f"- MODEL_PLANNER: `{models['MODEL_PLANNER']}`")
    lines.append("")

    # ---- Section 2: DIRECTORY STRUCTURE ----
    lines.append("## 2. PROJECT DIRECTORY STRUCTURE")
    lines.append("")
    lines.append("```")
    lines.append(os.path.basename(ROOT) + "/")
    lines.append(tree)
    lines.append("```")
    lines.append("")

    # ---- Section 3: FILE SUMMARIES ----
    lines.append("## 3. FILE SUMMARIES")
    lines.append("")
    for rel, purpose, functions, line_count in summaries:
        lines.append(f"### {rel} ({line_count} lines)")
        lines.append(f"**Purpose:** {purpose}")
        lines.append("")
        lines.append("**Key functions:**")
        if functions:
            for fn in functions:
                lines.append(f"- `{fn}()`")
        else:
            lines.append("- (none detected)")
        lines.append("")

    # ---- Section 4: AGENT ARCHITECTURE ----
    lines.append("## 4. AGENT ARCHITECTURE")
    lines.append("")
    lines.append("```")
    lines.append("User task (stdin)")
    lines.append("   ↓")
    lines.append(f"planner_light.py → {planner_model}")
    lines.append("   ↓ (bullet plan)")
    lines.append("main.py agent loop")
    lines.append("   ↓ (each step)")
    lines.append("cognition/tree_of_thoughts.py")
    lines.append("   ↓ (3 candidates → select best)")
    lines.append(f"llm.py ask_coder() → {coder_model}")
    lines.append("   ↓ (JSON action)")
    lines.append("parser.py extract_json()")
    lines.append("   ↓")
    lines.append("executor.py execute_tool()")
    lines.append("   ├── tools/filesystem.py")
    lines.append("   ├── tools/ast_editor*.py")
    lines.append("   ├── run_command() → subprocess")
    lines.append("   ├── tools/web_tools.py")
    lines.append("   └── ... (25+ tools)")
    lines.append("   ↓ (result)")
    lines.append("debug_loop.py should_debug() / analyze_error()")
    lines.append("   ↓")
    lines.append("reflection.py reflect()")
    lines.append("   ↓")
    lines.append("loop detection → next step or done")
    lines.append("```")
    lines.append("")

    # ---- Section 5: CURRENT FEATURES ----
    lines.append("## 5. CURRENT FEATURES")
    lines.append("")
    tool_funcs = []
    tools_dir = os.path.join(ROOT, "tools")
    if os.path.isdir(tools_dir):
        for name in sorted(os.listdir(tools_dir)):
            if _should_skip_file(name) or not name.endswith(".py"):
                continue
            content = _read_file(os.path.join(tools_dir, name))
            fns = _find_functions(content)
            for fn in fns:
                if not fn.startswith("_"):
                    tool_funcs.append(f"`{name}` → `{fn}()`")
    features = [
        "Multi-step autonomous loop with step counter (MAX_STEPS=30)",
        "Planner + Coder LLM split (separate models)",
        "Tree-of-Thoughts candidate generation (k=3) + best selection",
        "JSON parsing with fallback, newline fix, and field-level extraction",
        "Context-aware code editing (read before edit)",
        "Loop detection (3 consecutive identical real actions)",
        "Auto-debug loop (analyze_error → pending_action injection)",
        "Post-step reflection (auto pip install, test detection, PDF verification)",
        "Session memory persistence (agent_memory.json)",
        "Workspace sandboxing via safe_path()",
        "Allowed command whitelist (ALLOWED_COMMANDS)",
        "pip package whitelist (pip_whitelist.json)",
        "AST-safe function editing (ast_editor, ast_editor_safe)",
        "Diff-patch editing (diff_edit, apply_patch)",
        "Web search + page fetch + text extraction",
        "Knowledge base + research workflow",
        "Task queue + subgoal discovery",
        "Error recording + self-improvement agent",
        "Code indexer + semantic code search",
        "Offline fallback when Ollama is unreachable",
    ]
    for f in features:
        lines.append(f"- {f}")
    lines.append("")
    lines.append("### Tool functions (from tools/):")
    for tf in tool_funcs[:40]:
        lines.append(f"- {tf}")
    if len(tool_funcs) > 40:
        lines.append(f"- ... ({len(tool_funcs) - 40} more)")
    lines.append("")

    # ---- Section 6: TODO / FIXME / HACK ----
    lines.append("## 6. CURRENT PROBLEMS / TODO")
    lines.append("")
    if todos:
        lines.append("### Inline TODO/FIXME/HACK comments found:")
        lines.extend(todos)
    else:
        lines.append("No `# TODO`, `# FIXME`, or `# HACK` comments found in project source.")
    lines.append("")
    lines.append("### Known architectural issues (from session notes):")
    lines.append("- `agent.py` is dead code — critical indentation bug, never called by main.py")
    lines.append("- `tools/terminal.py` uses `shell=True` — never called but exists")
    lines.append("- Loop detection only catches exact repeats, not semantic loops")
    lines.append("- qwen2.5-coder model tends to ignore `done` after task completion")
    lines.append("- Planner sometimes outputs `workspace/` prefixes in plan text")
    lines.append("- `vector_store.py` exists at both root and `tools/` (duplication)")
    lines.append("- `code_indexer.py` and `code_search.py` duplicated at both root and `tools/`")
    lines.append("")

    # ---- Section 7: IMPORT DEPENDENCY GRAPH ----
    lines.append("## 7. IMPORT DEPENDENCY GRAPH")
    lines.append("")
    lines.append("Local module dependencies (→ = imports):")
    lines.append("")
    lines.append("```")
    lines.append(dep_graph)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    report = build_report()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    size = os.path.getsize(OUTPUT_FILE)
    print(f"Wrote {OUTPUT_FILE} ({size} bytes)")


if __name__ == "__main__":
    main()
