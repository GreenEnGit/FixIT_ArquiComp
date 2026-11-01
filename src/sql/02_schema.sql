-- FixIT_ArquiComp — src/sql/02_schema.sql
-- SCB-1001 — T-03: U3.T3.S4 — Migracion de las ~19 tablas reales de
--   database.py (SQLite) hacia PostgreSQL 16.4, distribuidas en los 4
--   tablespaces (ts_catalogos, ts_transaccional, ts_auditoria, ts_indices).
--
-- Criterio de distribucion:
--   ts_catalogos     -> datos maestros / referencia, baja frecuencia de escritura
--   ts_transaccional -> datos operativos del taller (tickets, inventario, pagos...)
--   ts_auditoria     -> bitacora de auditoria
--   ts_indices       -> todos los indices PK/UNIQUE (USING INDEX TABLESPACE)
--
-- Nota de tipos: las columnas de fecha/hora con datos ISO consistentes en el
-- seed original (tickets.date, payments.date, warranties.*_date,
-- purchase_orders.date) se tipan como DATE/TIMESTAMP nativos. La columna
-- appointments.date/time conserva VARCHAR porque el seed legacy almacena
-- valores no normalizados ("Hoy", "Mañana", "10:00 AM"); su normalizacion a
-- tipos de fecha reales queda a cargo del ETL de migracion (T-05).

-- =====================================================================
-- TABLESPACE: ts_catalogos
-- =====================================================================

CREATE TABLE branches (
    id          VARCHAR(20)   PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    name        VARCHAR(100)  NOT NULL,
    tax_rate    NUMERIC(5,4)  NOT NULL DEFAULT 0.16
) TABLESPACE ts_catalogos;

CREATE TABLE users (
    id              INTEGER GENERATED ALWAYS AS IDENTITY
                        PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    username        VARCHAR(50)   NOT NULL UNIQUE USING INDEX TABLESPACE ts_indices,
    password_hash   VARCHAR(255)  NOT NULL,
    role            VARCHAR(20)   NOT NULL,
    branch_id       VARCHAR(20)   REFERENCES branches(id)
) TABLESPACE ts_catalogos;

CREATE TABLE customers (
    id      VARCHAR(20)   PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    name    VARCHAR(100)  NOT NULL,
    phone   VARCHAR(20),
    email   VARCHAR(100),
    address VARCHAR(200)
) TABLESPACE ts_catalogos;

CREATE TABLE vendors (
    id      VARCHAR(20)  PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    name    VARCHAR(100) NOT NULL,
    contact VARCHAR(100)
) TABLESPACE ts_catalogos;

CREATE TABLE knowledge_base (
    id          INTEGER GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    title       VARCHAR(200) NOT NULL,
    keywords    TEXT         NOT NULL,
    content     TEXT         NOT NULL,
    category    VARCHAR(50)  NOT NULL DEFAULT 'General'
) TABLESPACE ts_catalogos;

-- =====================================================================
-- TABLESPACE: ts_transaccional
-- =====================================================================

CREATE TABLE inventory (
    id          VARCHAR(30)   PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    name        VARCHAR(150)  NOT NULL,
    brand       VARCHAR(80)   NOT NULL,
    category    VARCHAR(50)   NOT NULL,
    specs       JSONB,
    stock       INTEGER       NOT NULL CHECK (stock >= 0),
    cost        NUMERIC(10,2) NOT NULL,
    price       NUMERIC(10,2) NOT NULL,
    branch_id   VARCHAR(20)   NOT NULL REFERENCES branches(id)
) TABLESPACE ts_transaccional;

CREATE TABLE purchase_orders (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    vendor_id   VARCHAR(20)  NOT NULL REFERENCES vendors(id),
    part_id     VARCHAR(30)  NOT NULL REFERENCES inventory(id),
    qty         INTEGER      NOT NULL CHECK (qty > 0),
    status      VARCHAR(30)  NOT NULL,
    date        DATE         NOT NULL
) TABLESPACE ts_transaccional;

CREATE TABLE customer_devices (
    id              VARCHAR(30)  PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    customer_id     VARCHAR(20)  REFERENCES customers(id),
    type            VARCHAR(30),
    model           VARCHAR(100),
    serial_number   VARCHAR(100),
    condition       TEXT,
    password        VARCHAR(100),
    branch_id       VARCHAR(20)  REFERENCES branches(id)
) TABLESPACE ts_transaccional;

CREATE TABLE tickets (
    id          VARCHAR(20)   PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    status      VARCHAR(30)   NOT NULL,
    customer_id VARCHAR(20)   NOT NULL REFERENCES customers(id),
    device_id   VARCHAR(30)   NOT NULL REFERENCES customer_devices(id),
    symptom     TEXT          NOT NULL,
    date        DATE          NOT NULL,
    labor_cost  NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    branch_id   VARCHAR(20)   NOT NULL REFERENCES branches(id)
) TABLESPACE ts_transaccional;

