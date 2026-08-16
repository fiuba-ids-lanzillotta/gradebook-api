---
name: verify
description: Run the project's verification suite (tests + syntax check)
allowed-tools:
  - read
  - exec
permissions:
  allow:
    - Read(**)
    - Exec(pytest*)
    - Exec(python*)
    - Exec(pip install*)
---

Run the verification suite and report the result. Do not change code; if something fails, report
the failing test(s) and the likely cause.

## Steps

1. Ensure dev dependencies are installed (only if `pytest` is missing):
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run the tests (they set dummy `SUPABASE_URL`/`SUPABASE_KEY` via `conftest.py`, no network):
   ```bash
   pytest -q
   ```

3. Syntax check:
   ```bash
   python -m compileall -q gradebook_api app.py
   ```

## Report

- Tests: passed / failed (with names and the first failing assertion).
- Compile: OK / errors.
- If everything is green, say so explicitly.
