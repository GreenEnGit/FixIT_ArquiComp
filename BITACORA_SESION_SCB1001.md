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

### T-13.1 — Segunda pasada: identidad visual propia (feedback: "se siente igual, solo mejorado")

El primer pase de T-13 fue, en honor a la verdad, un reskin conservador: mismo esqueleto de tarjeta-redondeada + sombra-suave + badge-píldora de siempre, solo con colores/íconos nuevos encima (el patrón genérico "SaaS card kit"). Tras feedback directo del usuario, se hizo una segunda pasada con un lenguaje visual propio inspirado en el dominio real (taller de hardware + consola de servidores/DBA), aplicado en `layout.html` y propagado al resto de plantillas:

- **Forma/sombra**: fuera `rounded-xl`/`shadow-sm` por defecto en tarjetas estáticas; radio máximo `rounded-lg`, bordes de 1px ("hairline"), sombra reservada solo para elementos realmente flotantes (modales, dropdowns, chat).
- **Panel de lectura ("gauge-panel")**: las tarjetas KPI (Dashboard, Inventario, Reportes) pasan a un panel oscuro `#020617` con barra de acento superior y cifras monoespaciadas con resplandor sutil (`text-shadow`), evocando un multímetro/osciloscopio — es el único lugar del sistema donde se rompe a oscuro sobre fondo claro, usado de forma consistente (no decorativa).
- **Estados como LED**: los badges de estado de tickets (`tickets_list.html`, `ticket.html`) pasan de píldora de color sólido a punto LED con resplandor (`.led-dot`, `box-shadow: 0 0 6px currentColor`) + etiqueta monoespaciada sobre fondo neutro — como un panel de luces de servidor, no un chip de app genérica.
- **Sidebar**: textura sutil de rejilla tipo placa base (`.pcb-grid`, gradientes lineales de 24px repetidos a baja opacidad) sobre `slate-950`; el ítem de navegación activo se marca con una barra de acento lateral de 2px en vez de un bloque relleno.
- **Topbar**: breadcrumb en estilo ruta de archivo monoespaciada (`/dashboard`) en vez de icono+texto genérico.
- Mismas garantías que el primer pase: cero cambios a `name`/`id`/rutas de formularios, `pytest` 10/10, verificado de nuevo con Chrome DevTools MCP (0 errores, 0 requests externos) y evidencia UI regenerada.

### T-13.2 — Bug preexistente encontrado y corregido: `sales.status` truncaba al revertir una venta

El usuario reportó `500 Internal Server Error` al vender un artículo por POS y luego revertir esa venta — algo que, según indicó, no pasaba antes. El traceback (`psycopg.errors.StringDataRightTruncation: value too long for type character varying(20)`) señaló la causa exacta en `routers/pos.py::revert_pos_sale`: la columna `sales.status` se definió en `src/sql/02_schema.sql` como `VARCHAR(20)` durante la migración SQLite→Postgres de T-05/T-06, pero el código construye un mensaje de auditoría largo (`"REVERTIDA por @usuario el <fecha> | Motivo: <razón>"`) para esa misma columna. SQLite nunca validó la longitud, así que el bug quedó dormido hasta la primera reversión real contra Postgres. **No relacionado con el rediseño de T-13/T-13.1** (no se tocó ningún `.py` ni `.sql` en esas fases).

- Corregido: `status` pasó de `VARCHAR(20)` a `TEXT` en `src/sql/02_schema.sql` (ya no se ejecuta con `init_env.sh` salvo en un volumen vacío) **y** se aplicó en vivo contra `fixit_pg_master` con `ALTER TABLE sales ALTER COLUMN status TYPE TEXT;` (se replica automáticamente a `fixit_pg_replica` vía streaming).
- Auditoría de todo el código en busca del mismo patrón (string largo construido dinámicamente hacia una columna `VARCHAR` corta): se revisaron todos los `UPDATE ... SET status = ...` y todos los `f"..."` insertados en columnas tipadas de `routers/*.py` y `main.py`. Único caso afectado. `tickets.status` (VARCHAR(30)) y `appointments.status`/`loaners.status` (VARCHAR(20/30)) solo reciben valores fijos cortos de un enum, no strings concatenados — no están en riesgo.
- Verificación en vivo (no solo el fix puntual): se ejercitó de punta a punta, contra el clúster real, el ciclo completo de tickets (comentario, mano de obra, añadir refacción, cambio de estado, abono parcial, liquidación total con imagen, garantía, factura), inventario (alta, edición, surtido, deducción por venta, merma, vaciado de stock, eliminación), auditoría (revertir merma ✅, revertir surtido con stock insuficiente → bloqueado correctamente con 400, no es un bug), citas/préstamos, usuarios, clientes y base de conocimientos. **0 errores 500 nuevos** en todo el barrido; el único 500 de la sesión fue el ya corregido. `pytest -v tests/test_dba_scb1001.py`: 10/10 después del fix.

## Estado final

- `fixit_pg_master` (:5432) y `fixit_pg_replica` (:5433) en streaming estable.
- Auditoría dinámica activa; 4 tablespaces con las ~19 tablas distribuidas; RBAC y cuotas verificados.
- Suite `pytest -v tests/test_dba_scb1001.py`: 10/10.
- UI/UX rediseñada en las 25 plantillas sobre Flowbite + Lucide + ApexCharts + Alpine.js, 100% offline (ver T-13).
- Pendiente para una futura sesión: rotar las credenciales de laboratorio antes de cualquier uso real, evaluar *connection pooling* (`psycopg_pool`) y automatizar `backup_job.sh` por cron/systemd timer.
