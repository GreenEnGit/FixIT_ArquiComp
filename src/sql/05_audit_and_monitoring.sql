-- FixIT_ArquiComp — src/sql/05_audit_and_monitoring.sql
-- SCB-1001 — T-10: U6.T6.S1 (monitoreo con pg_stat_statements) y U6.T6.S2
-- (auditoria dinamica JSONB sobre tablas criticas). Practicas 10 y 11.

-- =====================================================================
-- 1. Monitoreo del rendimiento (RNF-09)
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
GRANT SELECT ON pg_stat_statements TO rol_auditor, rol_dba;

-- =====================================================================
-- 2. Auditoria dinamica JSONB sobre tablas criticas (RNF-10)
-- =====================================================================

ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS old_data JSONB;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS new_data JSONB;

-- Trigger generico: audita INSERT/UPDATE/DELETE de cualquier tabla a la
-- que se adjunte, capturando la fila anterior/nueva completa en JSONB.
-- Complementa (no reemplaza) los registros de negocio que la app ya
-- inserta explicitamente en audit_logs (VENTA_DIRECTA, MERMA, etc.) con
-- una pista tecnica de bajo nivel distinguible por el prefijo TRIGGER_.
CREATE OR REPLACE FUNCTION trg_audit_dml()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_row     JSONB;
    v_branch  VARCHAR(20);
BEGIN
    v_row := to_jsonb(CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END);
    v_branch := v_row ->> 'branch_id';

    -- payments no tiene branch_id propio: se deriva via ticket_id.
    IF v_branch IS NULL AND v_row ->> 'ticket_id' IS NOT NULL THEN
        SELECT branch_id INTO v_branch FROM tickets WHERE id = (v_row ->> 'ticket_id');
    END IF;

    INSERT INTO audit_logs (username, action, item_id, details, monetary_impact, date, branch_id, old_data, new_data)
    VALUES (
        session_user,
        'TRIGGER_' || TG_OP,
        v_row ->> 'id',
        format('Auditoria automatica de %s sobre %s', TG_OP, TG_TABLE_NAME),
        0.00,
        now(),
        COALESCE(v_branch, 'NORTE'),
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) END
    );

    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER trg_audit_payments
    AFTER INSERT OR UPDATE OR DELETE ON payments
    FOR EACH ROW EXECUTE FUNCTION trg_audit_dml();

CREATE TRIGGER trg_audit_tickets
    AFTER INSERT OR UPDATE OR DELETE ON tickets
    FOR EACH ROW EXECUTE FUNCTION trg_audit_dml();

CREATE TRIGGER trg_audit_inventory
    AFTER INSERT OR UPDATE OR DELETE ON inventory
    FOR EACH ROW EXECUTE FUNCTION trg_audit_dml();
