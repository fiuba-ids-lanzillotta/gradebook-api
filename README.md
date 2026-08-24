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
| `CACHE_TTL_CURSADAS` | TTL (seg) del cache de cursos (default `300`). |
| `CACHE_TTL_ESTUDIANTES` | TTL (seg) del cache del listado de estudiantes (default `60`; se invalida en cada escritura). |
| `API_KEY` | Si tiene valor, exige `X-API-Key` en toda request. Vacío = sin key. |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Credenciales Upstash (rate limiting + cache). Vacío = deshabilitado (fail-open). |
| `RATE_LIMIT_MAX` / `RATE_LIMIT_WINDOW` | Límite por IP (default `100`/`60`). |
| `FRONTEND_URL` | Base del frontend para el link de recuperación (default `http://localhost:5001`). |
| `PASSWORD_RESET_TTL` | TTL (seg) del token de recuperación (default `1800`). Requiere Upstash. |
| `RESEND_API_KEY` / `RESEND_FROM` | Envío por API HTTP (Resend, puerto 443). Recomendado detrás de VPN que bloquea SMTP. Si está seteada, tiene prioridad sobre SMTP. |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USE_TLS` / `MAIL_USE_SSL` | SMTP (fallback) para el mail de recuperación. |
| `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_DEFAULT_SENDER` | Credenciales SMTP. Sin Resend ni SMTP = no se envía, se loguea el link (dev). |
| `MAIL_SUPPRESS_SEND` | `true` = no enviar por SMTP (se loguea el link). |

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
| POST | `/password-reset/solicitar` | — | Pide el email de recuperación (respuesta uniforme). |
| POST | `/password-reset/confirmar` | — | Restablece la contraseña con el token de un solo uso. |
| GET | `/me` | (autenticado) | Identidad + permisos efectivos. |
| GET/POST | `/docentes` | `docentes.leer` / `docentes.gestionar` | Listar / crear docentes. |
| GET/PUT/DELETE | `/docentes/{id}` | `docentes.leer` / `docentes.gestionar` | Ver / editar / eliminar. |
| PUT | `/docentes/{id}/permisos` | `permisos.asignar` | Overrides de permisos del docente. |
| GET | `/estudiantes` | `estudiantes.leer` | Estudiantes de una cursada (`?anio=&cuatrimestre=` + búsqueda `q` (OR: numérico→padrón/email, alfabético→nombre/apellido/email) o filtros `nombre/apellido/padron/email` + paginación `_offset/_limit`); incluye `recursa`, `estado`, `motivos_baja` y `_links` (HATEOAS). |
| POST | `/estudiantes` | `estudiantes.gestionar` | Crear estudiante e inscribirlo en la cursada vigente. |
| POST | `/estudiantes/csv` | `estudiantes.gestionar` | Alta masiva por CSV (export SIU; password = padrón) + inscripción en la cursada vigente. |
| GET/PUT | `/estudiantes/{id}` | `estudiantes.leer` / `estudiantes.gestionar` | Ver / editar. |
| POST | `/estudiantes/{id}/baja` | `estudiantes.gestionar` | Baja lógica / abandono en la cursada vigente (`{estado, motivo}`; `motivo` obligatorio si `baja`). |
| PUT | `/estudiantes/{id}/permisos` | `permisos.asignar` | Overrides de permisos del estudiante. |
| GET | `/cursadas` | `cursadas.leer` | Lista cursos/cursadas (filtros `codigo/anio/cuatrimestre` + paginación); expone código, nombre, año, cuatrimestre, fechas y `vigente` (si transcurre hoy). |
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
