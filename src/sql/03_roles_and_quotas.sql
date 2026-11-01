-- FixIT_ArquiComp — src/sql/03_roles_and_quotas.sql
-- SCB-1001 — T-04: U3.T3.S3 (cuotas de espacio por usuario) y U3.T3.S5
--   (creacion y verificacion de roles RBAC).
--
-- Credenciales: placeholders de laboratorio (mismo criterio que el seed
-- original de taller_prototipo.db con admin123/tec123). Rotar con
-- ALTER ROLE ... PASSWORD '...' antes de cualquier despliegue real.

-- =====================================================================
-- 1. Roles de privilegios (NOLOGIN) — RBAC
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_dba') THEN
        CREATE ROLE rol_dba NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_tecnico') THEN
        CREATE ROLE rol_tecnico NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_recepcion') THEN
        CREATE ROLE rol_recepcion NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_auditor') THEN
        CREATE ROLE rol_auditor NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_replicacion') THEN
        CREATE ROLE rol_replicacion NOLOGIN;
    END IF;
END $$;

-- =====================================================================
-- 2. Usuarios de login y asignacion de rol (RBAC)
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_sys') THEN
        CREATE ROLE admin_sys LOGIN SUPERUSER CREATEDB CREATEROLE
            PASSWORD 'Admin_SCB1001!';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_tecnico') THEN
        CREATE ROLE app_tecnico LOGIN PASSWORD 'Tecnico_SCB1001!';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_recepcion') THEN
        CREATE ROLE app_recepcion LOGIN PASSWORD 'Recepcion_SCB1001!';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_auditor') THEN
        CREATE ROLE app_auditor LOGIN PASSWORD 'Auditor_SCB1001!';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'replicator') THEN
        CREATE ROLE replicator LOGIN REPLICATION PASSWORD 'Replicator_SCB1001!';
    END IF;
END $$;

GRANT rol_dba         TO admin_sys;
GRANT rol_tecnico      TO app_tecnico;
GRANT rol_recepcion    TO app_recepcion;
GRANT rol_auditor      TO app_auditor;
GRANT rol_replicacion  TO replicator;

ALTER ROLE app_auditor SET default_transaction_read_only = on;

-- =====================================================================
-- 3. Privilegios por rol sobre los objetos de FixIT (database.py)
-- =====================================================================

GRANT USAGE ON SCHEMA public TO rol_dba, rol_tecnico, rol_recepcion, rol_auditor;

-- rol_tecnico: catalogos de solo lectura + flujo de tickets/refacciones.
-- Sin DELETE y sin acceso a payments ni audit_logs.
GRANT SELECT ON branches, customers, customer_devices, vendors, knowledge_base, inventory
    TO rol_tecnico;
GRANT INSERT, UPDATE ON tickets, ticket_parts TO rol_tecnico;
GRANT UPDATE (stock) ON inventory TO rol_tecnico;

-- rol_recepcion: atencion a clientes, equipos, tickets y cobro de pagos.
-- Sin DELETE.
GRANT SELECT ON branches, inventory TO rol_recepcion;
GRANT SELECT, INSERT, UPDATE ON customers, customer_devices, tickets TO rol_recepcion;
GRANT SELECT, INSERT ON payments TO rol_recepcion;

-- rol_auditor: solo lectura sobre auditoria y vistas de monitoreo del SGBD.
GRANT SELECT ON audit_logs TO rol_auditor;
GRANT pg_read_all_stats TO rol_auditor;

-- =====================================================================
-- 4. Cuotas de espacio en disco por rol (user_disk_quotas)
-- =====================================================================

CREATE TABLE user_disk_quotas (
    role_name   VARCHAR(50)  PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    max_bytes   BIGINT       NOT NULL,
    used_bytes  BIGINT       NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
) TABLESPACE ts_auditoria;

INSERT INTO user_disk_quotas (role_name, max_bytes) VALUES
    ('app_tecnico',    52428800),   -- 50 MB
    ('app_recepcion',  104857600),  -- 100 MB
    ('app_auditor',    0)           -- Solo lectura, sin escritura permitida
ON CONFLICT (role_name) DO NOTHING;

GRANT SELECT ON user_disk_quotas TO rol_dba, rol_auditor;

-- =====================================================================
-- 5. Trigger PL/pgSQL de cumplimiento de cuota (trg_enforce_user_quota)
-- =====================================================================

CREATE OR REPLACE FUNCTION trg_enforce_user_quota()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_quota      user_disk_quotas%ROWTYPE;
    v_row_bytes  BIGINT;
BEGIN
    -- NOTA: esta funcion es SECURITY DEFINER, por lo que current_user
    -- resolveria al DUEÑO de la funcion (postgres) y no al rol que
    -- realmente ejecuta el INSERT. Se usa session_user para identificar
    -- siempre al rol conectado (app_tecnico, app_recepcion, etc.).

    -- admin_sys y cualquier superusuario quedan exentos de cuota.
    IF (SELECT rolsuper FROM pg_roles WHERE rolname = session_user) THEN
        RETURN NEW;
    END IF;

    SELECT * INTO v_quota FROM user_disk_quotas
        WHERE role_name = session_user FOR UPDATE;

    IF NOT FOUND THEN
        -- Rol sin cuota definida: sin restriccion de espacio.
        RETURN NEW;
    END IF;

    v_row_bytes := pg_column_size(NEW);

    IF (v_quota.used_bytes + v_row_bytes) > v_quota.max_bytes THEN
        RAISE EXCEPTION 'Cuota de espacio en disco excedida para el rol %: % de % bytes permitidos',
            session_user, v_quota.used_bytes, v_quota.max_bytes;
    END IF;

    UPDATE user_disk_quotas
        SET used_bytes = used_bytes + v_row_bytes,
            updated_at = now()
        WHERE role_name = session_user;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_quota_tickets
    BEFORE INSERT ON tickets
    FOR EACH ROW EXECUTE FUNCTION trg_enforce_user_quota();

CREATE TRIGGER trg_quota_ticket_parts
    BEFORE INSERT ON ticket_parts
    FOR EACH ROW EXECUTE FUNCTION trg_enforce_user_quota();

CREATE TRIGGER trg_quota_customers
    BEFORE INSERT ON customers
    FOR EACH ROW EXECUTE FUNCTION trg_enforce_user_quota();

CREATE TRIGGER trg_quota_customer_devices
    BEFORE INSERT ON customer_devices
    FOR EACH ROW EXECUTE FUNCTION trg_enforce_user_quota();

CREATE TRIGGER trg_quota_payments
    BEFORE INSERT ON payments
    FOR EACH ROW EXECUTE FUNCTION trg_enforce_user_quota();
