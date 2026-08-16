# gradebook-api

Proyecto **base** de una API REST en **Flask**, pensado como punto de partida. Expone un login de
administración con roles (JWT) y un recurso de ejemplo `items` con CRUD completo. Sigue el mismo
estilo y arquitectura que el resto de los proyectos del workspace (basado en `ids-api`).

## Tecnologías

- **Python 3.10+**
- **Flask 3.0.3** + **flask-cors** (API y CORS para el frontend)
- **Supabase** (`supabase-py`) como backend de datos (PostgREST sobre PostgreSQL)
- **PyJWT** (autenticación stateless) + **bcrypt** (hashing de passwords)
- **Upstash Redis** (REST) para rate limiting y cache (opcional, fail-open)
- **python-dotenv** (variables de entorno)
- **Supabase CLI** para el entorno local (`supabase start`)

Estilo **funcional** (sin clases, DTOs como `dict`) y separación en capas
**routes / services / validators / db**. La capa `db` usa el **cliente de Supabase** (query
builder), no ejecuta SQL crudo desde la app.

## Arquitectura

```
Flujo de una request:

  Frontend / cliente
       |
       |  HTTP (JSON) [+ header Authorization: Bearer <jwt> en endpoints admin]
       v
  Flask API (este proyecto, puerto 5000)
       |   - valida el body / parámetros
       |   - en endpoints protegidos: decodifica el JWT y valida el rol
       |   - usa el cliente de Supabase (service_role)
       v
  Supabase (PostgREST + PostgreSQL)
```

## Estructura del proyecto

```
gradebook-api/
├── app.py                       # Entry point Flask (puerto 5000, CORS, API key, rate limit, blueprints)
├── requirements.txt             # Dependencias Python
├── requirements-dev.txt         # Dependencias de desarrollo (pytest)
├── vercel.json                  # Configuración de deploy en Vercel
├── pytest.ini / conftest.py     # Configuración de los tests
├── .env.example                 # Template de variables de entorno
├── setup_virtualenv.bat/.sh     # Scripts de setup con virtualenv
├── setup_pipenv.bat/.sh         # Scripts de setup con pipenv
├── AGENTS.md / README.md / LICENSE
├── .gitignore / .gitattributes
├── .agents/skills/              # Skills del proyecto (verify, add-endpoint, schema-change, ...)
│
├── gradebook_api/
│   ├── constants.py             # Constantes de dominio (roles, longitudes, códigos de error)
│   ├── config.py                # Configuración de entorno (Supabase, JWT, admin, CORS, Redis)
│   ├── db.py                    # Capa de acceso a datos (cliente de Supabase)
│   ├── utils.py                 # Validaciones, bcrypt, JWT, @requiere_auth
│   ├── cache.py                 # Cache-aside en Redis (Upstash) con invalidación
│   ├── ratelimit.py             # Rate limiting por IP (Upstash), fail-open
│   ├── routes/                  # Un blueprint por recurso
│   │   ├── auth.py              #   POST /login, GET /me
│   │   └── items.py             #   CRUD del recurso de ejemplo
│   ├── services/                # Lógica de negocio (una por recurso)
│   │   ├── auth.py
│   │   └── items.py
│   └── validators/              # Validación de bodies (una por recurso)
│       ├── auth.py
│       └── items.py
│
├── db/
│   ├── init_db.sql              # Esquema + seed (para correr en Supabase)
│   └── schema.md                # Diagrama entidad-relación (Mermaid)
├── docs/
│   └── swagger.yaml             # Documentación OpenAPI 3.0 de la API
└── tests/                       # Tests (pytest): utils, validators, servicios, rutas, cache, ratelimit
```

## Configuración

### 1. Variables de entorno

Copiá `.env.example` a `.env` y completá los valores:

```bash
cp .env.example .env        # Linux / macOS
copy .env.example .env      # Windows
```

