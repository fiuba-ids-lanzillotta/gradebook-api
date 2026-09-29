# AGENTS.md

Guide for agents (and people) working on **gradebook-api**. Keep it short and actionable.

## Overview

REST API in **Flask** for a course gradebook: own authentication (JWT) and **role/permission-based
access control (RBAC)**. People are **docentes** and **estudiantes** (login by email). Domain
resources: `docentes`, `estudiantes`, `roles`/`permisos`. Data backend: **Supabase** (PostgREST).

### Auth & RBAC (important)

- **Roles**: `super_admin` (docente a cargo), `admin` (ayudantes/colaboradores), `usuario`
  (estudiantes). The security role is **derived**, not stored: docente by cargo
  (`Profesor` → `super_admin`; `Ayudante`/`Colaborador` → `admin`), estudiante → `usuario`
  (`CARGO_A_ROL` in `constants.py`).
- **Permissions** per role live in `roles_permisos` (general) and per person in
  `docentes_permisos` / `estudiantes_permisos` (overrides: `concedido` true=grant / false=revoke).
  Effective = role perms ∪ granted − revoked (`services/auth.py::permisos_efectivos_de_payload`).
- Protect endpoints with `@requiere_permiso('recurso.accion')` (resolves per request);
  `@requiere_auth()` only checks that there is a valid token (used by `/me`).
- **Login** is `POST /login` with `{email, password}` against `docentes`/`estudiantes` (bcrypt).
  The JWT carries `sub` (id), `tipo` (docente|estudiante), `rol` and `email`.

## How to run

```bash
# setup + run (creates venv, installs deps, starts the API on :5000)
scripts\setup_virtualenv.bat   # Windows
scripts/setup_virtualenv.sh    # Linux / macOS

# or manually
python -m venv .venv && .venv\Scripts\activate   # (source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
python app.py
```

Requires a `.env` (see `.env.example`): `SUPABASE_URL`, `SUPABASE_KEY`, `JWT_SECRET`, and optional
`CORS_ORIGINS`, `JWT_EXPIRACION_HORAS`, `API_KEY`, and for Upstash Redis (rate limiting + cache):
`UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`,
`CACHE_TTL_ROLES`. The API is mounted under `/gradebook_api`. There is no env admin user: access is
against the `docentes`/`estudiantes` tables (seed in `db/init_db.sql`).

DB backup: `scripts/backup_db.*` dump schema+data of the remote DB into `backups/`
(gitignored) via `supabase db dump`. Requires the Supabase CLI, running Docker, and
`SUPABASE_DB_PASSWORD` in `.env`. Restore: apply `-schema.sql` then `-data.sql` with `psql`
(details in `README.md`).

Local DB for testing (instead of prod): `supabase start` runs the full Supabase stack in Docker
(config in `supabase/config.toml`); seed it with
`docker exec -i supabase_db_gradebook-api psql -U postgres -d postgres < db/init_db.sql`
(bash/cmd; en PowerShell: `Get-Content db/init_db.sql -Raw | docker exec -i ...`).
`scripts/use_local_db.*`/`scripts/use_prod_db.*` swap `.env` between `.env.local` and `.env.prod`
(both gitignored). Details in `README.md`.

`API_KEY` (if set) restricts consumption to the frontend: every request must send `X-API-Key` with
that value. It is shared with the frontend consumer and the Bruno collection — rotate it in all of
them at once (see the `manage-secrets` skill).

**Redis (Upstash, REST)** powers two features, both **env-gated** (disabled without credentials)
and **fail-open** (never break the request if Redis is down):
- **Rate limiting** per IP (`before_request` in `app.py` → `ratelimit.py`).
- **Cache** (`cache.py`): cache-aside per resource, **invalidated on every write**. Keys:
  `roles:lista` (roles + their permissions) and `roles:permisos:<codigo>` (role→permissions matrix
  used in the permission-resolution hot path, invalidated in `asignar_permisos_a_rol`);
  `cursadas:v<N>:<codigo>:<anio>:<cuatri>` (rows of `GET /cursadas`; `vigente` is recomputed fresh, not
  cached; the version counter se incrementa en altas/modificaciones de cursadas); and the students listing under `estudiantes:v<N>:...` where `<N>` is a version counter
  bumped on every student/inscription write (alta, edición, baja/abandono, import CSV) to invalidate
  the whole namespace at once. TTLs: `CACHE_TTL_ROLES` / `CACHE_TTL_CURSADAS` / `CACHE_TTL_ESTUDIANTES`.

**Emails asíncronos**: la API no envía emails — `cola.py` los publica en Upstash QStash
hacia `gradebook-mailer` (worker serverless, repo aparte) cuando `QSTASH_TOKEN` +
`MAIL_WORKER_URL` están configuradas. Sin ellas (dev/tests), `publicar` loguea el mensaje
que iría a la cola y `enviar_qrs` simula el envío marcando las asistencias. Contexto
y decisiones: `docs/worker-asincrono-qrs.md`; flujos: `docs/flujos.md`.

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

Mirror the `docentes`/`estudiantes` pattern across all four layers:
1. `gradebook_api/db.py`: query-builder functions (`CAMPOS_*`, select/insert/update/delete).
2. `gradebook_api/validators/<recurso>.py`: a `validar_body_<recurso>` that accumulates errors and
   returns a validated `dict` (reuse the helpers in `utils.py`).
3. `gradebook_api/services/<recurso>.py`: business logic, DTOs as `dict`, domain errors via
   `raise ValueError(construir_error_api(...), status)`.
4. `gradebook_api/routes/<recurso>.py`: thin handler; protect each endpoint with
   `@requiere_permiso('recurso.accion')` (add the new permission codes to `constants.py` and seed
   them in `roles_permisos`).
5. Register the blueprint in `app.py` (`url_prefix=BASE_URL`).
6. Add any new error/permission codes to `constants.py`.
7. Document in `docs/swagger.yaml` and update `db/init_db.sql` + `db/schema.md`.
8. Tests: one at the service level (with `db` mocked via `monkeypatch`) and one end-to-end route
   test (with `app.test_client()`, a real JWT via `generar_token(1, 'docente', 'super_admin',
   'x@fi.uba.ar')`, and `monkeypatch` on `services.auth.tiene_permiso`).

There is an `add-endpoint` skill in `.agents/skills/` that automates this checklist.

## Skills

Project skills live in `.agents/skills/` (committed; tool-agnostic `.agents` standard): `verify`,
`add-endpoint`, `schema-change`, `sync-docs`, `sync-bruno`, `deploy-vercel`, `manage-secrets`,
`code-review-python`.

## Deploy

- Vercel (`vercel.json`, Python function over `app.py`). Environment variables are set in the
  Vercel dashboard (not via `.env`, which is not committed).

## Do not

- Do not introduce classes.
- Do not run raw SQL from the app (use the Supabase client).
- Do not expose or commit secrets (`.env`, the `service_role` key).
- Do not weaken security controls to work around CI.
- Do not run writes/migrations against the production Supabase project via the MCP server
  without explicit confirmation (reads are fine).

## Git

- Commit messages in Spanish, focused on the "why".
- Do not push unless explicitly asked.

## Pointers

- API documented in `docs/swagger.yaml` (OpenAPI 3.0).
- Flow diagrams (async emails, QR send, password reset) in `docs/flujos.md` (Mermaid).
- Database schema in `db/schema.md` (source of truth: `db/init_db.sql`).
- Bruno API collection: `../../bruno-workspace/gradebook-api-collection` (kept in sync via the
  `sync-bruno` skill).
