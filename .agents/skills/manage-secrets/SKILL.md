---
name: manage-secrets
description: Generate and rotate the project secrets (admin password hash, JWT secret, API key)
allowed-tools:
  - exec
permissions:
  allow:
    - Exec(python*)
---

Generate or rotate the project's secrets. **Never** print or commit real secret values into
tracked files — only output them for the user to paste into their local `.env` and the Vercel
dashboard.

## Secrets

### `ADMIN_PASSWORD` (bcrypt hash)
The app stores the bcrypt hash, not the plaintext:
```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'THE-PASSWORD', bcrypt.gensalt()).decode())"
```

### `JWT_SECRET`
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Rotating it **invalidates all existing admin tokens** → the admin must log in again.

### `API_KEY` (restricts consumption to the frontend)
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
This value is **shared**: it must be set to the **same value** in all of these:
- `gradebook-api` → env `API_KEY` (local `.env` and the Vercel project).
- Every frontend consumer (e.g. `gradebook-web`) → its env `API_KEY`.
- Bruno collection (`../../bruno-workspace/gradebook-api-collection`) → the `api_key` environment
  variable (to keep the collection working).

## Rotation (important)

Because `API_KEY` is shared, rotate it **everywhere at once** to avoid a window of `401`s:
1. Generate the new value.
2. Update it in the backend and in every frontend consumer (local `.env` and each Vercel project)
   **together**.
3. Update the `api_key` var in the Bruno environment.
4. Redeploy the affected services if already deployed.

Leaving `API_KEY` empty disables the check — the API is public.

## Notes

- On Vercel, set these as environment variables in the dashboard, not via `.env`.
- Do not write generated values into `.env.example`, README, or any committed file.