| Variable         | Descripción                                                                 |
|------------------|-----------------------------------------------------------------------------|
| `SUPABASE_URL`   | URL de la API del proyecto Supabase (en local la imprime `supabase start`). |
| `SUPABASE_KEY`   | **service_role** key (secreta, no se expone al frontend).                   |
| `JWT_SECRET`     | Clave con la que se firman los tokens. Usá una propia y larga fuera de local. |
| `JWT_EXPIRACION_HORAS` | Horas de validez del token (default `8`).                             |
| `ADMIN_USER`     | Usuario del panel de administración (único usuario).                        |
| `ADMIN_PASSWORD` | **Hash bcrypt** del password del admin (no el password en texto plano).     |
| `CORS_ORIGINS`   | Orígenes permitidos para CORS, separados por coma (default `*` = todos).     |
| `CACHE_TTL_ITEMS`| TTL (segundos) del cache en Redis (default `300`; se invalida en cada escritura). Requiere Upstash. |
| `API_KEY`        | Si tiene valor, exige el header `X-API-Key` en toda request. Vacío = API pública. |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Credenciales de Upstash (REST) para rate limiting y cache. Vacío = ambos deshabilitados (fail-open). |
| `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW` | Límite por IP: máximo de requests por ventana en segundos (default `100`/`60`). |

> El `.env` está en `.gitignore` y **no debe subirse al repositorio**.

Para generar una `JWT_SECRET` aleatoria:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Para generar el hash bcrypt de `ADMIN_PASSWORD`:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'tu-password', bcrypt.gensalt()).decode())"
```

### 2. Base de datos (Supabase)

El backend habla con Supabase a través de su cliente (PostgREST), no ejecuta SQL desde la app.
El esquema y el diagrama entidad-relación están en [`db/schema.md`](db/schema.md).

#### Desarrollo local con la CLI de Supabase

```bash
# 1. Instalar la CLI: https://supabase.com/docs/guides/cli
# 2. Inicializar (una vez) y levantar el stack local
supabase init
supabase start
```

`supabase start` imprime la **API URL** y las keys (`anon` y `service_role`). Copiá la API URL a
`SUPABASE_URL` y la `service_role` key a `SUPABASE_KEY` en tu `.env`.

Luego aplicá el esquema y el seed corriendo [`db/init_db.sql`](db/init_db.sql) en la base local
(por ejemplo desde el editor SQL de Supabase Studio, en `http://127.0.0.1:54323`).

### 3. Entorno virtual, instalación y ejecución

Los scripts crean el entorno virtual, instalan las dependencias y levantan la API.

**Con virtualenv:**

```bash
setup_virtualenv.bat          # Windows
chmod +x setup_virtualenv.sh && ./setup_virtualenv.sh   # Linux / macOS
```

**Con pipenv:**

```bash
setup_pipenv.bat              # Windows
chmod +x setup_pipenv.sh && ./setup_pipenv.sh           # Linux / macOS
```

También manualmente:

```bash
python -m venv .venv
source .venv/bin/activate     # Linux / macOS
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python app.py
```

Una vez iniciada, la API estará disponible en `http://localhost:5000/gradebook_api`.

### 4. Acceso de administración

No hay tabla de usuarios: se usa un **único usuario** configurado por variables de entorno
(`ADMIN_USER` / `ADMIN_PASSWORD`). Para obtener un token, hacé login con esas credenciales:

```bash
curl -X POST http://localhost:5000/gradebook_api/login \
  -H "Content-Type: application/json" \
  -d '{"usuario":"admin","password":"tu-password"}'
```

La respuesta trae `{token, usuario}`. Ese `token` se envía en el header
`Authorization: Bearer <token>` en los endpoints protegidos.

## Endpoints

| Método | Ruta                 | Auth  | Descripción                        |
|--------|----------------------|-------|------------------------------------|
| POST   | `/login`             | —     | Login del admin, devuelve un JWT.  |
| GET    | `/me`                | JWT   | Identidad del admin autenticado.   |
| GET    | `/items`             | —     | Lista todos los items.             |
| GET    | `/items/{id}`        | —     | Obtiene un item por id.            |
| POST   | `/items`             | admin | Crea un item.                      |
| PUT    | `/items/{id}`        | admin | Actualiza un item.                 |
| DELETE | `/items/{id}`        | admin | Elimina un item.                   |

Todas bajo el prefijo `/gradebook_api`. Detalle completo (schemas y status codes) en
[`docs/swagger.yaml`](docs/swagger.yaml).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
python -m compileall -q gradebook_api app.py
```

Los tests cubren funciones puras (validaciones, servicios con la `db` mockeada, rutas con
`test_client`) y no hacen llamadas de red.

## Deploy

Vercel: función Python sobre `app.py` (ver `vercel.json`). Las variables de entorno se setean en el
dashboard de Vercel (no vía `.env`, que no se commitea).
