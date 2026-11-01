#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/setup_replication.sh
# SCB-1001 — T-08: U5.T5.S1 (espejeo) y U5.T5.S2 (replica). Practica 6.
#
# Clona fixit_pg_master hacia fixit_pg_replica (puerto 5433) via
# pg_basebackup ejecutado directamente desde el host (conecta por red al
# puerto publicado 5432; no requiere contenedores auxiliares), y levanta la
# replica como Hot Standby con Streaming Replication (slot fisico).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$INFRA_DIR/.." && pwd)"

set -a
source "$INFRA_DIR/.env"
set +a
: "${REPLICATOR_PASSWORD:?Falta REPLICATOR_PASSWORD en infra/.env}"

REPLICATOR_USER="replicator"
SLOT_NAME="fixit_replica_slot"
REPLICA_DIR="$INFRA_DIR/volumes/replica"

echo "== 1. Deteniendo/eliminando fixit_pg_replica previo (si existe) =="
podman rm -f fixit_pg_replica >/dev/null 2>&1 || true
podman exec --user postgres fixit_pg_master psql -U postgres -d fixit_db -c \
  "SELECT pg_drop_replication_slot('$SLOT_NAME') WHERE EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = '$SLOT_NAME');" >/dev/null

echo "== 2. Preparando directorios vacios de la replica (uid postgres=999) =="
podman unshare rm -rf "$REPLICA_DIR"
for d in pgdata tablespaces/ts_catalogos tablespaces/ts_transaccional tablespaces/ts_auditoria tablespaces/ts_indices; do
  mkdir -p "$REPLICA_DIR/$d"
  chmod 700 "$REPLICA_DIR/$d"
done

echo "== 3. pg_basebackup desde fixit_pg_master (usuario replicator, :5432) =="
PGPASSWORD="$REPLICATOR_PASSWORD" pg_basebackup \
  -h localhost -p 5432 -U "$REPLICATOR_USER" \
  -D "$REPLICA_DIR/pgdata" \
  -T "/var/lib/postgresql/tablespaces/ts_catalogos=$REPLICA_DIR/tablespaces/ts_catalogos" \
  -T "/var/lib/postgresql/tablespaces/ts_transaccional=$REPLICA_DIR/tablespaces/ts_transaccional" \
  -T "/var/lib/postgresql/tablespaces/ts_auditoria=$REPLICA_DIR/tablespaces/ts_auditoria" \
  -T "/var/lib/postgresql/tablespaces/ts_indices=$REPLICA_DIR/tablespaces/ts_indices" \
  -R -X stream -C -S "$SLOT_NAME" --checkpoint=fast -P -v

echo "== 4a. Corrigiendo symlinks de pg_tblspc (pg_basebackup -T los crea con la ruta" \
     "absoluta del HOST; el contenedor necesita la ruta /var/lib/postgresql/...) =="
podman unshare bash -c "
  cd '$REPLICA_DIR/pgdata/pg_tblspc'
  for link in *; do
    name=\$(basename \"\$(readlink \"\$link\")\")
    ln -sfn \"/var/lib/postgresql/tablespaces/\$name\" \"\$link\"
  done
"

echo "== 4b. Corrigiendo primary_conninfo (pg_basebackup -R escribe host=localhost," \
     "valido para el cliente del host pero no para la red del contenedor) =="
podman unshare sed -i \
  "s/host=localhost/host=fixit_pg_master/" \
  "$REPLICA_DIR/pgdata/postgresql.auto.conf"

echo "== 4c. Depurando ajustes de recovery_target heredados del maestro (si el" \
     "maestro paso antes por un PITR, pg_basebackup copia ese residuo y la" \
     "replica se auto-promoveria al alcanzarlo en vez de seguir en streaming) =="
podman unshare sed -i \
  -e "/^restore_command/d" -e "/^recovery_target_time/d" -e "/^recovery_target_action/d" \
  "$REPLICA_DIR/pgdata/postgresql.auto.conf"

echo "== 5. Normalizando propietario (uid/gid 999 postgres) =="
podman unshare chown -R 999:999 "$REPLICA_DIR"
podman unshare chmod 700 "$REPLICA_DIR/pgdata"

echo "== 6. Levantando fixit_pg_replica (:5433) =="
podman-compose -f "$INFRA_DIR/compose.yaml" --env-file "$INFRA_DIR/.env" up -d fixit_pg_replica

for i in $(seq 1 30); do
  podman exec --user postgres fixit_pg_replica pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done

echo ""
echo "== Verificacion: pg_is_in_recovery() en la replica =="
podman exec --user postgres fixit_pg_replica psql -U postgres -d fixit_db -c "SELECT pg_is_in_recovery();"

echo ""
echo "== Verificacion: pg_stat_replication en el maestro =="
podman exec --user postgres fixit_pg_master psql -U postgres -d fixit_db -c \
  "SELECT application_name, client_addr, state, sync_state FROM pg_stat_replication;"

echo ""
echo "== setup_replication.sh completado =="
