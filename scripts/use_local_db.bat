@echo off
REM Cambia el .env para apuntar a la base LOCAL (Supabase en Docker).
REM La config local vive en .env.local (gitignored); la de prod en .env.prod.
pushd "%~dp0.."
if not exist ".env.local" (
    echo ERROR: no existe .env.local. Crealo a partir de .env.example con los
    echo valores que imprime "supabase start" ^(SUPABASE_URL=http://127.0.0.1:54321^).
    exit /b 1
)
copy /y .env.local .env >nul
echo [OK] .env apunta a la base LOCAL. El stack se levanta con: supabase start
