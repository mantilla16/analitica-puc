-- =====================================================================
-- EQUIPO DEL ENCARGO
--
-- Hasta aqui un encargo tenia DOS campos de usuario:
--
--   · creado_por     -- id del usuario, lo usamos para el acceso.
--   · responsable    -- texto, lo que aparece en el papel.
--
-- Y el acceso era 1-a-1: solo lo ve creado_por (ademas de los ADMIN).
-- En equipos reales un encargo lo trabajan varias personas: el senior
-- firma, un semi-senior ejecuta pruebas, un junior sube archivos y
-- hace observaciones. Si solo el senior ve el encargo, cada subida
-- obliga a compartir pantalla, y el papel pierde trazabilidad de QUIEN
-- hizo cada movimiento.
--
-- Esta migracion crea core.encargo_asignado como tabla puente:
--
--   · (encargo_id, usuario_id) es la PK.
--   · `rol` deja declarar la figura: 'responsable', 'auditor', 'revisor'.
--     No cambia permisos ahora -- todos ven y editan igual -- pero
--     queda registrado para el papel y para una siguiente iteracion
--     que divida permisos por rol.
--   · ON DELETE CASCADE desde las dos tablas: si se borra un usuario
--     o un encargo, la relacion se cae sin quedar basura.
--
-- IMPORTANTE: creado_por SE MANTIENE. Es quien abrio el encargo (dato
-- auditable) y quien firma por defecto el papel. La tabla nueva es
-- COMPLEMENTO: amplia el acceso, no reemplaza la relacion original.
--
-- Al aplicarla se SIEMBRAN los existentes: cada encargo activo gana
-- una fila (encargo_id, creado_por, rol='responsable'). Asi al dia
-- siguiente el acceso de todos sigue identico; a partir de ahi los
-- auditores pueden sumar colegas al equipo desde la UI.
--
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 21_equipo_del_encargo.sql
-- =====================================================================

\encoding UTF8
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS core.encargo_asignado (
    encargo_id  uuid        NOT NULL REFERENCES core.encargo(id) ON DELETE CASCADE,
    usuario_id  uuid        NOT NULL REFERENCES core.usuario(id) ON DELETE CASCADE,
    rol         text        NOT NULL DEFAULT 'auditor'
        CHECK (rol IN ('responsable','auditor','revisor')),
    asignado_en timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (encargo_id, usuario_id)
);

CREATE INDEX IF NOT EXISTS ix_encargo_asignado_usuario
    ON core.encargo_asignado (usuario_id);

COMMENT ON TABLE core.encargo_asignado IS
  'Equipo del encargo. Da acceso a cada usuario asignado -- en adicion '
  'al creado_por original. El rol es declarativo (responsable/auditor/'
  'revisor) y sirve de documentacion; los permisos no se dividen por '
  'rol en esta iteracion.';

-- Siembra: cada encargo gana al menos a su creador como 'responsable'.
-- Asi la primera vez que esto aplica, nadie pierde acceso. Si en el
-- futuro se cambia la responsabilidad desde la UI, el rol se actualiza
-- -- no se dejan dos responsables en silencio.
INSERT INTO core.encargo_asignado (encargo_id, usuario_id, rol)
SELECT e.id, e.creado_por, 'responsable'
FROM core.encargo e
WHERE e.creado_por IS NOT NULL
ON CONFLICT DO NOTHING;

COMMIT;
