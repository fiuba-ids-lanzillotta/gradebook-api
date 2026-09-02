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
--    (Profesor -> super_admin; Ayudante -> admin; Colaborador -> superusuario) y
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
--  Dominio de cursada
--
--  materia -> cursadas (una por anio + cuatrimestre) -> inscripciones de
--  estudiantes (con estado y baja), plantel de docentes, evaluaciones y sus
--  notas. Las evaluaciones grupales arman grupos (por evaluacion) con miembros,
--  owner (estudiante) y tutor (docente, opcional), y su propia nota de grupo.
--  Valores fijos como VARCHAR validados en Python. updated_at nullable (lo setea
--  la API al actualizar).
-- -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS materias (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo      VARCHAR(20)  NOT NULL UNIQUE,
    nombre      VARCHAR(150) NOT NULL,
    descripcion VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS cursadas (
    id           BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    materia_id   BIGINT      NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    anio         SMALLINT    NOT NULL,
    cuatrimestre SMALLINT    NOT NULL,                    -- 1 | 2 (validado en Python)
    fecha_inicio DATE        NOT NULL,
    fecha_fin    DATE        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ,
    UNIQUE (materia_id, anio, cuatrimestre)
);

CREATE TABLE IF NOT EXISTS inscripciones (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cursada_id    BIGINT       NOT NULL REFERENCES cursadas(id)    ON DELETE CASCADE,
    estudiante_id BIGINT       NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    recursa       BOOLEAN      NOT NULL DEFAULT FALSE,
    estado        VARCHAR(20)  NOT NULL DEFAULT 'cursando',  -- cursando | abandono | baja
    motivo_baja   VARCHAR(500),                              -- razon (cuando estado = baja)
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,
    UNIQUE (cursada_id, estudiante_id)
);

CREATE TABLE IF NOT EXISTS cursada_docentes (
    cursada_id BIGINT      NOT NULL REFERENCES cursadas(id) ON DELETE CASCADE,
    docente_id BIGINT      NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cursada_id, docente_id)
);

