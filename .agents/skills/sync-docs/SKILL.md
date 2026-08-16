---
name: sync-docs
description: Audit and update README.md and docs/swagger.yaml so the documentation matches the current code
allowed-tools:
  - read
  - edit
  - grep
  - glob
permissions:
  allow:
    - Read(**)
  ask:
    - Write(README.md)
    - Write(docs/**)
---

Keep the documentation in sync with the code. **Only touch documentation** (`README.md`,
`docs/swagger.yaml`) — never change application code from this skill.

## Sources of truth

Read the code and compare it against the docs:
- `gradebook_api/routes/*.py` — endpoints, methods, auth (`@requiere_auth`), status codes returned.
- `gradebook_api/services/*.py` and `gradebook_api/validators/*.py` — DTO shapes, validations, error codes.
- `gradebook_api/constants.py` / `gradebook_api/config.py` — domain constants and environment variables.
- `db/init_db.sql` — tables/columns and seed.
- `.env.example` — the full set of environment variables.
- `app.py` — registered blueprints and the `BASE_URL` prefix.

## What to check and fix

### `docs/swagger.yaml`
- Every route in `gradebook_api/routes/` has a matching path/method, and there are no documented
  paths that no longer exist.
- Status codes match reality (e.g. `400/401/403/404/409`; a 204 only where the code returns 204).
- Request/response schemas match the DTOs and validated fields (types, `nullable`, enums, examples).

### `README.md`
- **Endpoints table** matches the actual routes.
- **Environment variables** table/example lists exactly what `config.py` reads (and `.env.example`),
  including defaults.
- **Project structure** tree reflects the real files/dirs (`config.py`, `tests/`, `vercel.json`,
  `requirements-dev.txt`, `.agents/`, etc.).
- No stale references (removed features, old names, old examples).

## Method

1. Build the real list of endpoints + status codes from `routes/` and cross-check `swagger.yaml`.
2. Build the real list of env vars from `config.py` + `.env.example` and cross-check the README table.
3. Verify the structure tree and any domain sections against the codebase.
4. Apply the doc fixes. Do not invent behavior — if unsure, inspect the code.

## Deliverable

Report the mismatches found and the fixes applied, grouped by file (`README.md`, `swagger.yaml`).
If everything was already consistent, say so explicitly.