CREATE TABLE ticket_parts (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    ticket_id   VARCHAR(20)   NOT NULL REFERENCES tickets(id),
    part_id     VARCHAR(30)   NOT NULL REFERENCES inventory(id),
    name        VARCHAR(150)  NOT NULL,
    qty         INTEGER       NOT NULL CHECK (qty > 0),
    cost        NUMERIC(10,2) NOT NULL,
    price       NUMERIC(10,2) NOT NULL
) TABLESPACE ts_transaccional;

CREATE TABLE payments (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    ticket_id   VARCHAR(20)   NOT NULL REFERENCES tickets(id),
    amount      NUMERIC(10,2) NOT NULL CHECK (amount > 0),
    method      VARCHAR(30)   NOT NULL,
    date        DATE          NOT NULL
) TABLESPACE ts_transaccional;

CREATE TABLE warranties (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    ticket_id   VARCHAR(20) NOT NULL REFERENCES tickets(id),
    start_date  DATE        NOT NULL,
    end_date    DATE        NOT NULL,
    notes       TEXT
) TABLESPACE ts_transaccional;

CREATE TABLE loaners (
    id          VARCHAR(20)  PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    type        VARCHAR(30)  NOT NULL,
    model       VARCHAR(100) NOT NULL,
    status      VARCHAR(20)  NOT NULL,
    branch_id   VARCHAR(20)  NOT NULL REFERENCES branches(id)
) TABLESPACE ts_transaccional;

CREATE TABLE appointments (
    id              BIGINT GENERATED ALWAYS AS IDENTITY
                        PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    customer_name   VARCHAR(100) NOT NULL,
    service         VARCHAR(150) NOT NULL,
    date            VARCHAR(20)  NOT NULL,
    time            VARCHAR(20)  NOT NULL,
    status          VARCHAR(30)  NOT NULL,
    branch_id       VARCHAR(20)  NOT NULL REFERENCES branches(id)
) TABLESPACE ts_transaccional;

CREATE TABLE activities (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    ticket_id   VARCHAR(20) NOT NULL REFERENCES tickets(id),
    action      TEXT        NOT NULL,
    time        TIMESTAMP   NOT NULL,
    branch_id   VARCHAR(20) NOT NULL REFERENCES branches(id)
) TABLESPACE ts_transaccional;

CREATE TABLE ticket_images (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    ticket_id   VARCHAR(20)  NOT NULL REFERENCES tickets(id),
    file_path   VARCHAR(255) NOT NULL
) TABLESPACE ts_transaccional;

CREATE TABLE sales (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    total       NUMERIC(10,2) NOT NULL,
    date        TIMESTAMP     NOT NULL,
    branch_id   VARCHAR(20)   NOT NULL REFERENCES branches(id),
    username    VARCHAR(50)   NOT NULL REFERENCES users(username),
    status      VARCHAR(20)   NOT NULL DEFAULT 'COMPLETADA'
) TABLESPACE ts_transaccional;

CREATE TABLE sale_items (
    id          BIGINT GENERATED ALWAYS AS IDENTITY
                    PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    sale_id     BIGINT        NOT NULL REFERENCES sales(id),
    item_id     VARCHAR(30)   NOT NULL REFERENCES inventory(id),
    qty         INTEGER       NOT NULL CHECK (qty > 0),
    price       NUMERIC(10,2) NOT NULL,
    subtotal    NUMERIC(10,2) NOT NULL
) TABLESPACE ts_transaccional;

-- =====================================================================
-- TABLESPACE: ts_auditoria
-- =====================================================================

CREATE TABLE audit_logs (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY
                            PRIMARY KEY USING INDEX TABLESPACE ts_indices,
    username            VARCHAR(50)   NOT NULL,
    action              VARCHAR(50)   NOT NULL,
    item_id             VARCHAR(30),
    details             TEXT,
    monetary_impact     NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    date                TIMESTAMP     NOT NULL,
    branch_id           VARCHAR(20)   NOT NULL REFERENCES branches(id)
) TABLESPACE ts_auditoria;

-- =====================================================================
-- Indices secundarios de apoyo a consultas frecuentes (equivalentes a los
-- indices de rendimiento ya existentes en database.py), todos en ts_indices.
-- =====================================================================

CREATE INDEX idx_tickets_branch        ON tickets(branch_id)            TABLESPACE ts_indices;
CREATE INDEX idx_tickets_status        ON tickets(status)               TABLESPACE ts_indices;
CREATE INDEX idx_tickets_customer      ON tickets(customer_id)          TABLESPACE ts_indices;
CREATE INDEX idx_tickets_date          ON tickets(date)                 TABLESPACE ts_indices;
CREATE INDEX idx_ticket_parts_ticket   ON ticket_parts(ticket_id)       TABLESPACE ts_indices;
CREATE INDEX idx_inventory_branch      ON inventory(branch_id)          TABLESPACE ts_indices;
CREATE INDEX idx_payments_ticket       ON payments(ticket_id)           TABLESPACE ts_indices;
CREATE INDEX idx_activities_ticket     ON activities(ticket_id)         TABLESPACE ts_indices;
CREATE INDEX idx_audit_logs_branch_date ON audit_logs(branch_id, date)  TABLESPACE ts_indices;
CREATE INDEX idx_audit_logs_action     ON audit_logs(action)            TABLESPACE ts_indices;
