---
name: deploy-vercel
description: Checklist to deploy this API to Vercel (config and required environment variables)
allowed-tools:
  - read
  - grep
  - glob
permissions:
  allow:
    - Read(**)
---

Guide the deploy of this API to Vercel. This is mostly a checklist; do not commit secrets.

## Config

- `vercel.json` defines a Python function over `app.py` with `includeFiles: "gradebook_api/**"`
  (the package source; there are no templates/static because this is an API).
- The entry point is `app.py`, which exposes the WSGI `app`.

## Environment variables (set in the Vercel dashboard, NOT via .env)

Required:
- `SUPABASE_URL` — API URL of the Supabase project.
- `SUPABASE_KEY` — the **service_role** key (secret).
- `JWT_SECRET` — long random secret (`python -c "import secrets; print(secrets.token_hex(32))"`).
- `FRONTEND_URL` — base of gradebook-web (the password-reset link is built with it).
- `RECAPTCHA_SECRET` — reCAPTCHA v2 secret used by `/login` (or `RECAPTCHA_DISABLED=true`
  only if intentionally skipping it).

Recommended:
- `CORS_ORIGINS` — the frontend domain(s), comma-separated (avoid the default `*` in production).
- **QStash wiring (emails)**: `QSTASH_URL` (regional base from the Upstash console, e.g.
  `https://qstash-us-east-1.upstash.io`), `QSTASH_TOKEN` (publish token) and
  `MAIL_WORKER_URL` (the gradebook-mailer deploy URL — must match the URL QStash signs).
  Without them the API runs in dev mode: payloads get logged and `enviar-qrs` does a
  dry-run, so real emails never leave. Do NOT leave it unset in production.
- Upstash Redis (`UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN`,
  `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`) for rate limiting, cache and the reset-token
  store — required in practice for `PASSWORD_RESET_TTL` to work.

Optional:
- `JWT_EXPIRACION_HORAS` (default `8`), `API_KEY` (restrict consumption to the frontend),
  the `CACHE_TTL_*` TTLs, `PASSWORD_RESET_TTL` (1800), `ASISTENCIA_*` tunables
  (`LOTE_EMAILS_WORKER`, `MARCA_ENCOLADO_SEGUNDOS`, `MAX_INTENTOS_ENVIO`,
  `DB_MAX_REINTENTOS`, `DB_BACKOFF_MS`).

## Removed env vars (delete from Vercel if still set)

- `ADMIN_USER` / `ADMIN_PASSWORD` — auth is against the `docentes`/`estudiantes` tables.
- All `MAIL_*` — the API no longer sends emails; SMTP config lives in gradebook-mailer.
- `ASISTENCIA_EMAILS_PAUSA_MS` / `ASISTENCIA_EMAILS_MAX_REINTENTOS` /
  `ASISTENCIA_EMAILS_BACKOFF_MS` — SMTP retry tunables, moved to the worker.

## Notes

- The database is external (Supabase); make sure `db/init_db.sql` has been applied to the target
  project (schema + seed).
- The API is served under the `/gradebook_api` prefix.
- `truststore` is only relevant for local corporate-TLS networks; it is harmless on Vercel.
