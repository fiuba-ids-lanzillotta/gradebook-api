-- =============================================================
--  gradebook-api :: Script DDL + seed para PostgreSQL / Supabase
-- =============================================================
--  Ejecutá este script en tu proyecto Supabase (editor SQL de
--  Supabase Studio o con psql contra la base local).
-- =============================================================

-- -------------------------------------------------------------
--  Convenciones
--
--  - Los campos de valor fijo (cargo de docente, codigos de rol y
--    de permiso) se modelan como VARCHAR y su validacion vive en la
--    capa Python (constants.py + validators), para mantener el
--    esquema portable entre motores (sin ENUM propios de Postgres).
--  - El rol RBAC de una persona se DERIVA: docente segun su cargo
--    (Profesor -> super_admin; Ayudante/Colaborador -> admin) y
--    estudiante siempre 'usuario'. Por eso las tablas de personas
--    no guardan un rol_id; el catalogo `roles` se usa para asociar
--    permisos por rol (roles_permisos).
--  - Login: el "usuario" es el email en ambos casos. Password inicial
--    de estudiantes = su padron; de docentes = Prueba123# (cambiar).
-- -------------------------------------------------------------

-- -------------------------------------------------------------
--  Esquema
--
--  created_at / updated_at: created_at lo setea la API al crear (con DEFAULT
--  now() como red de seguridad). updated_at queda NULL al crear (todavia no se
--  actualizo) y la API lo setea en cada UPDATE. No hay trigger en la base.
-- -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS roles (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo      VARCHAR(30)  NOT NULL UNIQUE,   -- super_admin | admin | usuario
    nombre      VARCHAR(50)  NOT NULL,
    descripcion VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS permisos (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo      VARCHAR(80)  NOT NULL UNIQUE,   -- recurso.accion, ej docentes.leer
    descripcion VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS roles_permisos (
    rol_id     BIGINT NOT NULL REFERENCES roles(id)    ON DELETE CASCADE,
    permiso_id BIGINT NOT NULL REFERENCES permisos(id) ON DELETE CASCADE,
    PRIMARY KEY (rol_id, permiso_id)
);

CREATE TABLE IF NOT EXISTS docentes (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    apellido      VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    rol           VARCHAR(20)  NOT NULL,          -- cargo: Profesor|Ayudante|Colaborador
    foto          VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,          -- bcrypt
    activo        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ                       -- null al crear; lo setea la API al actualizar
);

CREATE TABLE IF NOT EXISTS estudiantes (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    padron        VARCHAR(20)  NOT NULL UNIQUE,
    nombre        VARCHAR(100) NOT NULL,
    apellido      VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,          -- bcrypt
    activo        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ                       -- null al crear; lo setea la API al actualizar
);

CREATE TABLE IF NOT EXISTS docentes_permisos (
    docente_id BIGINT  NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    permiso_id BIGINT  NOT NULL REFERENCES permisos(id) ON DELETE CASCADE,
    concedido  BOOLEAN NOT NULL,                  -- true = otorga, false = revoca
    PRIMARY KEY (docente_id, permiso_id)
);

CREATE TABLE IF NOT EXISTS estudiantes_permisos (
    estudiante_id BIGINT  NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    permiso_id    BIGINT  NOT NULL REFERENCES permisos(id)    ON DELETE CASCADE,
    concedido     BOOLEAN NOT NULL,               -- true = otorga, false = revoca
    PRIMARY KEY (estudiante_id, permiso_id)
);

CREATE INDEX IF NOT EXISTS idx_roles_permisos_rol ON roles_permisos (rol_id);
CREATE INDEX IF NOT EXISTS idx_docentes_permisos_doc ON docentes_permisos (docente_id);
CREATE INDEX IF NOT EXISTS idx_estudiantes_permisos_est ON estudiantes_permisos (estudiante_id);

-- -------------------------------------------------------------
--  Seed: roles
-- -------------------------------------------------------------

INSERT INTO roles (codigo, nombre, descripcion) VALUES
    ('super_admin', 'Super Admin', 'Docente a cargo de la materia'),
    ('admin',       'Admin',       'Ayudantes y colaboradores de la catedra'),
    ('usuario',     'Usuario',     'Estudiantes')
ON CONFLICT (codigo) DO NOTHING;

-- -------------------------------------------------------------
--  Seed: permisos (catalogo de funcionalidades protegidas)
-- -------------------------------------------------------------

INSERT INTO permisos (codigo, descripcion) VALUES
    ('docentes.leer',        'Ver docentes'),
    ('docentes.gestionar',   'Alta/baja/modificacion de docentes'),
    ('estudiantes.leer',     'Ver estudiantes'),
    ('estudiantes.gestionar','Alta/baja/modificacion de estudiantes'),
    ('roles.gestionar',      'Configurar permisos por rol'),
    ('permisos.asignar',     'Asignar/revocar permisos por usuario')
ON CONFLICT (codigo) DO NOTHING;

-- -------------------------------------------------------------
--  Seed: roles_permisos (permisos por rol, a nivel general)
--
--  super_admin: todos. admin: gestion de estudiantes + lectura de docentes.
--  usuario (estudiantes): sin permisos por defecto (se otorgan por override o
--  cuando exista un recurso propio del estudiante).
-- -------------------------------------------------------------

INSERT INTO roles_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permisos p
WHERE r.codigo = 'super_admin'
ON CONFLICT DO NOTHING;

INSERT INTO roles_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r JOIN permisos p ON p.codigo IN (
    'docentes.leer', 'estudiantes.leer', 'estudiantes.gestionar'
)
WHERE r.codigo = 'admin'
ON CONFLICT DO NOTHING;

-- -------------------------------------------------------------
--  Seed: docentes (bootstrap)
--
--  Password inicial "Prueba123#" para todos los docentes. El cargo
--  determina el rol RBAC. Login con el email. Cambiar en el primer acceso.
-- -------------------------------------------------------------

INSERT INTO docentes (nombre, apellido, email, rol, foto, password_hash) VALUES
    ('Docente', 'Ejemplo', 'docente@fi.uba.ar', 'Profesor', NULL, '$2b$12$pU8tx6q5DbKuc5ejxoASIO4qoklZyFsnHX2Y6hNYZPHmCCxIiV7WS')
ON CONFLICT (email) DO NOTHING;

-- -------------------------------------------------------------
--  Seed: estudiantes (padron de la cursada)
--
--  Password inicial = su PADRON. Login con el email. Cambiar en el
--  primer acceso. Datos importados del detalle de inscripcion a cursada.
-- -------------------------------------------------------------

INSERT INTO estudiantes (padron, nombre, apellido, email, password_hash, activo) VALUES
    ('000000', 'Estudiante', 'Ejemplo', 'estudiante@fi.uba.ar', '$2b$12$pU8tx6q5DbKuc5ejxoASIO4qoklZyFsnHX2Y6hNYZPHmCCxIiV7WS', TRUE)
ON CONFLICT (padron) DO NOTHING;
