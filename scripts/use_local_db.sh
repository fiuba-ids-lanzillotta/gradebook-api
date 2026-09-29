#!/usr/bin/env bash
# Cambia el .env para apuntar a la base LOCAL (Supabase en Docker).
# La config local vive en .env.local (gitignored); la de prod en .env.prod.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -f .env.local ]] || {
  echo 'ERROR: no existe .env.local. Crealo a partir de .env.example con los'
  echo 'valores que imprime "supabase start" (SUPABASE_URL=http://127.0.0.1:54321).'
  exit 1
}
cp .env.local .env
echo "[OK] .env apunta a la base LOCAL. El stack se levanta con: supabase start"
