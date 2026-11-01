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
# backups/ ya NO se monta en el contenedor (pg_dump/pg_basebackup corren
# desde el host en backup_job.sh/restore_pitr.sh): permanece como
# directorio normal del usuario del host, sin el truco de uid 999.
mkdir -p "$PROJECT_DIR/backups"
chmod 755 "$PROJECT_DIR/backups"
echo "[OK] $PROJECT_DIR/backups"

echo ""
echo "--- Variables de ambiente (U2.T2.S5) ---"
if [[ ! -f "$INFRA_DIR/.env" ]]; then
  cp "$INFRA_DIR/.env.example" "$INFRA_DIR/.env"
  echo "[OK] Creado $INFRA_DIR/.env desde .env.example"
else
  echo "[OK] $INFRA_DIR/.env ya existe"
fi

# Genera una contraseña aleatoria unica por instalacion para cada variable
# que haya quedado en CHANGE_ME (nunca se commitea una contraseña real).
generate_password() {
  openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 24
}

while IFS='=' read -r key value; do
  [[ "$key" =~ ^[A-Z_]+$ ]] || continue
  if [[ "$value" == "CHANGE_ME" ]]; then
    newpass="$(generate_password)"
    sed -i "s/^${key}=CHANGE_ME$/${key}=${newpass}/" "$INFRA_DIR/.env"
    echo "[OK] Generada contraseña aleatoria para $key"
  fi
done < "$INFRA_DIR/.env"

set -a
source "$INFRA_DIR/.env"
set +a

# El .env de la app (raiz) debe autenticar admin_sys con la MISMA
# contraseña que se acaba de generar/fijar en infra/.env; se sincroniza
# automaticamente para que la instalacion sea reproducible sin pasos
# manuales adicionales.
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  echo "[OK] Creado $PROJECT_DIR/.env desde .env.example"
fi
sed -i "s/^PGUSER=.*/PGUSER=admin_sys/" "$PROJECT_DIR/.env"
sed -i "s/^PGPASSWORD=.*/PGPASSWORD=${ADMIN_SYS_PASSWORD}/" "$PROJECT_DIR/.env"
echo "[OK] Sincronizado PGUSER/PGPASSWORD en $PROJECT_DIR/.env con infra/.env"

echo ""
echo "--- Procedimiento general de instalacion (U2.T2.S6) ---"
# Solo el maestro: fixit_pg_replica se levanta via setup_replication.sh,
# que la clona correctamente con pg_basebackup (-d sin nombre de servicio
# levantaria tambien un "replica" vacio y desconectado, no un standby real).
podman-compose -f "$INFRA_DIR/compose.yaml" --env-file "$INFRA_DIR/.env" up -d fixit_pg_master

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

# pg_isready puede responder "listo" contra la instancia TEMPORAL que usa
# el entrypoint oficial para correr los scripts de docker-entrypoint-
# initdb.d; al terminar, esa instancia se detiene y se reinicia la
# definitiva. Si la consulta cae justo en ese reinicio, falla con
# "the database system is shutting down" aunque todo este bien — se
# reintenta brevemente para no reportar un falso error.
for i in $(seq 1 10); do
  if podman exec --user postgres fixit_pg_master psql -U "${POSTGRES_SUPERUSER:-postgres}" -d "${POSTGRES_DB:-fixit_db}" -c "SELECT version();"; then
    break
  fi
  sleep 1
done
podman exec --user postgres fixit_pg_master psql -U "${POSTGRES_SUPERUSER:-postgres}" -d "${POSTGRES_DB:-fixit_db}" -c "\db+"

echo ""
echo "== init_env.sh completado =="
