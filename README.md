# gradebook-api

API REST en **Flask** para la gestión de una cátedra: autenticación propia con **JWT** y control de
acceso por **roles y permisos (RBAC)**. Las personas son **docentes** y **estudiantes** (login por
email). Basada en la arquitectura de `ids-api`.

## Tecnologías

- **Python 3.10+**
- **Flask 3.0.3** + **flask-cors**
- **Supabase** (`supabase-py`) como backend de datos (PostgREST sobre PostgreSQL)
- **PyJWT** (autenticación stateless) + **bcrypt** (hashing de passwords)
- **Upstash Redis** (REST) para rate limiting y cache (opcional, fail-open)
- **python-dotenv** / **Supabase CLI** (entorno local)

Estilo **funcional** (sin clases, DTOs como `dict`) y separación en capas
**routes / services / validators / db**. La capa `db` usa el **cliente de Supabase** (query
builder), no ejecuta SQL crudo desde la app.

## Roles y permisos (RBAC)

- **Roles**: `super_admin` (docente a cargo), `admin` (ayudantes/colaboradores), `usuario` (estudiantes).
- El rol de seguridad se **deriva**: docente según su cargo (`Profesor` → `super_admin`;
  `Ayudante`/`Colaborador` → `admin`); estudiante → `usuario`.
- Los **permisos por rol** se configuran en la base (`roles_permisos`), a nivel general.
- Los **overrides por usuario** (`docentes_permisos`, `estudiantes_permisos`) permiten otorgar o
  revocar permisos puntuales por persona.
- **Permiso efectivo** = permisos del rol ∪ otorgados − revocados. El decorador
  `@requiere_permiso('recurso.accion')` los resuelve por request. La matriz rol→permisos se
  **cachea** en Redis (`roles:lista`, `roles:permisos:<codigo>`) y se invalida al cambiar los
  permisos de un rol.

El modelo entidad-relación está en [`db/schema.md`](db/schema.md).

## Estructura del proyecto

```
gradebook-api/
├── app.py                       # Entry point Flask (CORS, API key, rate limit, blueprints)
├── requirements.txt / requirements-dev.txt
├── vercel.json / pytest.ini / conftest.py
├── .env.example
├── setup_virtualenv.bat/.sh / setup_pipenv.bat/.sh
├── AGENTS.md / README.md / LICENSE / .gitignore / .gitattributes
├── .agents/skills/              # Skills del proyecto (verify, add-endpoint, ...)
│
├── gradebook_api/
│   ├── constants.py             # Roles, permisos, mapeo cargo→rol, códigos de error
│   ├── config.py                # Configuración de entorno (Supabase, JWT, CORS, Redis)
│   ├── db.py                    # Capa de datos (cliente Supabase)
│   ├── utils.py                 # Validaciones, bcrypt, JWT, @requiere_auth, @requiere_permiso
│   ├── cache.py / ratelimit.py  # Redis (Upstash): cache y rate limiting
│   ├── routes/                  # auth, docentes, estudiantes, roles
│   ├── services/                # auth, docentes, estudiantes, permisos
│   └── validators/              # auth, docentes, estudiantes, permisos
│
├── db/
│   ├── init_db.sql              # Esquema + seed (roles, permisos, docentes, padrón de estudiantes)
│   └── schema.md                # Diagrama entidad-relación (Mermaid)
├── docs/swagger.yaml            # OpenAPI 3.0
└── tests/                       # pytest
```

## Configuración

### 1. Variables de entorno

Copiá `.env.example` a `.env` y completá los valores. La API se monta bajo `/gradebook_api`.

| Variable | Descripción |
|----------|-------------|
| `SUPABASE_URL` | URL de la API del proyecto Supabase. |
| `SUPABASE_KEY` | **service_role** key (secreta). |
| `JWT_SECRET` | Clave de firma de los tokens (usar una propia y larga). |
| `JWT_EXPIRACION_HORAS` | Horas de validez del token (default `8`). |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma (default `*`). |
| `CACHE_TTL_ROLES` | TTL (seg) del cache de roles/permisos (default `300`). Requiere Upstash. |
| `API_KEY` | Si tiene valor, exige `X-API-Key` en toda request. Vacío = sin key. |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Credenciales Upstash (rate limiting + cache). Vacío = deshabilitado (fail-open). |
| `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW` | Límite por IP (default `100`/`60`). |

> Ya **no** se usan `ADMIN_USER` / `ADMIN_PASSWORD`: el acceso es contra las tablas `docentes` /
> `estudiantes`.

### 2. Base de datos (Supabase)

Aplicá [`db/init_db.sql`](db/init_db.sql) en tu proyecto Supabase (editor SQL de Studio o `psql`).
Crea el esquema y siembra roles, permisos, su matriz, docentes bootstrap y el padrón de estudiantes.

**Passwords iniciales del seed** (cambiar en el primer acceso):
- **Estudiantes**: su **padrón** es la contraseña. Usuario = email.
- **Docentes**: contraseña inicial **`Prueba123#`**. Usuario = email.

### 3. Instalación y ejecución

```bash
setup_virtualenv.bat          # Windows
./setup_virtualenv.sh         # Linux / macOS
# o manualmente
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

La API queda en `http://localhost:5000/gradebook_api`.

### 4. Login

```bash
curl -X POST http://localhost:5000/gradebook_api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bruno@fi.uba.ar","password":"..."}'
```

La respuesta trae `{token, usuario}`. El `token` se envía como `Authorization: Bearer <token>`.

## Endpoints

Todos bajo el prefijo `/gradebook_api`. Detalle completo en [`docs/swagger.yaml`](docs/swagger.yaml).

| Método | Ruta | Permiso | Descripción |
|--------|------|---------|-------------|
| POST | `/login` | — | Login por email + password. |
| GET | `/me` | (autenticado) | Identidad + permisos efectivos. |
| GET/POST | `/docentes` | `docentes.leer` / `docentes.gestionar` | Listar / crear docentes. |
| GET/PUT/DELETE | `/docentes/{id}` | `docentes.leer` / `docentes.gestionar` | Ver / editar / eliminar. |
| PUT | `/docentes/{id}/permisos` | `permisos.asignar` | Overrides de permisos del docente. |
| GET | `/estudiantes` | `estudiantes.leer` | Estudiantes de una cursada (`?anio=&cuatrimestre=` + filtros `nombre/apellido/padron/email`); incluye `recursa`, `estado` y `motivos_baja`. |
| POST | `/estudiantes` | `estudiantes.gestionar` | Crear estudiante e inscribirlo en la cursada vigente. |
| POST | `/estudiantes/csv` | `estudiantes.gestionar` | Alta masiva por CSV (export SIU; password = padrón) + inscripción en la cursada vigente. |
| GET/PUT/DELETE | `/estudiantes/{id}` | `estudiantes.leer` / `estudiantes.gestionar` | Ver / editar / eliminar. |
| PUT | `/estudiantes/{id}/permisos` | `permisos.asignar` | Overrides de permisos del estudiante. |
| GET | `/roles` | `roles.gestionar` | Roles con sus permisos. |
| GET | `/permisos` | `roles.gestionar` | Catálogo de permisos. |
| PUT | `/roles/{codigo}/permisos` | `roles.gestionar` | Reemplaza los permisos de un rol. |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
python -m compileall -q gradebook_api app.py
```

Los tests cubren funciones puras (validadores, servicios con la `db` mockeada, rutas con
`test_client` y JWT real) y no hacen llamadas de red.

## Deploy

Vercel: función Python sobre `app.py` (ver `vercel.json`). Variables de entorno en el dashboard de
Vercel (no vía `.env`).
