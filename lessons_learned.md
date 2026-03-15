# Lessons Learned

Last updated: 2026-03-10

- Ollama connectivity can be unavailable; the agent now needs an offline fallback for planning and tool selection.
- `create_file` should not overwrite existing files; using a dedicated create path avoids accidental loss.
- Quoted content extraction needs to handle escaped quotes to avoid truncation on append tasks.
- Stage 2 requires multi-step offline sequencing; a simple "success → done" shortcut breaks edit flows.
- Use history to detect successful `diff_edit` steps; relying on stale read content can trigger loops.
- Provide a minimal `diff_edit` implementation even in fallback paths to keep editing tools usable offline.
- Tool registry reduces executor branching and makes adding Stage 3 tools safer.
- Tests should be run via a dedicated `run_test` action so exit codes are easy to track.
- Regex patterns for paths should avoid over-escaping; a single `\.py` is sufficient in raw strings.
- `python -m pytest` is more reliable than a bare `pytest` executable in venvs.
- Missing pytest should trigger an automatic, whitelisted `pip install pytest` attempt before re-running tests.
- Reflection in the main loop helps recover from environment errors without LLM access.
- pip install may fail in restricted environments; capture and surface the failure rather than looping.
- When a common AssertionError indicates a simple arithmetic bug, a targeted `diff_edit` can unblock tests quickly.
- Distinguish environment errors (missing pytest) from logic errors (AssertionError) to choose repair actions.
- Planning templates should front-load tests when the task explicitly requests them (TDD-style).
- Simple domain templates (e.g., BankAccount) make multi-file tasks reliable offline.
- External-library tasks need two phases: dependency install then run; verify output artifacts explicitly.
- For networked tasks, fallback content allows artifact generation even when HTTP is blocked.
- Whitelist expansion should remain minimal and task-driven (requests/reportlab for PDF tasks).
- When reportlab install fails, generate HTML output as a graceful fallback and verify with `ls`.
- For external fetch tasks, print the output format and fetch library to simplify reporting.
- Detect library failures separately from network errors to choose between install and fallback.
- Derive output filenames from URL context to avoid generic names when not specified.
- External tasks without explicit filenames need a default script name in the plan to avoid ambiguity.
- A single denied install attempt is enough to trigger HTML fallback without retrying.
- Strip URLs before extracting `.py` paths to avoid false positives like `www.py`.
- Add simple content validation (title count) before declaring completion for scraped reports.
- If requests fails due to network, retry once with urllib; if both fail, stop with a clear network-failure reason.
- Add preflight checks (network DNS + write permission) and cache fallback to keep reports reproducible in restricted environments.
- Validate PDF content by checking for title strings in the generated binary; if validation fails, switch output format.

## Error-Handling Best Practices (Summary)
- Classify failures early: environment (missing/denied libs), network (HTTP/timeout), or logic (assertions), and choose the minimal corrective action.
- Enforce single-attempt installs for restricted dependencies; if denied or failed, switch to a standard-library or alternate-format path.
- Prefer deterministic recovery: read files after failures, apply targeted diffs, and re-run verification once.
- Verify outputs explicitly (e.g., `ls -l`) and fall back to alternate artifacts when primary outputs are missing.
- Keep plans aligned with task intent: TDD when tests are requested; external tasks should include dependency checks and artifact validation.

## Error Classification With Examples
- Environment: `ModuleNotFoundError: pytest` → try whitelisted `pip install pytest` once; if denied, stop and report the restriction.
- Network: requests/urllib both fail (`SOURCE=ERROR`, `ERROR_MSG=...`) → try cache; if no cache, ask for offline input or a local HTML snapshot.
- Logic: `AssertionError` in tests → read the failing file, apply a targeted `diff_edit`, and re-run tests to confirm.
