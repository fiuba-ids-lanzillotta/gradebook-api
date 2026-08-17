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
- `ADMIN_USER` and `ADMIN_PASSWORD` (bcrypt hash).

Recommended:
- `CORS_ORIGINS` — the frontend domain(s), comma-separated (avoid the default `*` in production).

Optional:
- `JWT_EXPIRACION_HORAS` (default `8`), `API_KEY` (restrict consumption to the frontend),
  `CACHE_TTL_ROLES` (default `300`), and the Upstash Redis credentials
  (`UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN`, `RATE_LIMIT_MAX`, `RATE_LIMIT_WINDOW`) for
  rate limiting and cache.

## Notes

- The database is external (Supabase); make sure `db/init_db.sql` has been applied to the target
  project (schema + seed).
- The API is served under the `/gradebook_api` prefix.
- `truststore` is only relevant for local corporate-TLS networks; it is harmless on Vercel.
