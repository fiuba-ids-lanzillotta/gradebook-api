# Esquema de la base de datos

Diagrama entidad-relación de la base (PostgreSQL / Supabase). Fuente de verdad: [`init_db.sql`](init_db.sql).

```mermaid
erDiagram
    roles {
        bigint   id          PK "identity"
        varchar  codigo      UK "super_admin | admin | usuario"
        varchar  nombre         "NOT NULL (50)"
        varchar  descripcion    "nullable (200)"
    }

    permisos {
        bigint   id          PK "identity"
        varchar  codigo      UK "recurso.accion (80)"
        varchar  descripcion    "nullable (200)"
    }

    roles_permisos {
        bigint   rol_id      FK "PK -> roles.id (ON DELETE CASCADE)"
        bigint   permiso_id  FK "PK -> permisos.id (ON DELETE CASCADE)"
    }

    docentes {
        bigint      id            PK "identity"
        varchar     nombre           "NOT NULL (100)"
        varchar     apellido         "NOT NULL (100)"
        varchar     email         UK "NOT NULL (150) - login"
        varchar     rol              "NOT NULL (20) - cargo: Profesor|Ayudante|Colaborador"
        varchar     foto             "nullable (255) - path en el bucket"
        varchar     password_hash    "NOT NULL (255) - bcrypt"
        boolean     activo           "NOT NULL default true"
        timestamptz created_at       "NOT NULL default now()"
        timestamptz updated_at       "NOT NULL default now() (lo setea la API)"
    }

    estudiantes {
        bigint      id            PK "identity"
        varchar     padron        UK "NOT NULL (20)"
        varchar     nombre           "NOT NULL (100)"
        varchar     apellido         "NOT NULL (100)"
        varchar     email         UK "NOT NULL (150) - login"
        varchar     password_hash    "NOT NULL (255) - bcrypt"
        boolean     activo           "NOT NULL default true"
        timestamptz created_at       "NOT NULL default now()"
        timestamptz updated_at       "NOT NULL default now() (lo setea la API)"
    }

    docentes_permisos {
        bigint   docente_id    FK "PK -> docentes.id (ON DELETE CASCADE)"
        bigint   permiso_id    FK "PK -> permisos.id (ON DELETE CASCADE)"
        boolean  concedido        "NOT NULL (true=otorga, false=revoca)"
    }

    estudiantes_permisos {
        bigint   estudiante_id FK "PK -> estudiantes.id (ON DELETE CASCADE)"
        bigint   permiso_id    FK "PK -> permisos.id (ON DELETE CASCADE)"
        boolean  concedido        "NOT NULL (true=otorga, false=revoca)"
    }

    roles       ||--o{ roles_permisos       : "tiene"
    permisos    ||--o{ roles_permisos       : "en"
    docentes    ||--o{ docentes_permisos    : "override"
    permisos    ||--o{ docentes_permisos    : "de"
    estudiantes ||--o{ estudiantes_permisos : "override"
    permisos    ||--o{ estudiantes_permisos : "de"
```

## Notas

- **RBAC con rol derivado.** El rol de seguridad de una persona no se guarda como FK: se **deriva**.
  - `docentes`: el `rol` (cargo) determina el rol RBAC → `Profesor` = `super_admin`;
    `Ayudante` / `Colaborador` = `admin` (ver `CARGO_A_ROL` en `constants.py`).
  - `estudiantes`: siempre `usuario`.
- **`roles` / `permisos` / `roles_permisos`** definen, a nivel general y configurable, qué permisos
  tiene cada rol. `roles_permisos` es la matriz rol→permiso.
- **Overrides por usuario** (`docentes_permisos`, `estudiantes_permisos`): excepciones individuales.
  `concedido = true` **otorga** un permiso extra; `concedido = false` **revoca** uno del rol.
  Permiso efectivo = permisos del rol ∪ otorgados − revocados.
- **Autenticación propia (monolito).** `docentes` y `estudiantes` guardan `password_hash` (bcrypt) y
  se autentican por `email` + password. No hay tabla de usuarios aparte.
- **Auditoría.** `created_at` / `updated_at` en `docentes` y `estudiantes`. `created_at` usa
  `DEFAULT now()` al insertar; **`updated_at` lo setea la API** en cada update (capa `db`), sin
  trigger en la base.
- **Campos de valor fijo como `VARCHAR`** (no `ENUM`): validación en Python (`constants.py` +
  validators), por portabilidad.
  - `docentes.rol` ∈ `Profesor` | `Ayudante` | `Colaborador`
  - `roles.codigo` ∈ `super_admin` | `admin` | `usuario`
  - `permisos.codigo` con formato `recurso.accion` (ej. `docentes.gestionar`)
- **Seed**: `roles`, `permisos` y su matriz `roles_permisos`; docentes bootstrap (password
  `admin123`) y el padrón de estudiantes de la cursada (password `cambiar123`). Cambiar en el primer
  acceso.
