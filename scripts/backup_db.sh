#!/usr/bin/env bash
# Backup de la base (Supabase): schema + datos en backups/backup-<ts>-*.sql
# Requiere la CLI de Supabase (en PATH o ~/bin), Docker corriendo y en .env:
#   SUPABASE_URL, SUPABASE_DB_PASSWORD
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Backup de la base de datos (Supabase) ==="

[[ -f .env ]] || { echo "ERROR: no se encontro el archivo .env"; exit 1; }

SUPABASE_URL=$(grep '^SUPABASE_URL=' .env | cut -d= -f2- | tr -d '\r')
SUPABASE_DB_PASSWORD=$(grep '^SUPABASE_DB_PASSWORD=' .env | cut -d= -f2- | tr -d '\r')

[[ -n "$SUPABASE_URL" ]] || { echo "ERROR: falta SUPABASE_URL en el .env"; exit 1; }
if [[ -z "$SUPABASE_DB_PASSWORD" ]]; then
  echo "ERROR: falta SUPABASE_DB_PASSWORD en el .env."
  echo "Es la contrasena de Postgres (no la API key): se obtiene o se"
  echo "resetea en el dashboard, Project Settings -> Database."
  exit 1
fi
echo "[OK] .env cargado"

# Extraer el project ref de SUPABASE_URL (https://<ref>.supabase.co)
PROJECT_REF=${SUPABASE_URL#*//}
PROJECT_REF=${PROJECT_REF%%.*}
[[ -n "$PROJECT_REF" ]] || { echo "ERROR: no se pudo extraer el project ref de SUPABASE_URL"; exit 1; }
echo "[OK] Proyecto: $PROJECT_REF"

# Ubicar la CLI de Supabase (PATH o ~/bin)
SUPABASE_CLI=$(command -v supabase || true)
if [[ -z "$SUPABASE_CLI" ]]; then
  for candidato in "$HOME/bin/supabase" "$HOME/bin/supabase.exe"; do
    if [[ -f "$candidato" ]]; then SUPABASE_CLI=$candidato; break; fi
  done
fi
[[ -n "$SUPABASE_CLI" ]] || {
  echo "ERROR: no se encontro la CLI de Supabase."
  echo "Instalarla desde https://github.com/supabase/cli/releases"
  exit 1
}

# Verificar que Docker este corriendo (la CLI corre pg_dump en un contenedor)
if ! docker info >/dev/null 2>&1; then
  echo "Docker no esta corriendo; intentando iniciarlo..."
  if [[ -f "/c/Program Files/Docker/Docker/Docker Desktop.exe" ]]; then
    powershell -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" >/dev/null 2>&1 || true
  elif [[ -d "/Applications/Docker.app" ]]; then
    open -a Docker
  else
    sudo systemctl start docker 2>/dev/null || true
  fi
  for _ in $(seq 1 24); do docker info >/dev/null 2>&1 && break; sleep 5; done
  docker info >/dev/null 2>&1 || { echo "ERROR: Docker no arranco en 120 segundos."; exit 1; }
fi
echo "[OK] Docker corriendo"

# Codificar la contrasena para la URL (puede tener caracteres especiales)
PYTHON_BIN=$(command -v python3 || command -v python)
PASS_ENC=$("$PYTHON_BIN" -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$SUPABASE_DB_PASSWORD")
DB_URL="postgresql://postgres:${PASS_ENC}@db.${PROJECT_REF}.supabase.co:5432/postgres"

TS=$(date +%Y%m%d-%H%M)
mkdir -p backups

echo "Dump del schema..."
"$SUPABASE_CLI" db dump --db-url "$DB_URL" -f "backups/backup-${TS}-schema.sql"

echo "Dump de los datos..."
"$SUPABASE_CLI" db dump --data-only --use-copy --schema public --db-url "$DB_URL" -f "backups/backup-${TS}-data.sql"

echo
echo "=== [OK] Backup completado ==="
echo "  backups/backup-${TS}-schema.sql"
echo "  backups/backup-${TS}-data.sql"
