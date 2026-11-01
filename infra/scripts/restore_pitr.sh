#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/restore_pitr.sh
# SCB-1001 — T-09: U5.T5.S4 — Recuperacion Point-In-Time (PITR) de
# fixit_pg_master a partir del respaldo fisico mas reciente + WAL
# archivado. Practica 8. RNF-08.
#
# Uso: infra/scripts/restore_pitr.sh "YYYY-MM-DD HH:MM:SS"
set -euo pipefail

TARGET_TIME="${1:?Uso: restore_pitr.sh \"YYYY-MM-DD HH:MM:SS\"}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$INFRA_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
PGDATA_DIR="$INFRA_DIR/volumes/pgdata"
TABLESPACES_DIR="$INFRA_DIR/volumes/tablespaces"

LATEST_TARBALL=$(ls -t "$BACKUP_DIR"/basebackup_*.tar.gz 2>/dev/null | head -1)
if [ -z "$LATEST_TARBALL" ]; then
  echo "[ERROR] No hay ningun respaldo fisico en $BACKUP_DIR. Ejecuta backup_job.sh primero."
  exit 1
fi
echo "== Restaurando a punto en el tiempo: $TARGET_TIME =="
echo "Respaldo fisico base: $LATEST_TARBALL"

echo ""
echo "== 1. Deteniendo fixit_pg_master y fixit_pg_replica =="
podman stop -t 30 fixit_pg_master || true
podman stop -t 30 fixit_pg_replica 2>/dev/null || true

echo ""
echo "== 2. Extrayendo el respaldo fisico =="
WORKDIR=$(mktemp -d)
tar xzf "$LATEST_TARBALL" -C "$WORKDIR"
BK_NAME=$(basename "$LATEST_TARBALL" .tar.gz)
EXTRACTED="$WORKDIR/$BK_NAME"

echo ""
echo "== 3. Restaurando pgdata y tablespaces, y configurando recovery_target_time =="
podman unshare bash -c "
set -euo pipefail
rm -rf '$PGDATA_DIR'/* '$PGDATA_DIR'/.[!.]* 2>/dev/null || true
cp -a '$EXTRACTED/base/.' '$PGDATA_DIR/'

for name in ts_catalogos ts_transaccional ts_auditoria ts_indices; do
    rm -rf '$TABLESPACES_DIR/'\$name/*
    cp -a '$EXTRACTED/'\$name'/.' '$TABLESPACES_DIR/'\$name'/'
done

# Los symlinks de pg_tblspc fueron creados por pg_basebackup con la ruta
# absoluta del HOST (ver backup_job.sh); se corrigen a la ruta que usa
# el contenedor en tiempo de ejecucion.
cd '$PGDATA_DIR/pg_tblspc'
for link in *; do
    [ -L \"\$link\" ] || continue
    name=\$(basename \"\$(readlink \"\$link\")\")
    ln -sfn \"/var/lib/postgresql/tablespaces/\$name\" \"\$link\"
done

touch '$PGDATA_DIR/recovery.signal'
cat >> '$PGDATA_DIR/postgresql.auto.conf' <<EOF
restore_command = 'cp /var/lib/postgresql/wal_archive/%f %p'
recovery_target_time = '$TARGET_TIME'
recovery_target_action = 'promote'
EOF

chown -R 999:999 '$PGDATA_DIR' '$TABLESPACES_DIR'
chmod 700 '$PGDATA_DIR'
"
rm -rf "$WORKDIR"

echo ""
echo "== 4. Arrancando fixit_pg_master en modo recovery (replay de WAL hasta el target) =="
podman start fixit_pg_master

for i in $(seq 1 60); do
  podman exec --user postgres fixit_pg_master pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done

echo ""
echo "== Verificacion: pg_is_in_recovery() (debe terminar en 'f' tras la promocion automatica) =="
podman exec --user postgres fixit_pg_master psql -U postgres -d fixit_db -c "SELECT pg_is_in_recovery();"

echo ""
echo "== 5. Limpiando ajustes de recovery ya consumidos =="
# restore_command / recovery_target_time / recovery_target_action quedan
# escritos en postgresql.auto.conf tras la promocion. Son inertes para el
# maestro ya promovido, pero si no se limpian, un pg_basebackup posterior
# (p. ej. para reclonar la replica) los copiaria junto con el resto del
# directorio y el nuevo nodo se "auto-promoveria" al alcanzar ese mismo
# target en vez de permanecer en streaming indefinidamente.
podman unshare sed -i \
  -e "/^restore_command/d" -e "/^recovery_target_time/d" -e "/^recovery_target_action/d" \
  "$PGDATA_DIR/postgresql.auto.conf"

echo ""
echo "[NOTA] fixit_pg_replica quedo detenida: el PITR genera una nueva linea de"
echo "tiempo (timeline) al promover, por lo que debe reclonarse con"
echo "setup_replication.sh para volver a sincronizarse con el maestro restaurado."
