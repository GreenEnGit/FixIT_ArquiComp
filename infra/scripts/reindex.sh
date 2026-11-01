#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/reindex.sh
# SCB-1001 — T-07: U4.T4.S3 — Diagnostico, reorganizacion y reconstruccion
# periodica de los indices B-Tree alojados en ts_indices. Practica 3.
set -euo pipefail

CONTAINER="fixit_pg_master"
PROBE_SQL="EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM tickets WHERE branch_id = 'NORTE' AND status = 'RECIBIDO';"

psql_exec() {
  podman exec --user postgres "$CONTAINER" psql -U postgres -d fixit_db -c "$1"
}

echo "== Diagnostico ANTES: EXPLAIN (ANALYZE, BUFFERS) =="
psql_exec "$PROBE_SQL"

echo ""
echo "== Tamaño de los indices en ts_indices (top 10) =="
psql_exec "
SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes i
JOIN pg_class c ON c.oid = i.indexrelid
JOIN pg_tablespace t ON t.oid = c.reltablespace
WHERE t.spcname = 'ts_indices'
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 10;"

echo ""
echo "== REINDEX de todos los indices en ts_indices =="
# No existe el comando "REINDEX TABLESPACE" en PostgreSQL; se reconstruye
# cada indice individualmente vía REINDEX INDEX, que es el equivalente real.
podman exec --user postgres "$CONTAINER" psql -U postgres -d fixit_db -v ON_ERROR_STOP=1 -c "
DO \$\$
DECLARE
    idx RECORD;
BEGIN
    FOR idx IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_tablespace t ON t.oid = c.reltablespace
        WHERE t.spcname = 'ts_indices' AND c.relkind = 'i'
    LOOP
        EXECUTE format('REINDEX INDEX %I', idx.relname);
    END LOOP;
END \$\$;"
echo "Codigo de salida REINDEX: $?"

echo ""
echo "== Diagnostico DESPUES: EXPLAIN (ANALYZE, BUFFERS) =="
psql_exec "$PROBE_SQL"
