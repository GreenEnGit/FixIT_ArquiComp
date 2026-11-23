-- FixIT_ArquiComp — src/sql/upgrades/2026-11_v2_catalogo_y_cifrado.sql
-- Actualiza una base creada con el esquema anterior al modelo v2 de
-- 02_schema.sql (una instalacion nueva ya nace con este modelo):
--   1. Catalogo `products` (ts_catalogos) separado de las existencias por
--      sucursal en `inventory` (PK compuesta id + branch_id) y vista v_inventory.
--   2. appointments.date/time como DATE/TIME nativos.
--   3. customer_devices.password cifrada con pgcrypto (BYTEA).
--
-- Uso (como superusuario, la clave sale del .env de la aplicacion):
--   podman exec -i --user postgres fixit_pg_master psql -U postgres -d fixit_db -v ON_ERROR_STOP=1 \
--     -v device_key="$DEVICE_DATA_KEY" < src/sql/upgrades/2026-11_v2_catalogo_y_cifrado.sql

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Catalogo maestro + existencias por sucursal --------------------------
CREATE TABLE products (
    id          VARCHAR(30)   PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    name        VARCHAR(150)  NOT NULL,
    brand       VARCHAR(80)   NOT NULL,
    category    VARCHAR(50)   NOT NULL,
    specs       JSONB,
    image_path  VARCHAR(255)
) TABLESPACE ts_catalogos;

INSERT INTO products (id, name, brand, category, specs, image_path)
SELECT id, name, brand, category, specs, image_path FROM inventory;

ALTER TABLE purchase_orders DROP CONSTRAINT purchase_orders_part_id_fkey;
ALTER TABLE ticket_parts    DROP CONSTRAINT ticket_parts_part_id_fkey;
ALTER TABLE sale_items      DROP CONSTRAINT sale_items_item_id_fkey;

ALTER TABLE inventory DROP CONSTRAINT inventory_pkey;
ALTER TABLE inventory
    DROP COLUMN name, DROP COLUMN brand, DROP COLUMN category,
    DROP COLUMN specs, DROP COLUMN image_path;
ALTER TABLE inventory ADD PRIMARY KEY (id, branch_id) USING INDEX TABLESPACE ts_indices;
ALTER TABLE inventory ADD CONSTRAINT inventory_id_fkey FOREIGN KEY (id) REFERENCES products(id);

ALTER TABLE purchase_orders ADD CONSTRAINT purchase_orders_part_id_fkey FOREIGN KEY (part_id) REFERENCES products(id);
ALTER TABLE ticket_parts    ADD CONSTRAINT ticket_parts_part_id_fkey    FOREIGN KEY (part_id) REFERENCES products(id);
ALTER TABLE sale_items      ADD CONSTRAINT sale_items_item_id_fkey      FOREIGN KEY (item_id) REFERENCES products(id);

CREATE VIEW v_inventory AS
SELECT i.id, p.name, p.brand, p.category, p.specs, i.stock, i.cost, i.price,
       i.branch_id, p.image_path
FROM inventory i
JOIN products p ON p.id = i.id;

GRANT SELECT ON products, v_inventory TO rol_tecnico, rol_recepcion;

-- 2. Citas con tipos nativos ------------------------------------------------
ALTER TABLE appointments
    ALTER COLUMN date TYPE DATE USING date::date,
    ALTER COLUMN time TYPE TIME USING time::time;

-- 3. Contrasenas de equipos cifradas ---------------------------------------
ALTER TABLE customer_devices
    ALTER COLUMN password TYPE BYTEA
    USING CASE WHEN password IS NULL OR password = '' THEN NULL
               ELSE pgp_sym_encrypt(password, :'device_key') END;

COMMIT;
