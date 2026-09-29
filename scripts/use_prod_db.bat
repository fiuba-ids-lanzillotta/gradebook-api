@echo off
REM Vuelve a apuntar el .env a la base de PRODUCCION (Supabase cloud).
pushd "%~dp0.."
if not exist ".env.prod" (
    echo ERROR: no existe .env.prod. Guarda ahi la config de produccion
    echo ^(copia del .env original^).
    exit /b 1
)
copy /y .env.prod .env >nul
echo [OK] .env apunta a la base de PRODUCCION.
