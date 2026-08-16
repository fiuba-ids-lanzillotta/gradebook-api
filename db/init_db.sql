-- =============================================================
--  gradebook-api :: Script DDL + seed para PostgreSQL / Supabase
-- =============================================================
--  Ejecutá este script en tu proyecto Supabase (editor SQL de
--  Supabase Studio o con psql contra la base local).
-- =============================================================

-- -------------------------------------------------------------
--  Esquema
--
--  `items` es el recurso de ejemplo de este proyecto base.
--  Los campos de valor fijo se validan en la capa Python
--  (constants.py + validators), para mantener el esquema
--  portable entre motores (sin ENUM propios de Postgres).
--
--  No hay tabla de usuarios: el único usuario de administración
--  se configura por variables de entorno (ADMIN_USER / ADMIN_PASSWORD).
-- -------------------------------------------------------------

CREATE TABLE IF NOT EXISTS items (
    id          BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(500),
    activo      BOOLEAN      NOT NULL DEFAULT TRUE
);

-- -------------------------------------------------------------
--  Seed: items de ejemplo
-- -------------------------------------------------------------

INSERT INTO items (nombre, descripcion, activo) VALUES
    ('Primer item',  'Item de ejemplo activo',      TRUE),
    ('Segundo item', 'Otro item de ejemplo',        TRUE),
    ('Item inactivo', 'Item de ejemplo desactivado', FALSE)
ON CONFLICT (nombre) DO NOTHING;