CREATE TABLE IF NOT EXISTS evaluaciones (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cursada_id  BIGINT       NOT NULL REFERENCES cursadas(id) ON DELETE CASCADE,
    nombre      VARCHAR(150) NOT NULL,
    descripcion VARCHAR(500),
    tipo        VARCHAR(20)  NOT NULL,             -- obligatorio | opcional
    criterio    VARCHAR(30)  NOT NULL,             -- nota | aprobado_desaprobado | entregado_no_entregado
    peso        NUMERIC(6,2) NOT NULL DEFAULT 0,   -- influye en el promedio
    modalidad   VARCHAR(20)  NOT NULL,             -- grupal | individual
    visibilidad VARCHAR(20)  NOT NULL,             -- habilitado | deshabilitado | sin_entrega
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS grupos (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evaluacion_id BIGINT       NOT NULL REFERENCES evaluaciones(id) ON DELETE CASCADE,
    numero        SMALLINT     NOT NULL,
    nombre        VARCHAR(150) NOT NULL,
    owner_id      BIGINT       NOT NULL REFERENCES estudiantes(id),   -- estudiante creador
    tutor_id      BIGINT                REFERENCES docentes(id),      -- opcional (puede no tener tutor)
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,
    UNIQUE (evaluacion_id, numero)
);

CREATE TABLE IF NOT EXISTS grupo_estudiantes (
    grupo_id      BIGINT      NOT NULL REFERENCES grupos(id)      ON DELETE CASCADE,
    estudiante_id BIGINT      NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (grupo_id, estudiante_id)
);

CREATE TABLE IF NOT EXISTS notas (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evaluacion_id BIGINT       NOT NULL REFERENCES evaluaciones(id) ON DELETE CASCADE,
    estudiante_id BIGINT       NOT NULL REFERENCES estudiantes(id)  ON DELETE CASCADE,
    nota          NUMERIC(5,2),                    -- criterio = nota
    estado        VARCHAR(20),                     -- aprobado|desaprobado | entregado|no_entregado
    observaciones VARCHAR(500),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,
    UNIQUE (evaluacion_id, estudiante_id)
);

CREATE TABLE IF NOT EXISTS notas_grupo (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id      BIGINT       NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    nota          NUMERIC(5,2),
    estado        VARCHAR(20),
    observaciones VARCHAR(500),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,
    UNIQUE (grupo_id)
);

CREATE INDEX IF NOT EXISTS idx_cursadas_materia ON cursadas (materia_id);
CREATE INDEX IF NOT EXISTS idx_inscripciones_cursada ON inscripciones (cursada_id);
CREATE INDEX IF NOT EXISTS idx_inscripciones_estudiante ON inscripciones (estudiante_id);
CREATE INDEX IF NOT EXISTS idx_cursada_docentes_docente ON cursada_docentes (docente_id);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_cursada ON evaluaciones (cursada_id);
CREATE INDEX IF NOT EXISTS idx_grupos_evaluacion ON grupos (evaluacion_id);
CREATE INDEX IF NOT EXISTS idx_grupo_estudiantes_estudiante ON grupo_estudiantes (estudiante_id);
CREATE INDEX IF NOT EXISTS idx_notas_evaluacion ON notas (evaluacion_id);
CREATE INDEX IF NOT EXISTS idx_notas_estudiante ON notas (estudiante_id);

-- -------------------------------------------------------------
--  Dominio de asistencia
--
--  La asistencia se toma en ciertas fechas (no todas). Cada `clase` es una fecha
--  de una cursada donde se toma asistencia; al dispararla se genera una fila de
--  `asistencias` por estudiante (inscripto + activo) con un `codigo` corto y
--  legible que va en el QR (y sirve de fallback tipeable). El estado del envio
--  del email (enviado/intentos/error) vive en la fila para que el envio por
--  lotes sea reanudable e idempotente. Valores fijos como VARCHAR (validados en
--  Python). updated_at nullable (lo setea la API).
-- -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS clases (
    id         BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cursada_id BIGINT       NOT NULL REFERENCES cursadas(id) ON DELETE CASCADE,
    fecha      DATE         NOT NULL,
    titulo     VARCHAR(150),
    estado     VARCHAR(20)  NOT NULL DEFAULT 'abierta',   -- abierta | cerrada
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    UNIQUE (cursada_id, fecha)
);

CREATE TABLE IF NOT EXISTS asistencias (
    id             BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clase_id       BIGINT       NOT NULL REFERENCES clases(id)      ON DELETE CASCADE,
    estudiante_id  BIGINT       NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    codigo         VARCHAR(16)  NOT NULL,                    -- corto/legible: QR + fallback tipeable
    estado         VARCHAR(20)  NOT NULL DEFAULT 'pendiente',-- pendiente | presente | ausente
    metodo         VARCHAR(20),                              -- qr | manual | padron (como se marco)
    marcado_por    BIGINT                REFERENCES docentes(id),  -- docente que marco
    marcado_at     TIMESTAMPTZ,
    enviado        BOOLEAN      NOT NULL DEFAULT FALSE,       -- email con el QR enviado
    enviado_at     TIMESTAMPTZ,
    envio_intentos SMALLINT     NOT NULL DEFAULT 0,
    envio_error    VARCHAR(300),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ,
    UNIQUE (clase_id, estudiante_id),
    UNIQUE (clase_id, codigo)
);

CREATE INDEX IF NOT EXISTS idx_clases_cursada ON clases (cursada_id);
CREATE INDEX IF NOT EXISTS idx_asistencias_clase ON asistencias (clase_id);
CREATE INDEX IF NOT EXISTS idx_asistencias_estudiante ON asistencias (estudiante_id);

-- -------------------------------------------------------------
--  Seed: roles
-- -------------------------------------------------------------

INSERT INTO roles (codigo, nombre, descripcion) VALUES
    ('super_admin', 'Super Admin', 'Docente a cargo de la materia'),
    ('admin',       'Admin',       'Ayudantes de la catedra'),
    ('superusuario', 'Superusuario', 'Colaboradores de la catedra'),
    ('usuario',     'Usuario',     'Estudiantes')
ON CONFLICT (codigo) DO NOTHING;

-- -------------------------------------------------------------
--  Seed: permisos (catalogo de funcionalidades protegidas)
-- -------------------------------------------------------------

INSERT INTO permisos (codigo, descripcion) VALUES
    ('docentes.leer',        'Ver docentes'),
    ('docentes.gestionar',   'Alta/baja/modificacion de docentes'),
    ('estudiantes.leer',     'Ver estudiantes'),
    ('estudiantes.crear',    'Alta de estudiantes'),
    ('estudiantes.modificar', 'Modificacion de estudiantes'),
    ('estudiantes.eliminar', 'Baja de estudiantes'),
    ('cursadas.leer',        'Ver cursos/cursadas'),
    ('asistencias.leer',     'Ver la asistencia de una clase'),
    ('asistencias.gestionar','Tomar asistencia: generar QRs, enviar, marcar y cerrar'),
    ('notas.leer',           'Ver notas'),
    ('evaluaciones.leer',    'Ver evaluaciones'),
    ('roles.leer',           'Ver roles y catálogo de permisos'),
    ('roles.gestionar',      'Configurar permisos por rol'),
    ('permisos.asignar',     'Asignar/revocar permisos por usuario')
ON CONFLICT (codigo) DO NOTHING;

-- -------------------------------------------------------------
--  Seed: roles_permisos (permisos por rol, a nivel general)
--
--  super_admin (Profesor): TODOS los permisos
--  admin (Ayudante): Todos EXCEPTO permisos.asignar, docentes.gestionar, estudiantes.crear y roles.gestionar
--  superusuario (Colaborador): Todos EXCEPTO permisos.asignar, docentes.gestionar, estudiantes.crear, estudiantes.eliminar y roles.gestionar
--  usuario (Estudiantes): Solo lectura de asistencias, estudiantes, notas, evaluaciones
-- -------------------------------------------------------------

-- super_admin: todos los permisos
INSERT INTO roles_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permisos p
WHERE r.codigo = 'super_admin'
ON CONFLICT DO NOTHING;

-- admin (Ayudante): todos EXCEPTO permisos.asignar, docentes.gestionar, estudiantes.crear y roles.gestionar
INSERT INTO roles_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r JOIN permisos p ON p.codigo NOT IN (
    'permisos.asignar', 'docentes.gestionar', 'estudiantes.crear', 'roles.gestionar'
)
WHERE r.codigo = 'admin'
ON CONFLICT DO NOTHING;

-- superusuario (Colaborador): todos EXCEPTO permisos.asignar, docentes.gestionar, estudiantes.crear, estudiantes.eliminar y roles.gestionar
INSERT INTO roles_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r JOIN permisos p ON p.codigo NOT IN (
    'permisos.asignar', 'docentes.gestionar', 'estudiantes.crear', 'estudiantes.eliminar', 'roles.gestionar'
)
WHERE r.codigo = 'superusuario'
ON CONFLICT DO NOTHING;

-- usuario (Estudiantes): solo lectura de asistencias, estudiantes, notas, evaluaciones
INSERT INTO roles_permisos (rol_id, permiso_id)
SELECT r.id, p.id
FROM roles r JOIN permisos p ON p.codigo IN (
    'asistencias.leer', 'estudiantes.leer', 'notas.leer', 'evaluaciones.leer'
)
WHERE r.codigo = 'usuario'
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

-- -------------------------------------------------------------
--  Seed: materia y cursada de ejemplo
--
--  Punto de partida del dominio de cursada. Las inscripciones, el plantel de
--  docentes, las evaluaciones y las notas se cargan luego (por endpoints / CSV).
-- -------------------------------------------------------------

INSERT INTO materias (codigo, nombre, descripcion) VALUES
    ('TB022', 'Introducción al Desarrollo de Software', 'Materia de la catedra Lanzillotta (FIUBA)')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO cursadas (materia_id, anio, cuatrimestre, fecha_inicio, fecha_fin)
SELECT m.id, 2026, 2, DATE '2026-08-01', DATE '2026-12-15'
FROM materias m
WHERE m.codigo = 'TB022'
ON CONFLICT (materia_id, anio, cuatrimestre) DO NOTHING;

-- -------------------------------------------------------------
--  Seed: inscripciones (todo el padron sembrado a la cursada 2026-C2)
--
--  Deja a los estudiantes del seed inscriptos en la cursada de ejemplo, con
--  estado 'cursando'. En el uso real, las inscripciones las crea el alta de
--  estudiantes (POST) o el import CSV, ambos sobre la cursada vigente.
-- -------------------------------------------------------------

INSERT INTO inscripciones (cursada_id, estudiante_id, recursa, estado)
SELECT c.id, e.id, FALSE, 'cursando'
FROM cursadas c
JOIN materias m ON m.id = c.materia_id
CROSS JOIN estudiantes e
WHERE m.codigo = 'TB022' AND c.anio = 2026 AND c.cuatrimestre = 2
ON CONFLICT (cursada_id, estudiante_id) DO NOTHING;
