# Agent Capabilities

Last updated: 2026-03-10

## Stage 1 — Basic Tool Execution
- Can list workspace contents via `read_directory` using an offline fallback policy.
- Can create a new file with simple content when the task specifies filename and print text.
- Can append a quoted line to a target file when explicitly requested.
- Handles escaped quotes in append content (e.g., `\"` inside a quoted string).

## Stage 2 — Code Editing (Complete)
- Can read a target file before editing when the task explicitly requests it.
- Can perform a simple `diff_edit` replacement when old/new strings are provided.
- Can append a current-time print snippet when requested.

## Stage 3 — Test Generation (Complete)
- Can generate a minimal pytest file for simple functions using offline templates.
- Can run tests via `run_test` (python -m pytest) and record exit codes.

## Stage 4 — Self-Debugging (In Progress)
- Can attempt environment repair when pytest is missing by running a whitelisted `pip install pytest`.
- Can re-run tests after a successful environment fix.
- Adds a reflection step to trigger environment repair actions after failed runs.
- Reads test and implementation files after failed test runs to aid debugging.
- Applies a simple AssertionError repair pattern (e.g., `a - b` → `a + b`) and re-runs tests.
- Reflection can auto-read the test file on AssertionError to improve context.
- Reflection checks for the presence of tests when a task requests them.

## Stage 5 — Multi-Step Planning (In Progress)
- Planner can prefer a TDD-like order (tests → implementation → run_test) when tests are requested.
- Offline fallback supports multi-file tasks (e.g., BankAccount class + tests) with a preset template.

## Stage 6 — Real-World Tasks (In Progress)
- Offline fallback can generate a basic web-to-PDF script using requests + reportlab.
- Reflection can install whitelisted external libraries (requests/reportlab) when missing.
- Verifies generated PDFs via `ls -l` after execution.
- PDF generation proceeds even if HTTP fetch fails (fallback text is written).
- Falls back to HTML output when reportlab installation fails, and can switch to urllib if requests is unavailable.
- Scripts print output format and fetch library used for reporting.
- Output filenames are inferred from the target URL and optional output directories.
- Can intentionally fall back to HTML when PDF libraries are denied, with rationale recorded in thoughts.
- Generates and logs extracted titles (TITLE_COUNT) for content validation.
- Retries network fetch with urllib when requests fails before declaring network failure.
- Generated scripts perform preflight checks (DNS + write permission) and report results.
- Network fetch can fall back to cached HTML when live requests fail.
- PDF output includes a validation pass that checks title strings in the generated binary and can trigger HTML fallback.

## Known Limits
- LLM (Ollama) connectivity is not available in this environment, so complex reasoning relies on minimal offline heuristics.
- Offline fallback supports only simple multi-step edit/test flows and does not infer complex refactors.
- `pip install` is restricted to a whitelist (currently `pytest`, `requests`, `reportlab`).
- pytest is now installed in the venv, but installation can fail in restricted environments.
- External HTTP calls can fail due to network restrictions; scripts now fall back to a local error message.
- Fallback HTML output is used when PDF libraries cannot be installed.
