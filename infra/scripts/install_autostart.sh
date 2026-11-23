#!/usr/bin/env bash
# Instala el arranque automatico de FixIT al encender la VM y el acceso por
# http://fixittester.com (solo en esta maquina, via /etc/hosts).
# Requiere que init_env.sh (y opcionalmente setup_replication.sh) ya se hayan ejecutado.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
HOSTNAME_FIXIT="fixittester.com"

mkdir -p "$UNIT_DIR"
for unit in container-fixit_pg_master.service container-fixit_pg_replica.service fixit-web.service; do
    sed "s#@PROJECT_DIR@#$PROJECT_DIR#g" "$PROJECT_DIR/infra/systemd/$unit" > "$UNIT_DIR/$unit"
done

units="container-fixit_pg_master.service fixit-web.service"
podman container exists fixit_pg_replica && units="$units container-fixit_pg_replica.service"

# Pasos con privilegios: hostname local, puerto 80 sin root y servicios sin sesion iniciada
sudo sh -c "grep -q '$HOSTNAME_FIXIT' /etc/hosts || echo '127.0.0.1 $HOSTNAME_FIXIT www.$HOSTNAME_FIXIT' >> /etc/hosts
echo 'net.ipv4.ip_unprivileged_port_start=80' > /etc/sysctl.d/99-fixit-port80.conf
sysctl --system >/dev/null"
sudo loginctl enable-linger "$USER"

systemctl --user daemon-reload
systemctl --user enable $units
systemctl --user restart $units

sleep 3
systemctl --user is-active $units
curl -s -o /dev/null -w "http://$HOSTNAME_FIXIT/login -> HTTP %{http_code}\n" "http://$HOSTNAME_FIXIT/login"
