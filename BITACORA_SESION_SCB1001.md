# Bitácora de la sesión — Evolución de FixIT a PostgreSQL 16.4 (SCB-1001)

Recapitulación de las 12 tareas (T-01 a T-12) ejecutadas sobre `FixIT_ArquiComp` para cumplir el temario **Administración de Base de Datos (SCB-1001)**, en orden cronológico y con verificación real (sin mocks) en cada paso.

## T-01 a T-04 — Aprovisionamiento, esquema y seguridad

- `infra/scripts/init_env.sh` + `infra/compose.yaml` + `infra/config/{postgresql.conf,pg_hba.conf}`: levantan `fixit_pg_master` (PostgreSQL 16.4) en Podman 4.9.3 rootless.
- `src/sql/01_tablespaces.sql`: los 4 tablespaces (`ts_catalogos`, `ts_transaccional`, `ts_auditoria`, `ts_indices`).
- `src/sql/02_schema.sql`: las 19 tablas de `database.py` migradas 1:1, distribuidas por tablespace, con todos los índices PK/UNIQUE en `ts_indices`.
- `src/sql/03_roles_and_quotas.sh`: roles RBAC (`rol_dba`, `rol_tecnico`, `rol_recepcion`, `rol_auditor`, `rol_replicacion`) y el trigger `trg_enforce_user_quota`.
- Bug corregido en el camino: dentro de Podman rootless, el sufijo `:U` de un bind mount chownea al UID del *proceso raíz* del contenedor (root), no al usuario interno `postgres` (999); se resolvió con `podman unshare chown 999:999` desde los scripts.

## T-05 a T-07 — Migración del motor de la app y mantenimiento

- `database.py` reescrito completo sobre `psycopg 3.2.2`. Un shim traduce `?` → `%s` para no reescribir las ~400 consultas de `routers/`.
- `infra/scripts/migrate_sqlite_to_pg.py --verify`: migra `taller_prototipo.db` preservando IDs (`OVERRIDING SYSTEM VALUE`) y resincronizando secuencias.
- Al conectar la app real contra Postgres aparecieron 7 incompatibilidades reales (no cosméticas) que se corrigieron una por una: `Decimal` vs `float` en columnas `NUMERIC`, `date` vs `str` en comparaciones, `GROUP BY` estricto de Postgres, `text || integer` sin cast, `cursor.lastrowid` inexistente (se usó `RETURNING id`), `date('now')` de SQLite, y la excepción de integridad equivocada.
- `infra/scripts/ops_modes.sh [start|stop|status|recovery|normal|logs]`.
- `src/sql/04_indexes.sql` + `infra/scripts/reindex.sh` (con `REINDEX INDEX` en un `DO` block, porque `REINDEX TABLESPACE` no existe en PostgreSQL).
- `src/data_generator/seed_workload.py`: 10,000 tickets sintéticos con Faker en <1s.

## T-08 a T-10 — Alta disponibilidad, continuidad y auditoría

- `infra/scripts/setup_replication.sh`: Streaming Replication real hacia `fixit_pg_replica` (:5433) vía `pg_basebackup` ejecutado desde el host. Se corrigieron tres trampas no obvias: `host=localhost` inválido en `primary_conninfo`, symlinks de `pg_tblspc` con ruta del host, y residuos de `recovery_target_time` que hacían que una réplica reclonada se auto-promoviera sola.
- `infra/scripts/backup_job.sh` + `infra/scripts/restore_pitr.sh`: drill completo probado (borrado simulado en `payments`, recuperación exacta al segundo previo al incidente).
- `src/sql/05_audit_and_monitoring.sql`: `pg_stat_statements` + trigger genérico `trg_audit_dml` (JSONB antes/después) sobre `payments`/`tickets`/`inventory`.
- `infra/scripts/toggle_audit.sh` y `infra/scripts/monitor_resources.sh`.

## T-11 y T-12 — Evidencia visual y validación académica

- `infra/scripts/capture_evidence.py` (Playwright + mermaid-cli): 4 diagramas de arquitectura, 25 capturas de terminal ejecutando comandos reales de las 11 prácticas, y 4 capturas de la interfaz web FixIT corriendo contra PostgreSQL.
- `tests/test_dba_scb1001.py`: 10 casos (CP-01 a CP-10), **10/10 pasan** contra el clúster real.
- Los 6 manuales (`README.md`, `MANUAL_INSTALACION.md`, `DICCIONARIO_DATOS.md`, `MANUAL_ADMINISTRACION.md`, `PLAN_CONTINGENCIA.md`, `REPORTE_AUDITORIA.md`) con las capturas incrustadas.

## T-13 — Rediseño UI/UX SaaS Enterprise 100% offline

- Las 25 plantillas Jinja2 de `templates/` se rediseñaron sobre un sistema de diseño único (paleta semántica `slate`/`indigo`/`emerald`/`amber`/`rose`, tipografía `ui-sans-serif`/`ui-monospace`) definido vía `tailwind.config` inline en `layout.html`.
- Se integraron 4 motores locales ya presentes en `static/` (`flowbite.min.js`, `lucide.min.js`, `apexcharts.min.js`, `alpine.min.js`): iconografía Lucide en sidebar/topbar/tablas, búsqueda y filtros por estado con Alpine.js (`tickets_list.html`, `inventory_sales.html`), y las 3 gráficas de `dashboard.html` migradas de Chart.js (CDN) a ApexCharts (local).
- Blindaje 100% offline: se eliminaron las 3 URLs externas que quedaban (`fonts.googleapis.com` en `layout.html`/`login.html`/`tracking.html` y el `cdn.jsdelivr.net` de Chart.js en `layout.html`). Verificado con Chrome DevTools MCP en las vistas de login, dashboard, tickets, inventario, POS y auditoría: 0 peticiones a dominios externos, 0 errores de consola, 0 peticiones fallidas.
- Shell de aplicación nuevo: sidebar oscura colapsable con badge técnico `PostgreSQL 16.4 · Cluster HA (Master:5432 / Replica:5433)`, topbar con breadcrumbs + búsqueda global + rol RBAC + logout.
- REGLA INQUEBRANTABLE respetada: ningún `name`, ruta de formulario ni selector usado por `infra/scripts/capture_evidence.py` o `tests/test_dba_scb1001.py` (`input[name="username"]`, `input[name="password"]`, `button[type="submit"]`, rutas `/login`, `/ticket`, `/inventory/sales`, `/audit`) se tocó.
- Evidencia regenerada: `evidencias/capturas/ui/UI_01..04.png` con `infra/scripts/capture_evidence.py --ui`, inspeccionadas visualmente. Suite `pytest -v tests/test_dba_scb1001.py`: **10/10** sobre el clúster real recién reaprovisionado (`init_env.sh` + `seed_sqlite_source.py` + `migrate_sqlite_to_pg.py --verify`).

## Estado final

- `fixit_pg_master` (:5432) y `fixit_pg_replica` (:5433) en streaming estable.
- Auditoría dinámica activa; 4 tablespaces con las ~19 tablas distribuidas; RBAC y cuotas verificados.
- Suite `pytest -v tests/test_dba_scb1001.py`: 10/10.
- UI/UX rediseñada en las 25 plantillas sobre Flowbite + Lucide + ApexCharts + Alpine.js, 100% offline (ver T-13).
- Pendiente para una futura sesión: rotar las credenciales de laboratorio antes de cualquier uso real, evaluar *connection pooling* (`psycopg_pool`) y automatizar `backup_job.sh` por cron/systemd timer.
