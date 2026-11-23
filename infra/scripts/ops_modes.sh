#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/ops_modes.sh
# SCB-1001 — T-06: U4.T4.S1 (archivos log y WAL) y U4.T4.S2 (modos de
#   operacion alta/baja/recovery). Practicas 4 y 5.
set -euo pipefail

CONTAINER="fixit_pg_master"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PGDATA_PATH="/var/lib/postgresql/data"

psql_exec() {
  podman exec --user postgres "$CONTAINER" psql -U postgres -d fixit_db -t -A -c "$1"
}

# Espera hasta 90 s a que la instancia acepte conexiones (bajo carga, un
# reinicio con recuperacion puede tardar mas de 20 s).
wait_ready() {
  for i in $(seq 1 90); do
    podman exec --user postgres "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "[ERROR] $CONTAINER no acepto conexiones en 90 s" >&2
  return 1
}

usage() {
  echo "Uso: $0 [start|stop|status|recovery|normal|logs]"
  exit 1
}

case "${1:-}" in
  start)
    echo "== Alta del servicio (start) =="
    podman start "$CONTAINER"
    wait_ready
    podman exec --user postgres "$CONTAINER" pg_isready -U postgres
    ;;

  stop)
    echo "== Baja del servicio (stop) =="
    podman stop -t 30 "$CONTAINER"
    podman ps -a --filter "name=$CONTAINER" --format "{{.Names}}: {{.Status}}"
    ;;

  status)
    echo "== Estado del contenedor =="
    podman ps -a --filter "name=$CONTAINER" --format "{{.Names}}: {{.Status}}"
    if podman exec --user postgres "$CONTAINER" pg_isready -U postgres 2>/dev/null; then
      echo ""
      echo "== pg_is_in_recovery() =="
      psql_exec "SELECT pg_is_in_recovery();"
    fi
    ;;

  recovery)
    echo "== Transicion a modo RECOVERY =="
    # No existe aun un nodo primario que transmita WAL (streaming replication
    # se implementa en T-08); se fuerza el modo standby/recovery sobre el
    # propio nodo creando standby.signal, el mecanismo real que usa Postgres
    # para permanecer en recuperacion de forma sostenida y consultable.
    podman exec --user postgres "$CONTAINER" touch "$PGDATA_PATH/standby.signal"
    podman restart "$CONTAINER"
    wait_ready
    echo "pg_is_in_recovery():"
    psql_exec "SELECT pg_is_in_recovery();"
    ;;

  normal)
    echo "== Transicion a modo NORMAL (promocion) =="
    wait_ready
    if [[ "$(psql_exec "SELECT pg_is_in_recovery();")" == "t" ]]; then
      # pg_promote(wait => true, wait_seconds => 120): espera a que termine la promocion.
      psql_exec "SELECT pg_promote(true, 120);"
    fi
    echo "pg_is_in_recovery():"
    state="$(psql_exec "SELECT pg_is_in_recovery();")"
    echo "$state"
    [[ "$state" == "f" ]]
    ;;

  logs)
    echo "== Archivos log del SGBD (U4.T4.S1) =="
    podman exec --user postgres "$CONTAINER" ls -la "$PGDATA_PATH/pg_log"
    echo ""
    echo "== Ultimas lineas del log mas reciente =="
    LATEST=$(podman exec --user postgres "$CONTAINER" bash -c "ls -t $PGDATA_PATH/pg_log/*.log | head -1")
    podman exec --user postgres "$CONTAINER" tail -n 20 "$LATEST"
    echo ""
    echo "== pg_stat_wal =="
    podman exec --user postgres "$CONTAINER" psql -U postgres -d fixit_db -c "SELECT * FROM pg_stat_wal;"
    ;;

  *)
    usage
    ;;
esac
