#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/toggle_audit.sh
# SCB-1001 — T-10: U6.T6.S2 — Activa, verifica y desactiva la auditoria
# dinamica (trg_audit_*) definida en src/sql/05_audit_and_monitoring.sql.
# Practica 10.
set -euo pipefail

CONTAINER="fixit_pg_master"
TABLES="payments tickets inventory"

psql_exec() {
  podman exec --user postgres "$CONTAINER" psql -U postgres -d fixit_db -c "$1"
}

case "${1:-}" in
  on)
    echo "== Activando auditoria dinamica =="
    for t in $TABLES; do
      psql_exec "ALTER TABLE $t ENABLE TRIGGER trg_audit_$t;"
    done
    ;;

  off)
    echo "== Desactivando auditoria dinamica =="
    for t in $TABLES; do
      psql_exec "ALTER TABLE $t DISABLE TRIGGER trg_audit_$t;"
    done
    ;;

  status)
    echo "== Estado de los triggers de auditoria =="
    psql_exec "
      SELECT c.relname AS tabla, t.tgname AS trigger,
             CASE t.tgenabled WHEN 'O' THEN 'ACTIVO' ELSE 'DESACTIVADO' END AS estado
      FROM pg_trigger t
      JOIN pg_class c ON c.oid = t.tgrelid
      WHERE t.tgname LIKE 'trg_audit_%'
      ORDER BY tabla;"
    ;;

  *)
    echo "Uso: $0 [on|off|status]"
    exit 1
    ;;
esac
