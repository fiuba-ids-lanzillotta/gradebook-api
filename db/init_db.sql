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
    ('cursadas.leer',        'Ver cursos/cursadas'),
    ('asistencias.leer',     'Ver la asistencia de una clase'),
    ('asistencias.gestionar','Tomar asistencia: generar QRs, enviar, marcar y cerrar'),
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
    'docentes.leer', 'estudiantes.leer', 'estudiantes.gestionar', 'cursadas.leer',
    'asistencias.leer', 'asistencias.gestionar'
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
    ('Bruno', 'Lanzillotta', 'blanzillotta@fi.uba.ar', 'Profesor', NULL, '$2b$12$Hry1Yv.Yu53Xy5ptu2JhpenflPNGDh3ZUMsMCWC28CInb6gQGxe4S'),
    ('Leonel', 'Chaves', 'lchaves@fi.uba.ar', 'Ayudante', NULL, '$2b$12$UYa5WCVXP/lepQuWZqrCV.30dsA.9MLWfP6NAVYDNNSLSBw1Q3eSu'),
    ('Valentina', 'Grobly', 'vgrobly@fi.uba.ar', 'Colaborador', NULL, '$2b$12$GRl/iYaMBahli5tEGMP38OXzJQiSyybqeePF83MzqxIvrz23agAv.')
ON CONFLICT (email) DO NOTHING;

-- -------------------------------------------------------------
--  Seed: estudiantes (padron de la cursada)
--
--  Password inicial = su PADRON. Login con el email. Cambiar en el
--  primer acceso. Datos importados del detalle de inscripcion a cursada.
-- -------------------------------------------------------------

