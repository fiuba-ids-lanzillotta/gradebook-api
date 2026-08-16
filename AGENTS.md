# AGENTS.md

Guide for agents (and people) working on **gradebook-api**. Keep it short and actionable.

## Overview

A **base** REST API in **Flask**: admin authentication (JWT) and an example resource `items` with a
full CRUD. Data backend: **Supabase** (PostgREST). Meant as a starting point for building the real
API (e.g. consumed by a frontend like `gradebook-web`).

## How to run

```bash
# setup + run (creates venv, installs deps, starts the API on :5000)
setup_virtualenv.bat        # Windows
./setup_virtualenv.sh       # Linux / macOS

# or manually
python -m venv .venv && .venv\Scripts\activate   # (source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
python app.py
```

Requires a `.env` (see `.env.example`): `SUPABASE_URL`, `SUPABASE_KEY`, `JWT_SECRET`,
`ADMIN_USER`, `ADMIN_PASSWORD` (bcrypt hash), and optional `CORS_ORIGINS`, `JWT_EXPIRACION_HORAS`,
`API_KEY`, and for Upstash Redis (rate limiting + cache): `UPSTASH_REDIS_REST_URL`,
`UPSTASH_REDIS_REST_TOKEN`, `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`, `CACHE_TTL_ITEMS`. The API is
mounted under `/gradebook_api`.

`API_KEY` (if set) restricts consumption to the frontend: every request must send `X-API-Key` with
that value.

**Redis (Upstash, REST)** powers two features, both **env-gated** (disabled without credentials)
and **fail-open** (never break the request if Redis is down):
- **Rate limiting** per IP (`before_request` in `app.py` → `ratelimit.py`).
- **Cache** (`cache.py`): cache-aside for the list GET (`items:filas`), **invalidated on every
  write**. The public GETs are `Cache-Control: no-store` so invalidation takes effect immediately.

## Verification (run before considering a change done)

```bash
pip install -r requirements-dev.txt
pytest                                          # pure-function tests (no network)
python -m compileall -q gradebook_api app.py    # syntax check
```

The tests set dummy `SUPABASE_URL`/`SUPABASE_KEY` in `conftest.py`, so they never hit Supabase.
Importing `gradebook_api.db` creates the Supabase client, so those env vars must be set (even if
dummy) in order to import/test.

## Code conventions

- **Functional style: do NOT use classes.** DTOs and payloads are `dict`.
- **Avoid `break`/`continue`/`pass`** unless strictly necessary or unavoidable (e.g. `pass` in an
  `except`); prefer clear `if`/`else` or `try/except/else`.
- **Spanish naming, no abbreviations** (self-explanatory variables: `error` not `e`,
  `respuesta` not `r`, etc.). The domain vocabulary stays in Spanish.
- **Layers**: `routes → services → validators → db`. Routes hold no business logic; the `db`
  layer uses the Supabase client (query builder), **never raw SQL** from the app.
- **Constants vs config**: `constants.py` = domain constants (roles, lengths, error codes);
  `config.py` = environment configuration (Supabase, JWT, admin, CORS).
- **Errors**: raised as `raise ValueError(construir_error_api(...), status)` (status defaults to
  400) and routes translate them to `jsonify(payload), status`. Payload shape:
  `{"errors": [{"code", "message", "level", "description"}]}`.
- Don't add/remove comments needlessly; mirror the existing style.

## How to add a new resource

Mirror the `items` pattern across all four layers:
1. `gradebook_api/db.py`: query-builder functions (`CAMPOS_*`, select/insert/update/delete).
2. `gradebook_api/validators/<recurso>.py`: a `validar_body_<recurso>` that accumulates errors and
   returns a validated `dict` (reuse the helpers in `utils.py`).
3. `gradebook_api/services/<recurso>.py`: business logic, DTOs as `dict`, domain errors via
   `raise ValueError(construir_error_api(...), status)`.
4. `gradebook_api/routes/<recurso>.py`: thin handler; public reads without auth, writes with
   `@requiere_auth(rol=ROL_ADMIN)`.
5. Register the blueprint in `app.py` (`url_prefix=BASE_URL`).
6. Add any new error codes to `constants.py`.
7. Document in `docs/swagger.yaml` and update `db/init_db.sql` + `db/schema.md`.
8. Tests: one at the service level (with `db` mocked via `monkeypatch`) and one end-to-end route
   test (with `app.test_client()` and a real JWT via `generar_token('admin', 'admin')`).

There is an `add-endpoint` skill in `.agents/skills/` that automates this checklist.

## Skills

Project skills live in `.agents/skills/` (committed; tool-agnostic `.agents` standard): `verify`,
`add-endpoint`, `schema-change`, `sync-docs`, `deploy-vercel`, `manage-secrets`,
`code-review-python`.

## Deploy

- Vercel (`vercel.json`, Python function over `app.py`). Environment variables are set in the
  Vercel dashboard (not via `.env`, which is not committed).

## Do not

- Do not introduce classes.
- Do not run raw SQL from the app (use the Supabase client).
- Do not expose or commit secrets (`.env`, the `service_role` key).
- Do not weaken security controls to work around CI.

## Git

- Commit messages in Spanish, focused on the "why".
- Do not push unless explicitly asked.

## Pointers

- API documented in `docs/swagger.yaml` (OpenAPI 3.0).
- Database schema in `db/schema.md` (source of truth: `db/init_db.sql`).
