#!/usr/bin/env bash
# Vuelve a apuntar el .env a la base de PRODUCCION (Supabase cloud).
set -euo pipefail
cd "$(dirname "$0")/.."

[[ -f .env.prod ]] || {
  echo "ERROR: no existe .env.prod. Guarda ahi la config de produccion"
  echo "(copia del .env original)."
  exit 1
}
cp .env.prod .env
echo "[OK] .env apunta a la base de PRODUCCION."
