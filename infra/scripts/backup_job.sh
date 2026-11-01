#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/backup_job.sh
# SCB-1001 — T-09: U5.T5.S3 — Respaldo logico (pg_dump) y fisico
# (pg_basebackup) de fixit_pg_master. Practica 7. RNF-08.
#
# Ejecutado directamente desde el host (pg_dump/pg_basebackup conectan por
# red al puerto publicado 5432), sin contenedores auxiliares.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
export PGPASSWORD="Admin_SCB1001!"

echo "== Respaldo logico (pg_dump, formato custom) =="
pg_dump -h localhost -p 5432 -U admin_sys -d fixit_db -F c \
  -f "$BACKUP_DIR/fixit_db_logical_$TS.dump"
echo "[OK] $BACKUP_DIR/fixit_db_logical_$TS.dump"

echo ""
echo "== Respaldo fisico (pg_basebackup: pgdata + 4 tablespaces) =="
PHYS_DIR="$BACKUP_DIR/basebackup_$TS"
mkdir -p "$PHYS_DIR"
# pg_basebackup requiere una conexion tipo "replication"; pg_hba.conf solo
# la autoriza para el rol replicator (admin_sys solo tiene acceso normal).
PGPASSWORD="Replicator_SCB1001!" pg_basebackup -h localhost -p 5432 -U replicator \
  -D "$PHYS_DIR/base" \
  -T "/var/lib/postgresql/tablespaces/ts_catalogos=$PHYS_DIR/ts_catalogos" \
  -T "/var/lib/postgresql/tablespaces/ts_transaccional=$PHYS_DIR/ts_transaccional" \
  -T "/var/lib/postgresql/tablespaces/ts_auditoria=$PHYS_DIR/ts_auditoria" \
  -T "/var/lib/postgresql/tablespaces/ts_indices=$PHYS_DIR/ts_indices" \
  -X stream --checkpoint=fast -P -v

echo ""
echo "== Empaquetando respaldo fisico en .tar.gz =="
tar czf "$BACKUP_DIR/basebackup_$TS.tar.gz" -C "$BACKUP_DIR" "basebackup_$TS"
rm -rf "$PHYS_DIR"
echo "[OK] $BACKUP_DIR/basebackup_$TS.tar.gz"

date "+%Y-%m-%d %H:%M:%S" > "$BACKUP_DIR/.last_backup_timestamp"

echo ""
echo "== Contenido de backups/ =="
ls -la "$BACKUP_DIR"
