-- FixIT_ArquiComp — src/sql/04_indexes.sql
-- SCB-1001 — T-07: U3.T3.S4 / U4.T4.S3 — Indices secundarios adicionales
-- para las columnas de FK y filtro que aun no tenian cobertura tras
-- src/sql/02_schema.sql, todos alojados en ts_indices. Practica 3.

CREATE INDEX IF NOT EXISTS idx_warranties_ticket       ON warranties(ticket_id)        TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_ticket_images_ticket    ON ticket_images(ticket_id)     TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_ticket_parts_part       ON ticket_parts(part_id)        TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_purchase_orders_vendor  ON purchase_orders(vendor_id)   TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_purchase_orders_part    ON purchase_orders(part_id)     TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_customer_devices_customer ON customer_devices(customer_id) TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_customer_devices_branch ON customer_devices(branch_id)  TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_sales_branch            ON sales(branch_id)             TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_sales_username          ON sales(username)              TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_sale_items_sale         ON sale_items(sale_id)          TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_sale_items_item         ON sale_items(item_id)          TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_appointments_branch     ON appointments(branch_id)      TABLESPACE ts_indices;
CREATE INDEX IF NOT EXISTS idx_loaners_branch          ON loaners(branch_id)           TABLESPACE ts_indices;

-- Compuesto: acelera el conteo del dashboard (tickets activos/listos por sucursal).
CREATE INDEX IF NOT EXISTS idx_tickets_branch_status   ON tickets(branch_id, status)   TABLESPACE ts_indices;
