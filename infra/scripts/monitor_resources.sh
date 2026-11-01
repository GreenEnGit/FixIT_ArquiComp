#!/usr/bin/env bash
# FixIT_ArquiComp — infra/scripts/monitor_resources.sh
# SCB-1001 — T-10: U6.T6.S1 — Monitoreo de rendimiento y recursos del
# SGBD (pg_stat_statements, cache hit ratio, conexiones, bloqueos y
# tamaño por tablespace). Practica 11. RNF-09.
set -euo pipefail

CONTAINER="fixit_pg_master"

psql_exec() {
  podman exec --user postgres "$CONTAINER" psql -U postgres -d fixit_db -c "$1"
}

echo "== Top 10 consultas mas costosas (pg_stat_statements) =="
psql_exec "
  SELECT substring(query, 1, 60) AS query, calls,
         round(total_exec_time::numeric, 2) AS total_ms,
         round(mean_exec_time::numeric, 2) AS mean_ms
  FROM pg_stat_statements
  ORDER BY total_exec_time DESC
  LIMIT 10;"

echo ""
echo "== Cache hit ratio (tablas) =="
psql_exec "
  SELECT round(
    sum(heap_blks_hit)::numeric / nullif(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100,
    2
  ) AS cache_hit_ratio_pct
  FROM pg_statio_user_tables;"

echo ""
echo "== Conexiones activas por usuario y estado =="
psql_exec "
  SELECT usename, state, count(*)
  FROM pg_stat_activity
  WHERE datname = 'fixit_db'
  GROUP BY usename, state
  ORDER BY count DESC;"

echo ""
echo "== Bloqueos actuales =="
psql_exec "
  SELECT pid, mode, granted, relation::regclass AS tabla
  FROM pg_locks
  WHERE relation IS NOT NULL
  ORDER BY pid;"

echo ""
echo "== Tamaño por tablespace =="
psql_exec "
  SELECT spcname AS tablespace, pg_size_pretty(pg_tablespace_size(spcname)) AS tamaño
  FROM pg_tablespace
  ORDER BY pg_tablespace_size(spcname) DESC;"