INSERT INTO estudiantes (padron, nombre, apellido, email, password_hash, activo) VALUES
    ('115494', 'IAN EZEQUIEL', 'ACOSTA', 'acostaian7030@gmail.com', '$2b$12$lHMUDKCJvdAcdZJIE6/FIudwoyx6aacMcg080bnmZKAK7YRVOCVbe', TRUE),
    ('104675', 'JOSE ALEJANDRO', 'ADRIAN LOZANO', 'jadrian@fi.uba.ar', '$2b$12$HewQnML/5krHBWAwvQB0yekb0OQdlHGl5ny5TIILrn0kKdZJkIjbS', TRUE),
    ('116530', 'EZEQUIEL TOMÁS', 'AFARIAN', 'ezequielafarian@gmail.com', '$2b$12$7s84Y9TUCCwJQmdEhvXZoOgQx0btAT6Hg3j7Xz5JM8a/pA5mY2sea', TRUE),
    ('116367', 'NOELIA MILAGROS', 'AGUILAR SORAIDE', 'noeliaaguilar081@gmail.com', '$2b$12$wMKGYt4MX72dgqmEO5Cvuu8rLwbMxy6r8dyeAwpayd.UTq6YtEI/6', TRUE),
    ('116126', 'FACUNDO DAMIÁN', 'AIZINAS', 'aizin.facundo@gmail.com', '$2b$12$vPhMiKRU/N/fOa/asiuLDejRpj.1sXF41lDyLiG.Aqi4zvIP3sq1i', TRUE),
    ('116268', 'FEDERICO', 'ALBARRACIN', 'federicoalb1570@gmail.com', '$2b$12$nWisc.EvXh7oVxdLTJSMrOeq9kQV2qlG8MmgnDuMDMLLhb5Wm1soe', TRUE),
    ('116217', 'FABRIZIO NAHUEL', 'AMADO', 'fabrizio.nahuel.amado@gmail.com', '$2b$12$4rXrkL6IJtxD6X2w45TrXutg1d/odxCOjJ0tb/wBgpJ2C6rlHnmau', TRUE),
    ('115665', 'GASTON ARIEL', 'AMENTA', 'gasty.amenta.et26@gmail.com', '$2b$12$wVzkiQpbA2c2bReNa1Q2o.pueaAmVnntrbYdQ97yvk0rr9owj.xIu', TRUE),
    ('115335', 'ADDERLY ARMANDO', 'ANAYA CUCHULA', 'adderlyarmando@gmail.com', '$2b$12$qg2vxkEbdSS2R/3zSimOL.xI0s29pmS..XKpwr5mRDK2yfPG4d0la', TRUE),
    ('116024', 'SANTINO NICOLÁS', 'ANDREATTA', 'santinoandreatta@gmail.com', '$2b$12$1FlS3rBJ6ziV3fF2/5rfCuXP7Dow9RKEyznWvkpIQvX0cWUBAHZHS', TRUE),
    ('116519', 'SANTIAGO MATIAS', 'ANDREJIN', 'smandrejin@gmail.com', '$2b$12$kk3nLkIUtVCxV8VsN1.XcucG87YB8/vFYE/wRyLhCJ0WYXhjsgA5G', TRUE),
    ('107047', 'IVAN', 'ANGULO FARIAS', 'iaf.arg@hotmail.com', '$2b$12$3QVGS537HbfvCaWDaX3fG.MgJo9kWPMGKX75W1EdlxQUqy1OZ3AbC', TRUE),
    ('116512', 'RODRIGO RAMIRO', 'APAZA VENTURA', 'rodrigo.apazaventur@gmail.com', '$2b$12$LUQDI7LSzzzPzEH6e14k0uYZ17qUnpRpWzRombK9iHSfjlGpD9sci', TRUE),
    ('115221', 'IVAN RUDDY', 'ARACENA CHOQUE', 'ivanaracena18@gmail.com', '$2b$12$xUfC0M/.gYO80cOXkU9JxuQGa5N2sJ1l3/0k/Yvtb1iUufsSm3Wm.', TRUE),
    ('116052', 'IGNACIO', 'ARANCIBIA', 'nachoarancibia06@gmail.com', '$2b$12$uITc1MutA0m5u5OHR.d0kehBPxgGxrOjfS.KKupDOeQeapKH7Hpp2', TRUE),
    ('115518', 'NICOLE', 'ARROYO', 'emiarroyo40@gmail.com', '$2b$12$8abtQAcilQUe3D.ipIw65.nzuelDjv39SMp53TIoHV9WMfXPlrKaG', TRUE),
    ('100964', 'HANS JUNIOR', 'ASPAJO POQUIS', 'hansaspajo@gmail.com', '$2b$12$2ZCwlit8U8ncIyru.ni7ieGuXqwjfHfNC39oWoLjNsD.mwWbWhAI2', TRUE),
    ('114565', 'ALVARO RICARDO', 'AVALOS AGUILAR', 'aavalos@fi.uba.ar', '$2b$12$oBM7cJiNTbAoBasod45qquGOgjDD0U8MHYVt9xAMf2xXpvJKIeamq', TRUE),
    ('115442', 'TADEO', 'BAGNATO', 'tadeobag77@gmail.com', '$2b$12$NMKK8JHTqlWD5iCuAb2BCuI54/YoNKKohWfXsCbr88wMjKkuZ7lYy', TRUE),
    ('114791', 'FRANK DIEGO', 'BARBARAN PEREZ', 'frankfdbp@gmail.com', '$2b$12$PnIAOfJ6NvAQplTndXsog.heiiJa7PVPo9QG0XmD1o2d.lw0ZnsOG', TRUE),
    ('116066', 'ALI', 'BARIEGO MAGGIORINI', 'sofiaalejandrabariego@gmail.com', '$2b$12$C90dOH6B2zphcqBoP3C4SOkbV.np.YRlzS8o2IOEwpRafsKi36Wii', TRUE),
    ('115842', 'GASTÓN ALEJANDRO', 'BARRERA LEMARCHAND', 'gastonalebarrera789@gmail.com', '$2b$12$nqD.HA/0y7EDXVFV55WYj.HHSJpTgJWQ3iQ6a4JFfh50is7wbP8Vy', TRUE),
    ('116050', 'FIAMMA BELEN', 'BARRETO', 'fiammii317@gmail.com', '$2b$12$l61.blcGIG2B9Bvwdz1ZNuihvd0CCcZFGbkSBz2uSmh2wqOL/Hv.a', TRUE),
    ('116141', 'TIAGO', 'BECERRA AMENOS', 'becerramenostiago@gmail.com', '$2b$12$8yVVDU63wQkeXsKHaabAmOMB8ZBsAEme4OoNt9eJM7xLRFt1cVOMG', TRUE),
    ('112391', 'ALEJANDRA', 'BEJARANO MUÑOZ', 'alejandrabej29@gmail.com', '$2b$12$c2/.3Djh6.9Ink.x3JXJyunF/oFQuMJYYOgxB3CNabBX9qSNoxzpy', TRUE),
    ('116044', 'VICTORIA', 'BENAVIDEZ', 'benavidezvictoria9@gmail.com', '$2b$12$zVNSs6ZcLcIzp5ACFM/cheOcgZyxu6cwK97.m8vPHC0X01cRG09T6', TRUE),
    ('116303', 'JORGE RAFAEL', 'BENCOMO NAVAS', 'bencomonavasjr@gmail.com', '$2b$12$83i2rCNwvYmy.7k87YJafOX9rVrzCKf5Cp9k/gbz4Firr2WtagoSu', TRUE),
    ('114031', 'ALEX NICOLAS', 'BENITEZ OLMEDO', 'abenitezo@fi.uba.ar', '$2b$12$aTIavT8U5X.nMITTWsm0iOhi1JFBq5ZUKS1h.BPGrODACrpwn8fJS', TRUE),
    ('116500', 'LEONEL HERNAN', 'BERMAN TOLEDO', 'leonelberman7@gmail.com', '$2b$12$Z5vQe7auuHWHwDM38yXfo.kXyoAYubHKDiSI8ncC.dTND/pDxk.A2', TRUE),
    ('116175', 'JOAQUIN', 'BERZUNCES', 'berzusjoako@gmail.com', '$2b$12$Eoa4nQhzBNdlwqjpQjzk4O9s9BL6dwmKdTpI4Ww7.hC9NPzGDPp5.', TRUE),
    ('116155', 'JOAQUIN', 'BLANDINO', 'joaquinblandino@gmail.com', '$2b$12$vtoOrbSL23LKB/V8GHuF6ebjn3NO51j9Uw88yScZBcQ7crzpvTEgq', TRUE),
    ('115977', 'ALEXIS MARTIN', 'BLAZEK', 'alexistecno79@gmail.com', '$2b$12$fVsapGpYNmwfIEMGlkkN5OB.KCo..8SH2P7LGO/eXzCzanrkOUrIy', TRUE),
    ('113958', 'MILAGROS LUCIA', 'BORGSTRAND PINTOS', 'borgstrandmili@gmail.com', '$2b$12$fMXrCEFIJbiQR0B7zyDBIeKTpRyLqpXJfV7VtM1/ZUAyKuK/V5Sme', TRUE),
    ('110975', 'Gonzalo', 'BRAVO', 'gonzaloleonardo2002@gmail.com', '$2b$12$nzeqgvMy7agUP2ICDd8SDeA9a7DQZ2P4PsQ/ghn.3JEXhpqdqLnyS', TRUE),
    ('116277', 'LISANDRO SEBASTIÁN', 'BRIGNOLI RODRIGUEZ', 'lisandrobrignoli21@gmail.com', '$2b$12$bFr32qoTGcFKXv1XqBbSrOFMNvYny3lCGUuuXHP1HYfQv4UntWakq', TRUE),
    ('115714', 'JUAN PABLO', 'BRUZONE', 'ujuanpbruzone@gmail.com', '$2b$12$BLK5RsNQMcfWYz.513Uz..exuPNb81.jREdrhLzBfcEwWS8HEJEeC', TRUE),
    ('115693', 'LUCAS BUENO', 'BUENO COLIQUEO', 'buenocoliqueolucas@gmail.com', '$2b$12$zaCgYBSyn/ANHy8EIQWqBuWwmfm1roauCUWOUfjVRYHQtTzeLrXxu', TRUE),
    ('116365', 'AGUSTINA ELIZABETH', 'BURELLI', 'agustinaeburelli@gmail.com', '$2b$12$S1mu1qN8GRrCCWD1spGNHO0yA8JLZfaeN4IhM8m5TyoRkxJbPU7q6', TRUE),
    ('115963', 'HÉCTOR', 'BUSTAMANTE', 'juniorb90513@gmail.com', '$2b$12$0TbRo4W30RKIxlk5052ZneXWrCn9t9wa2L.eiL/.I00PP/Qx7mRz2', TRUE),
    ('114347', 'AGUSTIN', 'BUTIERREZ DEBOLI', 'agustinbutierrez16@gmail.com', '$2b$12$zGbOuOHPLJIUjL1PoCtfp.B06Z.pearUR/YJsrMxRr4MGIZu2Rth.', TRUE),
    ('115967', 'THIAGO MARTIN', 'CALAMITA MAGGI', 'tcalamita@fi.uba.ar', '$2b$12$JsvzNfxHsQZ2LjGPXE7qI.NzXhCLNXUG9Ls.ip/osgyZbR8Nkm.zW', TRUE),
    ('111066', 'BRIAN MARCELO', 'CALLEJAS APAZA', 'briancallejas.bc@gmail.com', '$2b$12$EU1NFqCVAaeXoWEYk37qzej7RuRaNYCFGSEEKSaqDf/YaKCy7qexm', TRUE),
    ('115512', 'FRANCO', 'CÁMPORA', 'francocampora27@gmail.com', '$2b$12$dKs8bii78l0bisquKMUvwuMymZqg9N8Bqp40/gFdWAKqTF7cquMk.', TRUE),
    ('116419', 'JULIAN JOEL', 'CANSINO', 'jcansino@fi.uba.ar', '$2b$12$Ge6ONIcvcEmFvXmynFOkreKNRlYZu5mE79oitS9CI6wCOcDEqDPzG', TRUE),
    ('116311', 'VALENTINA', 'CARERA', 'valencarera2007@gmail.com', '$2b$12$OY5lrlkhwGvj03WZrePk9.BywBjvV1FvjOLBLyo4QaclNtCdhWq1G', TRUE),
    ('116359', 'PEDRO', 'CARREIRO ROSELLINI', 'pedrocarreirors@gmail.com', '$2b$12$P3flSkaDzFJtXTZ9TtSoluakz/kc7BYMFjWadybNfJGudd66jzzUy', TRUE),
    ('113828', 'VALENTINO', 'CARRERA', 'valencarrera010@gmail.com', '$2b$12$kiO3.ujaMfaAv/Y0ALRNuO8FpWEbW7vkgVRTiTGXlx03jOIpgKRp6', TRUE),
    ('112891', 'ELIAS GUILLERMO', 'CASARRAMONA', 'eliascasarramona@gmail.com', '$2b$12$1v.rX/1ljy/VwgzKAP/sz.WxDL9iTLY0rQepc3BY83RStl6NthRcK', TRUE),
    ('116199', 'JORGE DAVID', 'CASCO CORONEL', 'jorgecasc121@gmail.com', '$2b$12$sYx.kbe6TgmJ8LVLBEznfe87JQFNVCym2cU2TNjaMEEW5UEgPMYkK', TRUE),
    ('116588', 'MATÍAS FRANCISCO', 'CASTRO', 'matute2302@gmail.com', '$2b$12$D0d6xHWnC1lCGIFuGEDxDe/j3S8eKTtx/AxCXzpu3qD5WP32CAcry', TRUE),
    ('116234', 'SANTIAGO', 'CASTRO OXILIA', 'santi.castrooxilia@hotmail.com', '$2b$12$7PjRzNONGMMgHZ52sfRjcupyNkdVtbPcdSNeQlrOWgTqIhSS6jAKW', TRUE),
    ('108549', 'ROMMELD ISRAEL', 'CHAMORRO CUPICHAMBA', 'rchamorro@fi.uba.ar', '$2b$12$ECNeN0asHVcOiHilr9xh4u4nROWwjTVrZ7IB.f07MKUUVczIRPzUq', TRUE),
    ('115630', 'ALEXIS', 'CHARKOWY', 'alexischarkowy@gmail.com', '$2b$12$AFFJEFoLKv.ueFSaaezLeesb4FrEMh32hWv/m0a.Kwa0lhjkdzKWa', TRUE),
    ('115323', 'FACUNDO NICOLÁS', 'CHOQUE AYALA', 'juanchi6715@gmail.com', '$2b$12$LSDMc9Okli2pM2HKWhxOCe9KIh5.dB7tnJLn1VjE5JgLunsoGUYEe', TRUE),
    ('116632', 'AXEL', 'CIFUENTES MOYANO', 'acifuentes@fi.uba.ar', '$2b$12$bBSy0mD9evNGX981x34.Uu6oe1GoF0.Mx0FPTX/MqPrf161hi3PFy', TRUE),
    ('116231', 'LUCAS', 'CIRILLO BERARDI', 'lucascirilloberardi@gmail.com', '$2b$12$1QK7Y0WoJbvivHW11tdGDOSiliK1wJGLNRF50kcEc3i/eHhuMbjPi', TRUE),
    ('115962', 'ANTONELLA BETSABÉ', 'COLLANTES OLIVARES', 'antonellacollantes7@gmail.com', '$2b$12$zi15NHr6R3QXaYyCwLuAvuJfdO/rW38STcLGOy/BorUS.puuzXO9e', TRUE),
    ('112843', 'JOSE ARMANDO', 'CONDORI', 'josearmando2024uba@gmail.com', '$2b$12$9CjnOEdi1h8g9BFwnMJ.muvsQf/GEYl5wz669Li8CS2cfhQPwDw82', TRUE),
    ('113158', 'MAILIN', 'CONDORI MARIN', 'mailincondori@gmail.com', '$2b$12$4/lRCsMUBeqgN22GxO6d8OdJ3vvMp75Wkl2lqpuBsKv2mD70Iq5yu', TRUE),
    ('116104', 'CRISTY MAR', 'CONTRERAS COLMENARES', 'cristymcontrerasc@gmail.com', '$2b$12$0MvkJq.zSJsUNwoXO0S5FuSFWgbd7D08KHwOU91.Kzt.306iAOruG', TRUE),
    ('116585', 'FRANCO LEANDRO', 'CONTRERAS', 'contreras.francoet36@gmail.com', '$2b$12$EqUvo7NVnV9uOw45d.hzhOMkKY0Zer3TeNKeWrqS.mdAVkO7d9vN.', TRUE),
    ('116093', 'MILAGROS BELÉN', 'CÓRDOBA', 'mbcordoba@fi.uba.ar', '$2b$12$kQQiSIcbw3260AXJYvg5yeChzVvcSI9A8iM.lOWo7TjPQPlQ616Au', TRUE),
    ('116364', 'YOHAN RODRIGO', 'CORNEJO CAMPANA', 'yohancampana@gmail.com', '$2b$12$sueSsaZvzKV4EX/J1YgG5epkeTFDHloODA0AcV0x/E/b7BZk6gNgC', TRUE),
    ('116538', 'MARCO', 'DAFFUNCHIO', 'marcodaffunchio@gmail.com', '$2b$12$KtSzBbm5tSWoWvV5EjchwuWAHw10uM02hO/0L6g3WOmqLaVa5cp2S', TRUE),
    ('116017', 'CRISTIAN NAHUEL', 'DAGLIO', 'cdaglio@fi.uba.ar', '$2b$12$cCZcW40f4XvZL7JJfGEEn.DEzVk46Tz2pICz9nJowsy2QBaGRSfLC', TRUE),
    ('103305', 'FRANCO', 'DANERI', 'fdaneri@fi.uba.ar', '$2b$12$FUpi9UyOH90PSZId6EBtrOC2I1fuk3gaMqWCZQsXVNViGw8UPHGIa', TRUE),
    ('116068', 'SANTIAGO VICTOR', 'DAU', 'santiagodau1406@gmail.com', '$2b$12$KLHywWjCd07M41O6kHRGy.MwbjezF4c5q9TBFbKYg3j9l833i1icK', TRUE),
    ('114814', 'MATEO', 'DAWIDIUK', 'mateo.dawidiuk@gmail.com', '$2b$12$XYbzly8TaK6U1Jsk4h7xY.Bb8DpEmGagk6.ZWPSHro0ZLgXDU1LLi', TRUE),
    ('116418', 'LORENZO JAVIER', 'DECILLO', 'lorenzojdecillo@gmail.com', '$2b$12$pmiNcaPTCdn92.eOopp8/uoMcV5cLPgky7CYv//7OsJO0fpwestCy', TRUE),
    ('114870', 'MAGALÍ', 'DIB', 'magalidib15@gmail.com', '$2b$12$3Jv7CAcUmWnPkvXG1VWHpuZvofJLSULlSzl5UnLh/Jf/kOSEvYw5K', TRUE),
    ('115997', 'SANTIAGO', 'DORTA AROCENA', 'santidorta07@gmail.com', '$2b$12$HlVGw29SzYOgBMV3/35AGeE0xnwscJmSyrrxahuze.HV3BIdTgGfW', TRUE),
    ('115750', 'PABLO', 'ESTRADA CLAROS', 'pabloestradaclaros@gmail.com', '$2b$12$I7Zxqx7SJof5VreGJYtkb.uL1UI3HzMFwvLZJDa8Jl1/.WFK6XofW', TRUE),
    ('116105', 'MAXIMO EZEQUIEL', 'FEBLES BARLETA', 'maximofebles@gmail.com', '$2b$12$s0XDDJNlQP2inzmA5cUVyOZq4VVorxDIDbh2r2anNd1ckb/kJhI9C', TRUE),
    ('116037', 'GALO', 'FERNANDEZ ACHILLE', 'galofernandezachille@gmail.com', '$2b$12$iTIB5jBNsmRAmf8Na36jNOzXwm9BQWY/9LdAR6VL5DGtyB74i/OCS', TRUE),
    ('115969', 'SANTIAGO', 'FERNANDEZ BAIN', 'santiferar@gmail.com', '$2b$12$a/D00oXkEcmnuHJS2oXEq.ME0f8/ISXITgaysVLlKmwfHMoCEdcpu', TRUE),
    ('115583', 'GUADALUPE', 'FERNANDEZ', 'gf7192448@gmail.com', '$2b$12$aCUi.h2xo2WeHXmRO3yoKuBV.DNTag9J29fizos0sTiBCgxBnw0xO', TRUE),
    ('115288', 'FRANCISCO', 'FERNANDEZ MEDRANO', 'francisco.fernandez.medrano@gmail.com', '$2b$12$CBg.ZlxBZ3T9pWMYbaePJOuVPRRZeVTqKdkAdQHmKeYnhmxnKZK/S', TRUE),
    ('116296', 'FRANCO', 'FERRARIO', 'francoferrariouba@gmail.com', '$2b$12$bMWZTRpx6NY.oe/6p24Mse8FRmt/.XzQ.7F8.nR0sgtNpF.U.JPwq', TRUE),
    ('116545', 'PAULINA', 'FERRARIO', 'pauliferrario@gmail.com', '$2b$12$kJcqUz0TyW/037fiGnm94OdN0bW4NofP9xoNkvouxRcgJ.IqVdjda', TRUE),
    ('116423', 'KEVIN', 'FLORES', 'flkevin039@gmail.com', '$2b$12$3.pjg4cxi0bpaKlHwWsmUu6opgNYm.aKM03VREhuKFeMEI/yLZiYa', TRUE),
    ('114853', 'EDWIN', 'FLORES RODRIGUEZ', 'edwinfloresrodriguez05@gmail.com', '$2b$12$uSrWKK8MZRVBSK0bqIXDn.18eUEI3I3/rnWyd5kjHON0agPzfyFai', TRUE),
    ('115415', 'FEDERICO NAHUEL', 'FOLGAR', 'federico28folgar@gmail.com', '$2b$12$om64KgSVy/5.enZAVdLcTeDah0Lsi.lI9EtrMBhYlF90sPdcbNZ6C', TRUE),
    ('116520', 'BRANDON EZEQUIEL', 'FRANCO', 'brandonfranco0516@gmail.com', '$2b$12$cTtgYUCmgq7juFtlC3AxDedcM2QPOX2UjFFfuVMCKEziX55OnZt9a', TRUE),
    ('114679', 'LORENA', 'FRANCO SANDOVAL', 'lorenaandreinafslc@gmail.com', '$2b$12$YLAbv0nbgDRbGmyR4YcNf.AYAycDYAueUrTu5jaYDTE/mkeK49.ge', TRUE),
    ('107667', 'JULIO LORENZO', 'FRETES CACERES', 'juliofcaceres@gmail.com', '$2b$12$DFEVPlH3CGyRdsHaayTmWuCaVMeQP91p0CDSkzQmNY6p6K.ECY6pC', TRUE),
    ('116621', 'FACUNDO MARTIN', 'FRISA', 'facuchino06@gmail.com', '$2b$12$/9IlIdiUzxs1OseYQzLOQOwV5iCGVI6YaCjeYw8.Zk6M2DICzTNYG', TRUE),
    ('116536', 'ROCCO', 'GALIMBERTI', 'rocco.galimberti@gmail.com', '$2b$12$2ORkR8Vedhd44VpHzEgf0uwQJpNns/h5LQl/muBABIblrs..f7JSC', TRUE),
    ('116617', 'NICOLAS', 'GALIZIO', 'ngalizio@fi.uba.ar', '$2b$12$B8hi/8gvkla.Xotyyv/l1eObhT8DlCdNzEjxACb3wfGYPAmRkAze.', TRUE),
    ('108516', 'VALERIA FRANCESCA', 'GARAY REYNA', 'vgaray@fi.uba.ar', '$2b$12$ItCv1OKmRtA6dOrWBhZ9j./F1MFf4tjhHMsE/J3cu4/bHLmWmPkRi', TRUE),
    ('97564', 'DANIELA BELEN', 'GARCIA ARAUCO', 'belengarciaarauco@gmail.com', '$2b$12$prs2V2iTfPZ2pwpnnZLip.Q2GtiiT.rZfdKvqnPi5nXPrXIHrjrFS', TRUE),
    ('116133', 'JORGE FELIX', 'GARCIA SANCHEZ', 'jorgito.gsrcia999@gmail.com', '$2b$12$c.ZlLwuR8DqIM0THyVJENe5BRmcje.mzMv/aSW3cGXaU170BrCFOO', TRUE),
    ('116142', 'MATEO NAHUEL', 'GELARDI', 'mgelardi@fi.uba.ar', '$2b$12$UlowQo5Ai0ZTWGA3hXxNBezqFWdWfL7GFdto1TJeu.A7YjviWKsB2', TRUE),
    ('116401', 'TOMÁS DAMIAN', 'GENTILE', 'tomasgentile8@gmail.com', '$2b$12$.oE6ELRw5foWINhwtUw4weryMk/TmYQwcyEgihZztfZ9vyNPFSPPG', TRUE),
    ('115735', 'DANTE', 'GHISI', 'ghisidante@gmail.com', '$2b$12$IrBXTwQmYmmdjzmSlbGVYOR3sRn7K78/HUwV/qOX2l/6zw19R9IwW', TRUE),
    ('116181', 'TOMÁS', 'GIACHELLO', 'tgiachello@fi.uba.ar', '$2b$12$SYQW9z7SGWyfHytvAxLvA.qOBFdM6HzoBW.lZvOCxw/aUXJBgaE7y', TRUE),
    ('116480', 'FEDERICO NAHUEL', 'GIODA', 'giodafede@gmail.com', '$2b$12$mLTX5ZCznqlMkDq1Es1vY.zWHaTvyvRFhwcM5.pglcUjAsMLefnra', TRUE),
    ('112893', 'NAHUEL LEANDRO', 'GOMEZ', 'nlgomez@fi.uba.ar', '$2b$12$f3DUwyxuswhMoUD0vSUqCel.wt8O25ixoqlBlV92MAI/0wmXcIOx2', TRUE),
    ('112221', 'NICOLE ALISON', 'GOMEZ URIOL', 'gomezuriolnicole@gmail.com', '$2b$12$F8AP3JoAokR7h7c/1k0EfuiUF/SNC5bDvm1whh1Ycxn5BcxpPxIqu', TRUE),
    ('116042', 'LAUTARO MANUEL', 'GOMILA', 'lautaromgomila@gmail.com', '$2b$12$jA6qxz0P/kRLF2qqj0OLt.HrSva9QBU1dDFcfLIWqo.rpDwlkrhi.', TRUE),
    ('109622', 'SHADI SAMANTHA', 'GONZALES AZAÑERO', 'shadigonsalezazanero@gmail.com', '$2b$12$3O/1DZ7yiJ8fXy6/nCW2g.8f649SRGzN5bLjBCF5Xp1iNotBPR3C6', TRUE),
    ('116294', 'TIZIANA IRUPE', 'GONZALEZ', 'tizianagonzalez07@gmail.com', '$2b$12$D3UdzGli5mUVSqLXtmk6y.kBLIV541mxHU6OcqYYUi9zqNIWx6mmO', TRUE),
    ('114866', 'MATIAS JAVIER', 'GORO', 'mati.jav@hotmail.com', '$2b$12$iMCMpwzchcLimhpai2KNF.3Va8Q6GbM.IsLPFYyyMH8J.Dfs0XNaS', TRUE),
    ('115748', 'CAMILA', 'GRASSANO', 'camigrassanooo@gmail.com', '$2b$12$GaFxGqJS/14EtBng7P5ITeL3UXuLH2J6oyAg9XN3FYMxUZ6.YEgie', TRUE),
    ('116085', 'SANTIAGO ARIEL', 'GUTIERREZ ALVAREZ', 'santigutal@gmail.com', '$2b$12$/0qaIrPRXWk0va4Q9fKGkufaac/EjCHpivyFFfInc9/hcMZFKwv1S', TRUE),
    ('113938', 'CRISTIAN EMANUEL', 'GUTIERREZ HUAYHUA', 'cristianema003@gmail.com', '$2b$12$aF5jaiLqtaaq3S9QTamdsucBx2kIg5NamBI0Ed0/5CKE4y4KvJT66', TRUE),
    ('114935', 'MAXIMILIANO TOMAS', 'GUTIERREZ', 'maxigutierrez419@gmail.com', '$2b$12$3MmAEsw0.kQ0feSmJBj06.oX8jlmJFxDbfeXH57BUSjimckfpSfr2', TRUE),
    ('115427', 'FABIAN ANTONIO', 'HERNANDEZ DE SANCTIS', 'fabihernandds@gmail.com', '$2b$12$lgbizxpmY9pcr2wNssjlS./Lg3c6Xo8gPkuzQK5th6hlfsjuNu9BS', TRUE),
    ('116281', 'LUCÍA', 'HERNÁNDEZ TAMAGNO', 'lhernandezt@fi.uba.ar', '$2b$12$GVSKaDfnP9UmPBcqSdu1Xux5scGg/YQFi.flhuz.mFLqvmecOG4x2', TRUE),
    ('116079', 'SOFÍA', 'HE', 'sofiahe1213@gmail.com', '$2b$12$icLkl2y8PbvJ6C6/4xiRhOnISMhgCCgexZq3smeWCxAhe8n41dPfa', TRUE),
    ('113778', 'YANINA', 'HIDALGO GONZALEZ', 'hidalgoyanina07@gmail.com', '$2b$12$fRGGaIUyMtWitks960ebL.sTlaJEX2F/FXvwH11Fq5Pna04Iykvuq', TRUE),
    ('116106', 'GÜNTER', 'HOCHBAUM ESPEJO', 'gunterhochbaum@gmail.com', '$2b$12$/YJuwkAqwIO4okFa/1.Q0.bmqrv2VJDXSINQsJh0Ve8M0O5rruOUO', TRUE),
    ('116144', 'NICOLAS ANTONIO', 'IBAÑEZ COMAN', 'nicoantoiba04@gmail.com', '$2b$12$1hHFV7K6bz8UufDZqgmAGu5.DNtcq4/JQIdKD22WTjws31PZemlPe', TRUE),
    ('115219', 'LARA SOFIA', 'INCA', 'sofia.inca9@gmail.com', '$2b$12$/AgymSjBuyNBxIDac.rPZO2q3H.rqVxj62WqiCkkcqZCRxCKhgh8u', TRUE),
    ('116196', 'SANTIAGO AMIN', 'JALUF MEMMEL', 'sjaluf@fi.uba.ar', '$2b$12$QnDwJXhuvGnUw9vd/vkSJuQ0M0mmvHargSs8zQ0UbaQ8aFeuP/KrS', TRUE),
    ('116526', 'ELIEL', 'CASTILLO', 'elielcas12@gmail.com', '$2b$12$VITtGLpNWKqihsskzHL8ke3Ohq3okFjFcw2VyicV5Hk4iQwQe0SA.', TRUE),
    ('103569', 'DIEGO AGUSTIN', 'JORGES', 'jorgesdiego@hotmail.com', '$2b$12$VHzXLxr7rdD14TCIvYBaKufkCcVd9Bjmb44wuuEaIa9eMWuO3yZW2', TRUE),
    ('110787', 'EVELYN PAMELA', 'JULIAN FLORES', 'jfevelyn20@gmail.com', '$2b$12$Y.ayN0XWRjIffOTcclqlTeSfs2sEcc0Bok4iyWhWIUykzAPKf3wMW', TRUE),
    ('115990', 'DAVID VACHAGAN', 'KHACHATRYAN', 'davkh10@gmail.com', '$2b$12$2TQ9J2jSdsZ9.Jfv/KDhq.jsg36HosQJvEjZkpsD69N4XyGyMAIj6', TRUE),
    ('116282', 'KIARA MICAELA', 'KOO', 'kookiki06@gmail.com', '$2b$12$fXDeTcrm.2y2cqLjfVcYsORSU.DDMjodpYdJbTPU03nl5v4TursQW', TRUE),
    ('116522', 'MAXIMO', 'KUKIOLKA', 'maximokukiolka@gmail.com', '$2b$12$DFt1LxIIlJ7yasnlulVbHeQDn6JGDrn2YN5iuFxHExeB1zUsSDCeO', TRUE),
    ('116006', 'TOMÁS MARIANO', 'KUPERMAN OLIVERA', 'kuper7ph@gmail.com', '$2b$12$QP9NThDlIuhTg1ZSXv3UtuvMHVAwdivMGAEztiodaCm.MO7Tjyg26', TRUE),
    ('116047', 'JOAQUÍN', 'LABADIE COSENTINO', 'labadiejoaco@gmail.com', '$2b$12$rvC/NR27cN/FvIDVYX4WBuZbjfMvHc2QfeoMtzlJ21/q2pKcmQ6ay', TRUE),
    ('115856', 'LEANDRO MARTIN', 'LAMBARDI', 'leandrolambardi@hotmail.com', '$2b$12$Xo9VsqPN.Gj6pM3Vd2wktOrDluD6ucILvIHbC.HMy2uPNIa7EI7bm', TRUE),
    ('106687', 'ALAN NAHUEL', 'LASTIRI', 'alanlastiri017@gmail.com', '$2b$12$K5V67uB/PVyrUEFeanto6uQv.UkHkj0qkG9gQMwSFZtaizN40JOMO', TRUE),
    ('116182', 'HUGO GABRIEL', 'LELOUTRE', 'hugoleloutre7@gmail.com', '$2b$12$2dVEspi5/mldyDPgfMUlVOOHJVtqVv9A8YhzEHgCm9L/grJ7i..ha', TRUE),
    ('116537', 'ALEXANDRA', 'LEON JESUS', 'alexandraleonje@gmail.com', '$2b$12$IzzDJ9MZBZV.MgmMZLWd3eVTfa0hwexUUdg.o6xsCaO3hl6rD3DLm', TRUE),
    ('116609', 'JOAQUIN DANIEL', 'LEON ZARATE', 'joaquin.zarate006@gmail.com', '$2b$12$JURpJWquiESKUKcYP1UaKuoC.veNRrWlioPh8k6Dkrgg5ZhbhRV5K', TRUE),
    ('116197', 'SOFIA PAULA', 'LEVIN', 'sofilevin29@gmail.com', '$2b$12$QvkNVIR4.RZtWrA3/6RKYOUzvhzqYroTEIXxXyQGdZ5VwWASQQ2XG', TRUE),
    ('116115', 'BRUNO NICOLÁS', 'LOPEZ', 'lopezbruno12319@gmail.com', '$2b$12$zMvyqNuR3C0/FhZ7MDiF3O8qu6xG.utRm7CXIb3pCslXAxYOao2OW', TRUE),
    ('114443', 'BRIAN DAVID', 'LUCERO', 'lucerobriandavid1@gmail.com', '$2b$12$rr37yGsyoWWf1m6F3L9IxOy.Ysu1x9Bo4sdQFt6ma8FoW86JAf816', TRUE),
    ('116325', 'ALEJANDRO', 'LUNA ALVAREZ', 'alejandrolunaalvarez2007@gmail.com', '$2b$12$M5yGXu5LUD.Dl9ZSgTIOr.EQWm1gt9YjziauZAbrZD74b7jOhyBRK', TRUE),
    ('116386', 'JUAN CRUZ', 'LUNA', 'juanluna020205@gmail.com', '$2b$12$Hm.DB6KTvWPbZvonN1wmsO0r0jO4bvqM5BpQNTZEndrN0WqSzkpui', TRUE),
    ('113022', 'AGUSTIN IGNACIO', 'LYNCH', 'ailynch005@gmail.com', '$2b$12$II.D/YpfH8xKMb7vXAGHdu69YYxgkGkOKwrD6bHLNHHTWY0iXcYSK', TRUE),
    ('116030', 'SOFIA ARIANA', 'MACHALEK MINGRONE', 'sofia.a.machalek@gmail.com', '$2b$12$diX2mMy7PbbsTBim7AFC5eoThqkF312jHyRmqE9i/lbD.MOVw1RdG', TRUE),
    ('113873', 'SOFÍA BELÉN', 'MACHUCA', 'smachuca@fi.uba.ar', '$2b$12$OEN22leVDcvfPk4fxdOFQe2LjEHQ1vJe/BCXBQCRIRu08bqn5f3Xy', TRUE),
    ('116623', 'DIEGO MATÍAS', 'MAHMOUD WONG', 'mhmoud.diegoet25@gmail.com', '$2b$12$gIByzwKzH1xDuMBFZdE8/.v6L7QkkpI2CAs9QhWJeNGH89gzFbeta', TRUE),
    ('108322', 'FRANCESCO MASSIMILIANO', 'MAI', 'fmai@fi.uba.ar', '$2b$12$eLczXx3Np/MYj2pZzAaUCOa4FVapNpcXSVBrcU7EzA8.cOt5R34H.', TRUE),
    ('107412', 'MANUEL', 'MALNERO ALBO', 'mmalnero@fi.uba.ar', '$2b$12$kiC9U8RCpGmJ/1Ks30x3OeWcEWiffnEXsq1ujQ/.E7gf.d7oxFKvG', TRUE),
    ('116257', 'YADIR DAYLER', 'MAMANI FLORES', 'yadir.daylermamani@gmail.com', '$2b$12$pq7yzAw8Q940y0InGXPEoOdlHN.QSnWTUrdQC8N08MgS/RowilLsa', TRUE),
    ('113839', 'ARIEL EDUARDO', 'MAMANI ROMERO', '0502eduardo@gmail.com', '$2b$12$vh74JPZ8mwJ8XvhrCvsheu5APnOpBhYrllv0VNqMo0ZtvVgzJJ2XW', TRUE),
    ('115983', 'BALTAZAR', 'MARANI', 'baltamarani@gmail.com', '$2b$12$sfl09E3.V6msFG2EY21wRezj6TT6Lm9EW3H4khxSzWbuyOntP/kQi', TRUE),
    ('113576', 'FERNANDO', 'MARAZ', 'fmaraz@fi.uba.ar', '$2b$12$v1jDf0oyjqVtPM6gxdAF8OGYzPG0gKrhQleCez6MjhuzCWowneAWa', TRUE),
    ('116255', 'FRANCISCO', 'MARTINEZ', 'fmartinez232007@gmail.com', '$2b$12$S47l5xbhvdf.xfznrdQYY.FIiU0XfaX36wSPDqMAHf3ZizD2o6oga', TRUE),
    ('116601', 'NICOLAS EZEQUIEL', 'MARTINEZ', 'nicolas.ezq.martinez21@gmail.com', '$2b$12$nMa4HevTRtzaxP26vcHz.elrXDceEvrqz.sUv0DYAiM9h.FOG4M/y', TRUE),
    ('115961', 'RAMIRO TOMAS', 'MARTINEZ', 'ramarti2003@gmail.com', '$2b$12$0mu3hqiORn5YBZA3JN9rMeLMyQRxbF0udMq6eB7kPqg0cBI/TOYwa', TRUE),
    ('115540', 'DAMIÁN AGUSTÍN', 'MARTINEZ ZAPATA', 'damianagustinmaartinez@gmail.com', '$2b$12$./enHaeSDAMr7CSBYR9VS.PHT1w7mceFHs1VoHvjIEzupXY9Gvok6', TRUE),
    ('116125', 'MATIAS', 'MATTOS', 'mattosmatias06@gmail.com', '$2b$12$sw3yqLXBDaJPCLgqLW8Yz.fg5z1fHCw2HS2xV9L/nCwcRgn4jy8Hm', TRUE),
    ('116212', 'KAREN IRENE', 'MEDINA URBANO', 'karenirene2908@gmail.com', '$2b$12$/sZ/u2u5q/MEwzgiJVjbZeWnm74iVP1X2yhP8Nd70a.TvQZBV7gJ6', TRUE),
    ('116111', 'TIAGO ELIAS', 'MELILLI', 'melilli.tiago@gmail.com', '$2b$12$F2wIoMRFKJoNFT7Wfu/vKecrxeM4EOV0jPnLUq1MAQrTbbSK9lHr.', TRUE),
    ('109670', 'FRANCA', 'MENICHETTI', 'francamenichettijuez@gmail.com', '$2b$12$ui/vwuq3EVssxnO6niRIPe3LBgl0Zz6xUi1wj8o1KtlGKPSzBBMdK', TRUE),
    ('116592', 'TOBIAS', 'MERCADER', 'tobimercader@gmail.com', '$2b$12$ajp2vdgVKRYvm3XE6aiQb.lsaMg3oKl1yM6fDgsbBtHmIzhlH3J7u', TRUE),
    ('111525', 'NICOLAS ANTONIO', 'MERLO MOREIRA', 'nmerlo@fi.uba.ar', '$2b$12$NkbSpNGmNLkhnydBHdEemulpm47Hhnyn5qala.UdTDkyhbOmKzDGW', TRUE),
    ('115947', 'VANESSA NICOLE', 'MICHUY TAPUY', 'vmichuy@fi.uba.ar', '$2b$12$vgx3wOrCu89c2jaTNad/YODV4PcrniLQcJz21lXZTMtZgMKi.ZHsa', TRUE),
    ('116118', 'MARCOS GAEL', 'MIMIZA', 'marcosmimiza@gmail.com', '$2b$12$f/crVYeRpUbcFeZBZaJpBOlNTVCveRLfYqqOWi7n9q26QdQ1xg2MS', TRUE),
    ('113926', 'IGNACIO', 'MIRANDA', 'fifaignacio.gmiranda@hotmail.com', '$2b$12$mh/AafUZ2pz4ZoN8bBeOk.Egu..qQwvXH3MPTs3ZLd.cxvIAd8gAq', TRUE),
    ('116102', 'JUAN FRANCISCO', 'MISIAC', 'juanmisiac@gmail.com', '$2b$12$QH.5V4S9i5qzEYSelNeggOjIyg0ed0.F0NqXgJMpMdxNB17aWCc7K', TRUE),
    ('114406', 'EMILIO JOSE', 'MONARD FUENTES', 'emilioelpro2005@gmail.com', '$2b$12$LAgnaxm00rVSzd9gZ9jZA.RpeGGM5VxMfyneJAPhf8QDG1JWgokoy', TRUE),
    ('116306', 'JUAN IGNACIO', 'MONSELL', 'juanimonsell@gmail.com', '$2b$12$dvkWhC87kPcViqQMcKVISe1onIJ0Ep0PnFd.G3xq9dknuzVbIOTZm', TRUE),
    ('114434', 'SMITH JUNIOR', 'MONTES SOLORZANO', 'smthmontes@gmail.com', '$2b$12$afElmVeGYfNaVo9lnBckuO78dmrz1RX9qFG7l3PSAY3fjex8sxeNq', TRUE),
    ('116356', 'MATIAS EZEQUIEL', 'MONTIEL', 'matidavila2020@gmail.com', '$2b$12$sH1ZXNuI8vp3py580s4SCeNyFvl5d5uTcO3ALzRnmEKzkeSP6IcNe', TRUE),
    ('114045', 'MAURICIO', 'MONZON PABLO', 'monzonpablomauricio@gmail.com', '$2b$12$8ajw5OOy/9.oHw7DCt2ePurnpgu2lTb/OXxsymxbSEo/BFeFXQbTy', TRUE),
    ('116373', 'LUZ MARIA', 'MORENO BENITEZ', 'lumoreno270219@gmail.com', '$2b$12$5FYW9PVtiXUjextQymNbT.4.n434mAjKB./xuSJoAyA6Ow2/mS6b2', TRUE),
    ('116327', 'MILENA', 'MOREYRA TABURET', 'milenam0603@gmail.com', '$2b$12$6bsbGZfKgrVpS55sJaR.reHBeNo9Tbj6n6j9lMDF4OvRzty/XEK1u', TRUE),
    ('105042', 'DANIEL', 'MORINIGO', 'vmorinigo@fi.uba.ar', '$2b$12$RX4xKWi5wROpwmqh7oLAFeSLdhN0I5jFp4gSWy2WH2nn8ln1qSKMa', TRUE),
    ('116351', 'FEDERICO SANTINO', 'MÜLLER TALOU', 'santinomullertalou@gmail.com', '$2b$12$ARYuBKJSQnSFojr4j50rjuXZdLhraYmoG2xPMfkQAgSAp3HldzUja', TRUE),
    ('114884', 'DAMIAN MAXIMILIANO', 'MULLET', 'mulletdamian@gmail.com', '$2b$12$wvgNamLwiqwvVAqAmDhCkeB0BnaKiTyrWDtMk9d3cJiRTCd0Jjov2', TRUE),
    ('114474', 'JULIETA', 'NÁGERA', 'julietanagera@gmail.com', '$2b$12$tdi/7YrFfqXv7MrIO2hHKuiJaRFN4qkHanq.kF8I/T.JdX6qx96/2', TRUE),
    ('113354', 'JOSEFINA', 'NAJAR GACEK', 'josefinajar06@gmail.com', '$2b$12$EOAbDYpKNDHP9ZG6.puHmeoXoLSkTFAjcgnNW/7s.UX5F2KI2Y2CG', TRUE),
    ('116032', 'DAVID JOEL', 'NARDELLI', 'dnardelli@fi.uba.ar', '$2b$12$0ML/WdGRR0lkHm00/ZBs8uF8uE3d/RcIbBwWZv.OGDCfHszEPHHXK', TRUE),
    ('115928', 'JERONIMO', 'NAVEIRA', 'jeronimonaveira30@gmail.com', '$2b$12$y0oc9awvxfoic2KhpsJS8eWgZzzezDDA5uMFdBc8rpb9otTndxUze', TRUE),
    ('109046', 'VALENTINA', 'NIETO', 'nieto_valentina02@hotmail.com', '$2b$12$X43OEtxbCFG4zC0iZsE0iedSIRwIZ1R7I40vdw2bXMHKVzeUizWIq', TRUE),
    ('113133', 'ALAN', 'NIEVES VILLAGRA', 'alan.2000.an@gmail.com', '$2b$12$Y6om0mqajh80919h/tmAuOiz1wJPhWNBcS4W5.yS2InJ1IBBNDBbO', TRUE),
    ('116318', 'PATRICIO', 'OLESEN', 'pachiolesen07@gmail.com', '$2b$12$iZ0WOY3IQ6tDsq6jG8Ei9Opyk6CFG2I//F9yLwN5T1QHH5ttS4iGC', TRUE),
    ('115743', 'BIANCA', 'OSIMANI', 'biancaosimani1@gmail.com', '$2b$12$h.nx.fRFXH.nZDBNZQnnuu6/i0M0gSp0UJ/W1G.QvfhVePj6KA5fi', TRUE),
    ('113970', 'DANIELA', 'OVAILLOS CASTRO', 'danielaovaillos@gmail.com', '$2b$12$voK6Oicl8jeDhweqii1jY.p8YnqicZCavSwAvgSLn8nOPaCRe0fXG', TRUE),
    ('116482', 'JESUS JUAN CARLOS', 'OVEJERO', 'jesusjncrls@gmail.com', '$2b$12$GY6J89bdwFbwR9vZhsUrSe5yReMgiybdTkoSDJAd0ljY73EZ75aF6', TRUE),
    ('116166', 'MATIAS ALEJANDRO', 'OZORES', 'matias.alejandro.ozores@gmail.com', '$2b$12$yv2ix1yUEreKOpjbOU8TfOajR8E9weBiGD9EoR6hvp.E0G6MXgZdq', TRUE),
    ('113940', 'GHERLIN', 'PALLASCO CALO', 'gherlinuni2002@gmail.com', '$2b$12$101s5A7bVFmRkyAsPHDBKOq73LyY4mrkuUjVd4JEndvmvKFVbZJmu', TRUE),
    ('107618', 'AGUSTIN DAMIAN', 'PANOZZO', 'apanozzo@fi.uba.ar', '$2b$12$0Nl0aM8pMPzDzEk77qJDVeShMQ96r75dowucOJ.DcgmKsWOIuMr32', TRUE),
    ('114595', 'ALBERTO', 'PAROT VARELA', 'aparot@fi.uba.ar', '$2b$12$lr4.QjirlJU2EWDCmCpM6e338WCUmWoc2MusJ.V5onKJECUlXmWza', TRUE),
    ('105695', 'GIANLUCA MIGUEL', 'PATE', 'gpate@fi.uba.ar', '$2b$12$lPgF9lrsBWoKMCXBhFpaquDBlwY7TdIZXM4R5BAXGOiEPhmyfmR5.', TRUE),
    ('116568', 'JOAQUIN', 'PATIÑO RIVAS', 'joaquinpatinorivas@gmail.com', '$2b$12$Qnwpfvm6NPGQifh2JYjBUuEQzLsicRyttlMcHpQUJQF/F7nBY04yS', TRUE),
    ('116062', 'SEBASTIÁN ALEJANDRO', 'PEÑALOZA FUENTES', 'spenaloza@fi.uba.ar', '$2b$12$9gYGLBQBbI2o/XYAOSuIK.IkvMlvKktYYn29GSaUB8g/vuqCgQDpm', TRUE),
    ('116087', 'EUGENIO', 'PENIN CAMPOS', 'eugeniopenincampos@gmail.com', '$2b$12$8cUcrC0zUzSKOk3WffWuY.3uZnT.dUJcxYI75UpjRyxupIccWJSS2', TRUE),
    ('115580', 'AGUSTIN', 'PERATA', 'agusperata@gmail.com', '$2b$12$u7wfeYnErrmzFsAuV.gC3OZp3mKB8NR.RCGNlCP0WpcWuoDUvPH5K', TRUE),
    ('115709', 'MARCELA EYELEN', 'PEREZ JUCHANI', 'marcelajuchani16@gmail.com', '$2b$12$vncPJNouaJlBmQ9s3CaQR.Gi921Qsbld/14T65CET53dhyi22J4Mu', TRUE),
    ('115810', 'ALEXIS AZRIEL', 'PIAI', 'alexispiai000@gmail.com', '$2b$12$HfdDTVJtct4mbGQWxHbOW.54c5PcylDhKjrY.QPDcVepR31KXGnhq', TRUE),
    ('116059', 'LEANDRO', 'PICCICACCO', 'lpiccicacco@fi.uba.ar', '$2b$12$eSXy4EzNd3Rse14IxkuPe.rj/MJCh1PxRDMti.yklKhvItfxSc4Fm', TRUE),
    ('114392', 'NATASHA ALISON', 'PILAPANTA CASTILLO', 'pilapanta2005@gmail.com', '$2b$12$ELq4lD8Qd8kECZ5WT5iv2eK5yvj2gjGl0zsxyL1UY.mgIbyBk9/di', TRUE),
    ('116276', 'RENZO', 'PIRIS SAPORITO', 'rpiris@fi.uba.ar', '$2b$12$KmX4VbVsSt67WACk0bFde.J4JUzLk9yFGF2JSdvCBPzZETJdjaQ6G', TRUE),
    ('116527', 'GEORGII', 'POLETAEV', 'georgii.poletaev.ar@gmail.com', '$2b$12$rRic6wct6ukohmL8ySgUzePyHwfLk50sm.YzjUfsyUgpw.s.7T77K', TRUE),
    ('116611', 'LUCIO JOAQUIN', 'POMPEI', 'pompeilucio@gmail.com', '$2b$12$noR8YAyD9PpEIyvXUrhRHegJD1xtUnsHuo4wp2bDgxsSMCSmgggAy', TRUE),
    ('116317', 'KAYL OMAR', 'PONCE ENCISO', 'omarargentina07@gmail.com', '$2b$12$8fCjOIKFAW/LmXJxv/E9aek.xuhlTm60EwXCJ3vQQ45b7vmgHlr5m', TRUE),
    ('116180', 'LAUTARO NAHUEL', 'QUINTANA', 'lautaroq3333@gmail.com', '$2b$12$QeXkSUjc5hes39TtX0D.Guert22l4zMAZgLEhmskhLGtW1zoc2UYu', TRUE),
    ('98759', 'ANDRES IGNACIO', 'QUIROZ', 'aquiroz@fi.uba.ar', '$2b$12$RS7MLXpp9GkSOfmOxJSMMeseClvl34eIQTQdGgfOlhlmN79Za8M9u', TRUE),
    ('116556', 'ROLANDO MARTIN', 'RISS', 'martinrissarg1985@gmail.com', '$2b$12$jYnSqOhIpeNZKEMdo9dVfuDIqQ36zsUvGf1m7V/Jq8wOYZ6sj2zcy', TRUE),
    ('115957', 'VALENTINA', 'RIVAROLA', 'valentina.esstt@gmail.com', '$2b$12$4nmdLM/rddUD6JE2znEDg.c46D6IxH1PF6daOzmf8maPaCuerWpD2', TRUE),
    ('116394', 'ADRIANA CAMILA', 'RODRIGUEZ CABALLERO', 'adrianarodriguezc777@gmail.com', '$2b$12$Bi5uveUKHbuUp3BxmMPEwexGaYHiImHQJYi2eR9RMUiqr/lh5WP7m', TRUE),
    ('101022', 'NIMER ABEL', 'RODRIGUEZ URO', 'nrodriguezu@fi.uba.ar', '$2b$12$K8djKRwRrvku5pC7lSHRheZ6U5Jry5GTzpcmmcf5mlp.RLl6Id.lS', TRUE),
    ('116067', 'TOMAS MATEO', 'ROLDAN', 'troldan@fi.uba.ar', '$2b$12$KpX3ofHmOg9dr1X4M4rscOVG6gZ7uz.vIsY0Qm6DKEzcyxuZSbf4.', TRUE),
    ('116313', 'SEBASTIAN MIGUEL', 'ROMERO', 'sebarom12@gmail.com', '$2b$12$Yz/IY.6D11vR/31TaqRdHOqAxlh53biZpXhdwwJYG8N4g0lcOtWLO', TRUE),
    ('116344', 'TYAGO', 'ROSSO VICH', 'tyagorosso9@gmail.com', '$2b$12$ZXZgg8inVhYlCTd11YIyiO4v3OQZ66aXngSCdSnQawJZe5m4VClO.', TRUE),
    ('115730', 'GASPAR', 'RUBBO', 'rubbogaspar@gmail.com', '$2b$12$bvjBDoPAV1QaHipz.rCl..K4kgvL3Djru9oSTDZ5E.w8DWiBQ3rQC', TRUE),
    ('114419', 'GABRIEL', 'SAAVEDRA GUTIERREZ', 'gab989363@gmail.com', '$2b$12$1.tKdnbt3HUycm.u95OzyOwveVLb8BXo4Lp7bRvo869HBG9tOlxqq', TRUE),
    ('116324', 'LUCÍA', 'SAINT MARTIN', 'lucia.st.martin@gmail.com', '$2b$12$kC4cp7b.qPFG2MHVYWpwd.X3hwzFYvBPtqLdwG00ETbryt9v7Q8l.', TRUE),
    ('116249', 'LISBET DAIANA', 'SANCHEZ SOTELO', 'lisbetsanchez006@gmail.com', '$2b$12$1wLEGEuu9OiGpXrOU4zgeeXTUgl0Gsk3TjPCs/LqMgUAOW3oPIlia', TRUE),
    ('116256', 'JAVIER MARTÍN', 'SCOPA LOPINA', 'javierscopa1@gmail.com', '$2b$12$hnMtN/iIUQesq2DmlRWPLuoJ1Tu.l6psCxKnzGBUnqaYe3k6F2Bje', TRUE),
    ('116121', 'CRISTOPHER ANDRÉS', 'SILVA CANDIA', 'cris.silva.candia@gmail.com', '$2b$12$lgQ.RaH/SXfNKVMWjXimAeR38BwHolbyc.VHMs8jgfF/al1WvrnJ.', TRUE),
    ('112048', 'FRANCO GABRIEL', 'SILVA', 'francosilva166@gmail.com', '$2b$12$vs7rzDS2kvkMFEEfK9NkUO/QjdDgpU/BKqn/EqMrqMoVYB.d0aB/O', TRUE),
    ('115666', 'MAXI', 'SILVA', 'masisilva05@gmail.com', '$2b$12$hqbrp2tJiKB.Y0hRr1gAvuM/PCgLkRZKXxT8CPahEFBCwb9nrIkoG', TRUE),
    ('116578', 'VANESSA FATIMA', 'SILVESTRE QUISPE', 'vanessafsq25@gmail.com', '$2b$12$aLNf1vNPTmulnLZh/oSLUOkujA7e3V.cSFRGDJ1KomKoQ9Wic46RS', TRUE),
    ('106935', 'MARTIN', 'SIMAJOWICH', 'msimajowich@fi.uba.ar', '$2b$12$sUiwK.qA4iELnPx9LMLx7OM7cBtJdM1/VP8mrtry7PxH1Sua2Qn6G', TRUE),
    ('116031', 'VALENTIN', 'SISKIND', 'siskindvalentin@gmail.com', '$2b$12$dqh1.WQb0mc3A0q64T08weuoR3X/NOJjqRq5iaDnzRxrMaiZhMJyW', TRUE),
    ('116128', 'JUAN FRANCISCO', 'SKANATA', 'jfskanata@gmail.com', '$2b$12$PNBh2SCwVkw.d37kJVsdS..9daT4gEWag/YeF1JQG9N7csoh91Iay', TRUE),
    ('114351', 'SARAI', 'SLAVKIS', 'saraislavkis@gmail.com', '$2b$12$rPH5otN3l5O6PSes9tK3h.n/YeLeoqMzH2sQwWyOwlNTimMWHLA0i', TRUE),
    ('116150', 'IGNACIO HIROKI', 'SOKEI', 'sokeiignacio@gmail.com', '$2b$12$9M1uoUNRjqFsHlr2dieIvubnfoS7H0Ifbz3mCkSadRb.W4KIMHMgS', TRUE),
    ('116388', 'MATÍAS DANTE', 'SOLETTA BRITEZ', 'matiassoletta1@gmail.com', '$2b$12$tnP/N6qknZ2EIPLl3uchMOvIpSGZsPh5dQ9sETJmjf0A.Fd4Sfxcq', TRUE),
    ('116467', 'BRUNO', 'SOSA SANCHEZ', 'sosabruno1995@gmail.com', '$2b$12$3MWHMElZ0X19CCzKmXR36OIeRP4sjHq5nwXhk4YzCsKcpXAFP3QPa', TRUE),
    ('116612', 'THADIER', 'STAROPOLI JEREZ', 'tstaropoli@fi.uba.ar', '$2b$12$cVRmNjtX5WujrTadKxwrlONMa6iJ5nTtR4KgbIG3kAPts76brBGNm', TRUE),
    ('116014', 'ROMINA ALEXANDRA', 'SUMEN HUAMAN', 'rominasumen332@gmail.com', '$2b$12$UOzP541lGnCrPe7RKebLruHGTNVU6jflB71ty97KGzmRDMmKMiK0S', TRUE),
    ('112500', 'JUAN PABLO', 'TACUNAN NAVARRO', 'juanpablotacunan@gmail.com', '$2b$12$RTGbMVJ2SP5BO1ENb3bko.DYC0axTUcwL2QoeWWo1NpmI2EnfIDAi', TRUE),
    ('115970', 'IGNACIO', 'THIERRY STUARDO', 'ignacioth05@gmail.com', '$2b$12$9aYwvIpbfctR.sg3BZ4nQuN5TyXjvofpbbpyh93K4hR7oi9L9yG4W', TRUE),
    ('116426', 'LEYDI', 'TICONA CALLISAYA', 'ticonaleydiet5@gmail.com', '$2b$12$JfHrbA0VTqLig2SYhIPwEOPu/hAkfp8WHnLygkiM.4SoEYnzfPdjO', TRUE),
    ('116343', 'MARCOS', 'TISSERA COLLOMPS', 'martiscol2005@gmail.com', '$2b$12$a9pxKdtwB3CgI8S.aSO7z.tx0qqoboRKMTUSmxEmC6pjog7GgsSBu', TRUE),
    ('115216', 'JOSE ANTONIO', 'TORO RIVAS', 'tororivasjoseantonio@gmail.com', '$2b$12$AL.4YHxOqAjik8MjhwKe3.AoFUN8dkaj8vsL5vTQAd0yXYec7GTvi', TRUE),
    ('116250', 'JOAQUIN', 'TRANSILLO', 'jtransillo@fi.uba.ar', '$2b$12$GDQ5E8WcqVPSTCkCNPQqHOGFd2p4UyMRRyiTf79qebpaFvK221b26', TRUE),
    ('115378', 'ALAN GUSTAVO', 'TRAVADO', 'atravado@fi.uba.ar', '$2b$12$9R9J0b4MepEtkUm8EVapUeNom0MQK1aM6ofmaFmuwUsEFrmgQRffe', TRUE),
    ('116478', 'LUCAS NAHUEL', 'URAN', 'lukitas1648@gmail.com', '$2b$12$1MlduRICcRJfNAmro1buh.v5daycYzMwLIDkQpaRxP9sj020BTxhC', TRUE),
    ('115946', 'FACUNDO MANUEL', 'URIBE ROLLANO', 'facundouribr26@gmail.com', '$2b$12$1zA.n3tXu35ovbmTrYpZy.obSNgwZOeY/KNg6FjgreLTWty7qEKKO', TRUE),
    ('116063', 'BRUNELLA', 'VALDATA', 'brunellavaldata@gmail.com', '$2b$12$c98VuoJIG78vtktCjbIwb.xjv5BbrlqZmXtHasQ5CqcA25DGnMQlK', TRUE),
    ('106191', 'NICOLÁS EZEQUIEL', 'VALENZUELA', 'nvalenzuela@fi.uba.ar', '$2b$12$dvxQzbG3eWrHoQMQ76rgM.IDCNXDtlcGEukMZhchK6Lhs5Y8.xEFS', TRUE),
    ('116004', 'MARIA EUGENIA', 'VALLEJO', 'mevallejo05@gmail.com', '$2b$12$sQmKNNq3yuwmp5mXzbTXBO73LNDyMLUWpXr4xl4o7JWAg6nDdk84W', TRUE),
    ('115887', 'FRAN', 'VARGAS LAIME', 'patulibro.98@gmail.com', '$2b$12$Gu45TKjLVThF3VktINm3mOEC108e8tPM.y8OIRDXcZojFS0kU5BI2', TRUE),
    ('116220', 'DENIS OSCAR', 'VASQUEZ MAMANI', 'denishola03@gmail.com', '$2b$12$N6HYjHrtrr7KfXXg3UWu/OQTGYah6pObP4Nh1UtqpfyKerBjf.f5y', TRUE),
    ('116323', 'KIARA YOSELYN', 'VENTURA DIAZ', 'kiarayoselynventuradiaz@gmail.com', '$2b$12$EaTEY5UstgudKhelBbWSQ.3AfPLVcmf74kh0n2rbEFOQyde3Bd6tW', TRUE),
    ('116022', 'JOAQUIN', 'VENTURA', 'venturajoaqui27@gmail.com', '$2b$12$suU2837F4VrxAO0Hr5vWxu4OZBoVdjdVyyNmLpxL.2DUszg5B6woC', TRUE),
    ('114517', 'GABRIEL DANIEL', 'VERA LLANOS', 'gdvll1234@gmail.com', '$2b$12$KpKBLg3TiU4faj9yGW.IieeNRbHppC0.PmtThq56cMuklmLxD0Pwu', TRUE),
    ('116288', 'LUCIO VALENTIN', 'VILLAGRA', 'lucio7valentin@gmail.com', '$2b$12$DAchYs2OZ8N/CfKYJamqxewfLSn2vhOlEy/Jh8Oo9TjOE5xxuynXS', TRUE),
    ('116596', 'JOSTIN JAEL', 'VILLAMAGUA ARROBO', 'jostinvillamagua08@gmail.com', '$2b$12$ieoeiemRV3oijn2XqwsRdOJoiN4eZOTqaE/oxvDgoT4YjtsDcYrlW', TRUE),
    ('115865', 'MANUEL', 'VILLAR', 'manuelvillar2007@gmail.com', '$2b$12$mUABkWjkx/sGeXEoXi.jx.W/izgpjG.pJym6soeS3BOJe6jw31/4a', TRUE),
    ('115821', 'MATEO', 'VILLEGAS', 'mateojotalo@gmail.com', '$2b$12$S0l6/kkwpFzo87nIWV854.JrOkUJY1ZqE7ihTN7rlUYkJr5ID.6Aa', TRUE),
    ('115375', 'LUCIANO', 'WENG', 'weng2250956017@gmail.com', '$2b$12$F.z3HN..WHfTzfIiHyu7M.kIrdOwKOQTiUamnIbP05POpAgMTEWry', TRUE),
    ('114725', 'NICOLAS', 'WU', 'niwu@fi.uba.ar', '$2b$12$tdvfVX3QvkyNfSvE95FHA.FcbfeGE4O9RnAJ.NN4iSJALYFRI638u', TRUE),
    ('114859', 'SOFIA', 'YANG', 'sofiayang4739@gmail.com', '$2b$12$7qd0H/BvPTLgvnkUSpD7GeTwFKLKCPP3V4Nq6zAZkNTvkJ32p5PcG', TRUE),
    ('113499', 'JUSTIN', 'YEPEZ CONCHA', 'chinoliss58@gmail.com', '$2b$12$sqQM1QUr1KSpgHdXfeFBSecnJbjTNudPuAYcRbHBd2.C6HMcTuGcS', TRUE),
    ('116532', 'DIEGO OLIVER', 'YUJRA COSSIO', 'diegooliver-18@hotmail.com', '$2b$12$Phr9mjJmRshxsYNLQ7zPJepVgAJnO9/LNd9azSiufT8nUbFD.N9cq', TRUE),
    ('113732', 'JONATHAN', 'YUNGA CARRASCO', 'yungajonathan777@gmail.com', '$2b$12$Yn5oExG19na.zb4Uaxk32OZc947wTru2w6txiESVqu3.vPGjFHAxi', TRUE),
    ('109869', 'GASTON MATIAS', 'ZALAZAR', 'zalazgaston@hotmail.com', '$2b$12$QwlcpENaf3vyJnqMjjiiN.BTL9zTI5eeocYDcnVKlbjvMHBVto4Rm', TRUE),
    ('97605', 'LUIS GERARDO', 'ZAMBRANO VERA', 'lzambrano@fi.uba.ar', '$2b$12$5qUDNegXWs15mfh3r.ive.jVvzORlp2Mc495OH0ycq7UFocLSLBgm', TRUE),
    ('102134', 'EMANUEL ALBERTO', 'ZETKA', 'ezetka@fi.uba.ar', '$2b$12$ZrE0FW/ven5Uoam4Qrbn5O5mVSLRx4How6oHjUxlgrtmSiw5wr0OK', TRUE),
    ('116474', 'MAKSIM', 'ZOTOV', 'maksim.zt8@gmail.com', '$2b$12$yD5GWzfS//x9QtkxzgoCbOm2i2wae2yPNyLsF4f/rAP8XnEabTI0e', TRUE)
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
