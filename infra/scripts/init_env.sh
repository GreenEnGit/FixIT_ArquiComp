#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/init_env.sh
# SCB-1001 — T-01: Aprovisionamiento del entorno y contenedor fixit_pg_master
#   U2.T2.S2 (estructura fisica), U2.T2.S3 (requerimientos), U2.T2.S5 (variables
#   de ambiente), U2.T2.S6 (procedimiento general de instalacion)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(cd "$INFRA_DIR/.." && pwd)"

CHECK_ONLY=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=true
fi

echo "== FixIT_ArquiComp :: init_env.sh (SCB-1001) =="
echo "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"

check_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "[FALTA] $name no esta instalado."
    return 1
  fi
  echo "[OK] $name -> $("$name" --version 2>&1 | head -n1)"
}

echo ""
echo "--- Requerimientos del host (U2.T2.S3) ---"
check_cmd podman
check_cmd podman-compose
check_cmd psql

if $CHECK_ONLY; then
  echo ""
  echo "Modo --check: no se realizaron cambios."
  exit 0
fi

echo ""
echo "--- Estructura fisica de directorios (U2.T2.S2) ---"
# uid/gid 999 = usuario "postgres" dentro de la imagen postgres:16.4-bookworm.
# `podman unshare chown` traduce ese uid al mapeo de subuid rootless del host
# una sola vez, para que el proceso postgres pueda escribir/chmod cada
# tablespace sin depender del sufijo :U en los bind mounts (que revertiria
# el dueño a root en cada reinicio).
for d in pgdata wal_archive tablespaces/ts_catalogos tablespaces/ts_transaccional tablespaces/ts_auditoria tablespaces/ts_indices; do
  mkdir -p "$INFRA_DIR/volumes/$d"
  chmod 700 "$INFRA_DIR/volumes/$d"
  podman unshare chown 999:999 "$INFRA_DIR/volumes/$d"
  echo "[OK] $INFRA_DIR/volumes/$d (0700, uid/gid 999 postgres)"
done
mkdir -p "$PROJECT_DIR/backups"
chmod 700 "$PROJECT_DIR/backups"
podman unshare chown 999:999 "$PROJECT_DIR/backups"
echo "[OK] $PROJECT_DIR/backups"

echo ""
echo "--- Variables de ambiente (U2.T2.S5) ---"
if [[ ! -f "$INFRA_DIR/.env" ]]; then
  cp "$INFRA_DIR/.env.example" "$INFRA_DIR/.env"
  echo "[OK] Creado $INFRA_DIR/.env desde .env.example"
else
  echo "[OK] $INFRA_DIR/.env ya existe"
fi

set -a
source "$INFRA_DIR/.env"
set +a

echo ""
echo "--- Procedimiento general de instalacion (U2.T2.S6) ---"
podman-compose -f "$INFRA_DIR/compose.yaml" --env-file "$INFRA_DIR/.env" up -d

echo ""
echo "--- Verificacion de arranque en modo transaccional ---"
READY=false
for i in $(seq 1 30); do
  if podman exec fixit_pg_master pg_isready -U "${POSTGRES_SUPERUSER:-postgres}" -d "${POSTGRES_DB:-fixit_db}" >/dev/null 2>&1; then
    READY=true
    break
  fi
  sleep 1
done

if ! $READY; then
  echo "[ERROR] fixit_pg_master no respondio a tiempo."
  podman logs --tail 50 fixit_pg_master || true
  exit 1
fi

echo "[OK] fixit_pg_master listo."
podman exec --user postgres fixit_pg_master psql -U "${POSTGRES_SUPERUSER:-postgres}" -d "${POSTGRES_DB:-fixit_db}" -c "SELECT version();"
podman exec --user postgres fixit_pg_master psql -U "${POSTGRES_SUPERUSER:-postgres}" -d "${POSTGRES_DB:-fixit_db}" -c "\db+"

echo ""
echo "== init_env.sh completado =="
