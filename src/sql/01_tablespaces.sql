-- FixIT_ArquiComp — src/sql/01_tablespaces.sql
-- SCB-1001 — T-03: U3.T3.S1 (definicion de espacio), U3.T3.S2 (creacion de
--   espacios asignados), U3.T3.S4 (espacios para objetos de la base de datos)
--
-- Se ejecuta una sola vez por docker-entrypoint-initdb.d al crear
-- fixit_pg_master (data dir vacio). Las rutas corresponden a los volumenes
-- montados en infra/compose.yaml (./volumes/tablespaces/*).

CREATE TABLESPACE ts_catalogos
    OWNER postgres
    LOCATION '/var/lib/postgresql/tablespaces/ts_catalogos';

CREATE TABLESPACE ts_transaccional
    OWNER postgres
    LOCATION '/var/lib/postgresql/tablespaces/ts_transaccional';

CREATE TABLESPACE ts_auditoria
    OWNER postgres
    LOCATION '/var/lib/postgresql/tablespaces/ts_auditoria';

CREATE TABLESPACE ts_indices
    OWNER postgres
    LOCATION '/var/lib/postgresql/tablespaces/ts_indices';
