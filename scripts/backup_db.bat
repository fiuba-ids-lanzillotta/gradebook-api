@echo off
setlocal
pushd "%~dp0.."

echo === Backup de la base de datos (Supabase) ===

REM Cargar SUPABASE_URL y SUPABASE_DB_PASSWORD desde .env

if not exist ".env" (
    echo ERROR: no se encontro el archivo .env
    exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if "%%a"=="SUPABASE_URL" set "SUPABASE_URL=%%b"
    if "%%a"=="SUPABASE_DB_PASSWORD" set "SUPABASE_DB_PASSWORD=%%b"
)
if not defined SUPABASE_URL (
    echo ERROR: falta SUPABASE_URL en el .env
    exit /b 1
)
if not defined SUPABASE_DB_PASSWORD (
    echo ERROR: falta SUPABASE_DB_PASSWORD en el .env.
    echo Es la contrasena de Postgres ^(no la API key^): se obtiene o se
    echo resetea en el dashboard, Project Settings -^> Database.
    exit /b 1
)
echo [OK] .env cargado

REM Extraer el project ref de SUPABASE_URL (https://<ref>.supabase.co)
set "SIN_PROTOCOLO=%SUPABASE_URL:*//=%"
for /f "tokens=1 delims=." %%r in ("%SIN_PROTOCOLO%") do set "PROJECT_REF=%%r"
if not defined PROJECT_REF (
    echo ERROR: no se pudo extraer el project ref de SUPABASE_URL
    exit /b 1
)
echo [OK] Proyecto: %PROJECT_REF%

REM Ubicar la CLI de Supabase (PATH o %USERPROFILE%\bin)
set "SUPABASE_CLI=supabase"
where supabase >nul 2>&1
if %ERRORLEVEL% neq 0 (
    if exist "%USERPROFILE%\bin\supabase.exe" (
        set "SUPABASE_CLI=%USERPROFILE%\bin\supabase.exe"
    ) else (
        echo ERROR: no se encontro la CLI de Supabase.
        echo Instalarla desde https://github.com/supabase/cli/releases
        echo ^(supabase_windows_amd64.tar.gz^) y copiar supabase.exe a %USERPROFILE%\bin
        exit /b 1
    )
)

REM Verificar que Docker este corriendo (la CLI corre pg_dump en un contenedor)
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Docker no esta corriendo; iniciando Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    set "INTENTOS=0"
    :esperar_docker
    timeout /t 5 /nobreak >nul
    docker info >nul 2>&1
    if %ERRORLEVEL% equ 0 goto docker_ok
    set /a INTENTOS+=1
    if %INTENTOS% lss 24 goto esperar_docker
    echo ERROR: Docker no arranco en 120 segundos.
    exit /b 1
    :docker_ok
)
echo [OK] Docker corriendo

REM Codificar la contrasena para la URL (puede tener caracteres especiales)
for /f "usebackq delims=" %%e in (`powershell -NoProfile -Command "[uri]::EscapeDataString('%SUPABASE_DB_PASSWORD%')"`) do set "PASS_ENC=%%e"
set "DB_URL=postgresql://postgres:%PASS_ENC%@db.%PROJECT_REF%.supabase.co:5432/postgres"

REM Timestamp para el nombre de archivo
for /f "usebackq delims=" %%t in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"`) do set "TS=%%t"
if not exist backups mkdir backups

echo Dump del schema...
"%SUPABASE_CLI%" db dump --db-url "%DB_URL%" -f "backups/backup-%TS%-schema.sql"
if %ERRORLEVEL% neq 0 (
    echo ERROR: fallo el dump del schema.
    exit /b 1
)

echo Dump de los datos...
"%SUPABASE_CLI%" db dump --data-only --use-copy --schema public --db-url "%DB_URL%" -f "backups/backup-%TS%-data.sql"
if %ERRORLEVEL% neq 0 (
    echo ERROR: fallo el dump de los datos.
    exit /b 1
)

echo.
echo === [OK] Backup completado ===
echo   backups/backup-%TS%-schema.sql
echo   backups/backup-%TS%-data.sql
