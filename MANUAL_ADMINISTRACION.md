# MANUAL_ADMINISTRACION.md — SCB-1001

**Unidad 3** (Espacio en disco, cuotas, roles) · **Unidad 4** (Operación y mantenimiento) · **Prácticas 2, 3, 4 y 5**

## 1. Administración de espacio en disco y cuotas de usuario

El trigger `trg_enforce_user_quota()` audita el espacio atribuido a cada rol en `user_disk_quotas` y aborta el `INSERT` cuando se excede el límite, devolviendo literalmente `ERROR: Cuota de espacio en disco excedida`.

![Bloqueo por cuota de espacio excedida](evidencias/capturas/terminal/P02_cuotas_limite_usuarios.png)

## 2. Índices, reorganización y reconstrucción

`src/sql/04_indexes.sql` cubre los índices de FK/filtro que no quedaron en `02_schema.sql`. `infra/scripts/reindex.sh` diagnostica con `EXPLAIN (ANALYZE, BUFFERS)`, reconstruye cada índice en `ts_indices` vía `REINDEX INDEX` (Postgres no tiene `REINDEX TABLESPACE`) y vuelve a medir.

![Carga sintética, EXPLAIN y REINDEX](evidencias/capturas/terminal/P03_indices_y_reorganizacion.png)

`src/data_generator/seed_workload.py` (Faker 30.1.0) inyecta carga sintética en segundos para ejercitar estos índices bajo volumen real.

## 3. Modos de operación: alta, baja y recovery

`infra/scripts/ops_modes.sh` controla la transición entre modos:

- **recovery**: crea `standby.signal` y reinicia el contenedor para forzar un `pg_is_in_recovery() = true` sostenido (no hay un segundo nodo primario aún en este punto del ciclo; se usa el propio nodo como standby de sí mismo).
- **normal**: espera hasta 90 s a que la instancia acepte conexiones, promueve con `SELECT pg_promote(true, 120);` (espera a que termine la promoción) y verifica que `pg_is_in_recovery()` sea `false`; si no lo es, el script termina con error.

![Transición entre modos alta/recovery/normal](evidencias/capturas/terminal/P04_modos_operacion_recovery.png)

## 4. Archivos log y WAL

`ops_modes.sh logs` lista `pg_log/*.csv`, muestra las últimas líneas del log activo y consulta `pg_stat_wal`.

![Verificación de archivos log y WAL](evidencias/capturas/terminal/P05_verificacion_archivos_log.png)

## 5. Configuración relevante (`infra/config/postgresql.conf`)

| Parámetro | Valor | Propósito |
| :--- | :--- | :--- |
| `wal_level` | `replica` | Habilita Streaming Replication y PITR |
| `archive_mode` / `archive_command` | `on` / copia a `wal_archive` | Respaldo continuo de WAL |
| `logging_collector` | `on` | Archivos log en `pg_log/` (csvlog) |
| `shared_preload_libraries` | `pg_stat_statements` | Monitoreo de consultas (Unidad 6) |
| `max_wal_senders` / `max_replication_slots` | 10 / 10 | Soporte de réplicas físicas |

## 6. Operación diaria en la aplicación

**Punto de venta:** cada clic sobre un producto agrega una unidad; las cantidades se ajustan con `-`/`+` y el cobro descuenta existencias solo de la sucursal activa.

![Punto de venta con fotos](evidencias/capturas/ui/UI_05_punto_de_venta_fotos.png)

**Inventario multi-sucursal:** el detalle de cada producto muestra sus existencias y precio en cada sucursal.

![Detalle de producto con existencias por sucursal](evidencias/capturas/ui/UI_06_detalle_producto_existencias.png)

**Recepción de equipos:** el PIN de desbloqueo se guarda cifrado y en el ticket solo se muestra al pulsar *Mostrar*.

![Recepción con PIN cifrado](evidencias/capturas/ui/UI_07_recepcion_pin_cifrado.png)

![Ticket con PIN revelado bajo demanda](evidencias/capturas/ui/UI_08_ticket_pin_desbloqueo.png)

**Citas y préstamos:** la agenda usa tipos `DATE`/`TIME`; no admite fechas pasadas ni horas fuera del horario laboral (09:00 a 19:00).

![Agenda de citas](evidencias/capturas/ui/UI_09_citas_agenda.png)

La interfaz se adapta a pantallas de celular:

![Vista móvil](evidencias/capturas/ui/UI_11_vista_movil.png)

