# E06 — Arquitectura del Sistema, Modelo de Datos y Pipeline de Diagramas

## 1. Arquitectura de Memoria, Procesos y Despliegue en Contenedores (`D01_arquitectura_memoria_procesos.png` — Unidad 2)

> *Nota:* Este diagrama se exporta también como archivo independiente `evidencias/diagramas/D01_arquitectura_memoria_procesos.mmd` y se compila a `evidencias/diagramas/D01_arquitectura_memoria_procesos.png` mediante `mmdc`.

```mermaid
graph TB
    subgraph VM["VM Linux Mint 22 — Podman 4.9.3 / Python 3.12.3"]
        subgraph AppLayer["Capa de Aplicación FixIT_ArquiComp y Evidencias"]
            FastAPI["FastAPI 0.115.0 + Uvicorn 0.31.0 (main.py + routers)\nhttp://fixittester.com (:80, servicio systemd)\npsycopg 3.2.2"]
            ETL["migrate_sqlite_to_pg.py\n& Faker 30.1.0 (seed_workload.py)"]
            Capturer["Playwright 1.48.0 + mmdc 11.2.0\n(capture_evidence.py -> evidencias/*.png)"]
            SQLiteDB[("taller_prototipo.db\nSQLite 3.45.1 (Origen U5.T5.S5)")]
        end

        subgraph PodmanNet["Red Podman: fixit_dba_net"]
            subgraph Master["Contenedor: fixit_pg_master (PostgreSQL 16.4 — Puerto 5432)"]
                PGMem["Memoria: shared_buffers=256MB | work_mem=16MB | wal_buffers=16MB\nProcesos: checkpointer, background writer, walwriter,\nautovacuum launcher, archiver, logger, walsender"]
                TS1[("ts_catalogos")]
                TS2[("ts_transaccional")]
                TS3[("ts_auditoria")]
                TS4[("ts_indices")]
                WAL[("pg_wal & wal_archive")]
            end

            subgraph Replica["Contenedor: fixit_pg_replica (PostgreSQL 16.4 Standby — Puerto 5433)"]
                RepProc["Procesos: walreceiver & startup (Hot Standby Read-Only)"]
                RepDisk[("Espejo Físico de Tablespaces")]
            end
        end

        Backups[("Volumen Host: ./backups\npg_dump (.dump) & pg_basebackup (.tar.gz)")]
    end

    SQLiteDB -->|Extracción ETL| ETL
    ETL -->|Carga Transaccional| Master
    FastAPI -->|Lectura/Escritura ACID :5432| Master
    DBA["DBA (psql)"] -.->|Consultas de solo lectura :5433| Replica
    Master ==>|Streaming Replication WAL| Replica
    WAL ==>|Archivado Continuo / PITR| Backups
    Capturer -.->|Captura Web :8000 y Terminal :5432| FastAPI
```

## 2. Arquitectura Física de Almacenamiento y Tablespaces (`D02_distribucion_tablespaces.png` — Unidad 3)

> *Nota:* Compilado también en `evidencias/diagramas/D02_distribucion_tablespaces.png`.

```mermaid
graph LR
    DB[("Base de Datos: fixit_db\n(PostgreSQL 16.4)")]
    DB --> TS_CATALOGOS["Tablespace: ts_catalogos\n/var/lib/postgresql/tablespaces/ts_catalogos\n6 tablas:\nbranches, customers, knowledge_base\nproducts, users, vendors"]
    DB --> TS_TRANSACCIONAL["Tablespace: ts_transaccional\n/var/lib/postgresql/tablespaces/ts_transaccional\n13 tablas:\nactivities, appointments, customer_devices\ninventory, loaners, payments\npurchase_orders, sale_items, sales\nticket_images, ticket_parts, tickets\nwarranties"]
    DB --> TS_AUDITORIA["Tablespace: ts_auditoria\n/var/lib/postgresql/tablespaces/ts_auditoria\n2 tablas:\naudit_logs, user_disk_quotas"]
    DB --> TS_INDICES["Tablespace: ts_indices\n/var/lib/postgresql/tablespaces/ts_indices\n46 índices (PK, UNIQUE y B-Tree secundarios)"]
```

## 3. Modelo Relacional Físico Normalizado en 3FN (`D03_modelo_relacional_3fn.png` — Unidad 3)

> *Nota:* Compilado también en `evidencias/diagramas/D03_modelo_relacional_3fn.png`.

```mermaid
erDiagram
    branches ||--o{ activities : "branch_id"
    branches ||--o{ appointments : "branch_id"
    branches ||--o{ audit_logs : "branch_id"
    branches ||--o{ customer_devices : "branch_id"
    branches ||--o{ inventory : "branch_id"
    branches ||--o{ loaners : "branch_id"
    branches ||--o{ sales : "branch_id"
    branches ||--o{ tickets : "branch_id"
    branches ||--o{ users : "branch_id"
    customer_devices ||--o{ tickets : "device_id"
    customers ||--o{ customer_devices : "customer_id"
    customers ||--o{ tickets : "customer_id"
    products ||--o{ inventory : "id"
    products ||--o{ purchase_orders : "part_id"
    products ||--o{ sale_items : "item_id"
    products ||--o{ ticket_parts : "part_id"
    sales ||--o{ sale_items : "sale_id"
    tickets ||--o{ activities : "ticket_id"
    tickets ||--o{ payments : "ticket_id"
    tickets ||--o{ ticket_images : "ticket_id"
    tickets ||--o{ ticket_parts : "ticket_id"
    tickets ||--o{ warranties : "ticket_id"
    users ||--o{ sales : "username"
    vendors ||--o{ purchase_orders : "vendor_id"
    activities {
        bigint id PK
        varchar ticket_id FK
        text action
        timestamp time
        varchar branch_id FK
    }
    appointments {
        bigint id PK
        varchar customer_name
        varchar service
        date date
        time time
        varchar status
        varchar branch_id FK
    }
    audit_logs {
        bigint id PK
        varchar username
        varchar action
        varchar item_id
        text details
        numeric monetary_impact
        timestamp date
        varchar branch_id FK
        jsonb old_data
        jsonb new_data
    }
    branches {
        varchar id PK
        varchar name
        numeric tax_rate
    }
    customer_devices {
        varchar id PK
        varchar customer_id FK
        varchar type
        varchar model
        varchar serial_number
        text condition
        bytea password
        varchar branch_id FK
    }
    customers {
        varchar id PK
        varchar name
        varchar phone
        varchar email
        varchar address
    }
    inventory {
        varchar id PK, FK
        int stock
        numeric cost
        numeric price
        varchar branch_id PK, FK
    }
    knowledge_base {
        int id PK
        varchar title
        text keywords
        text content
        varchar category
    }
    loaners {
        varchar id PK
        varchar type
        varchar model
        varchar status
        varchar branch_id FK
    }
    payments {
        bigint id PK
        varchar ticket_id FK
        numeric amount
        varchar method
        date date
    }
    products {
        varchar id PK
        varchar name
        varchar brand
        varchar category
        jsonb specs
        varchar image_path
    }
    purchase_orders {
        bigint id PK
        varchar vendor_id FK
        varchar part_id FK
        int qty
        varchar status
        date date
    }
    sale_items {
        bigint id PK
        bigint sale_id FK
        varchar item_id FK
        int qty
        numeric price
        numeric subtotal
    }
    sales {
        bigint id PK
        numeric total
        timestamp date
        varchar branch_id FK
        varchar username FK
        text status
    }
    ticket_images {
        bigint id PK
        varchar ticket_id FK
        varchar file_path
    }
    ticket_parts {
        bigint id PK
        varchar ticket_id FK
        varchar part_id FK
        varchar name
        int qty
        numeric cost
        numeric price
    }
    tickets {
        varchar id PK
        varchar status
        varchar customer_id FK
        varchar device_id FK
        text symptom
        date date
        numeric labor_cost
        varchar branch_id FK
    }
    user_disk_quotas {
        varchar role_name PK
        bigint max_bytes
        bigint used_bytes
        timestamp_with_time_zone updated_at
    }
    users {
        int id PK
        varchar username UK
        varchar password_hash
        varchar role
        varchar branch_id FK
    }
    vendors {
        varchar id PK
        varchar name
        varchar contact
    }
    warranties {
        bigint id PK
        varchar ticket_id FK
        date start_date
        date end_date
        text notes
    }
```

## 4. Topología de Espejeo, Réplica, Respaldo y Recuperación PITR (`D04_topologia_replicacion_pitr.png` — Unidad 5)

> *Nota:* Compilado también en `evidencias/diagramas/D04_topologia_replicacion_pitr.png`.

```mermaid
sequenceDiagram
    participant App as FastAPI FixIT (psycopg 3.2.2)
    participant Master as fixit_pg_master (:5432)
    participant WAL as Archivo WAL (/wal_archive)
    participant Replica as fixit_pg_replica (:5433)
    participant Backup as ./backups (pg_dump & pg_basebackup)

    App->>Master: COMMIT Transacción (INSERT payment / UPDATE ticket)
    Master->>Master: Escribe en pg_wal (Write-Ahead Log)
    par Espejeo y Streaming Replication (U5.1 y U5.2)
        Master->>Replica: Stream WAL continuo (wal_sender -> wal_receiver)
        Replica->>Replica: Aplica bloques en Hot Standby (Read-Only)
    and Archivado y Respaldo (U5.3 y U5.4)
        Master->>WAL: archive_command copia segmento WAL cerrado
        Master->>Backup: backup_job.sh genera basebackup + dump lógico
    end
    Note over Master,WAL: Ante desastre (DROP/DELETE), restore_pitr.sh restaura basebackup y reproduce WAL hasta T_safe
```

## 5. Política de Seguridad: Roles, Usuarios y Cuotas de Espacio (`U3.T3.S3`, `U3.T3.S5`)

| Rol de Base de Datos | Usuario Login | Privilegios Asignados | Cuota Máxima en Disco (`user_disk_quotas`) | Mecanismo de Control |
| :--- | :--- | :--- | :---: | :--- |
| `rol_dba` | `admin_sys` | `SUPERUSER`, control total de instancia, tablespaces, respaldos y auditoría. | Ilimitada | Control administrativo directo. |
| `rol_tecnico` | `app_tecnico` | `SELECT` en catálogos (`branches`, `customers`, `customer_devices`, `vendors`, `knowledge_base`, `products`, `inventory`, `v_inventory`); `INSERT, UPDATE` en `tickets` y `ticket_parts`; `UPDATE (stock)` en `inventory`. Sin permiso de `DELETE` ni acceso a `payments`. | **50 MB** (`52428800` bytes) | Trigger `trg_enforce_user_quota` aborta inserciones si el espacio atribuido supera `max_bytes`. |
| `rol_recepcion` | `app_recepcion` | `SELECT, INSERT, UPDATE` en `customers`, `customer_devices`, `tickets`; `SELECT, INSERT` en `payments`. Sin permiso de `DELETE`. | **100 MB** (`104857600` bytes) | Mismo trigger `trg_enforce_user_quota` (adjunto a `tickets` y `ticket_parts`); la cuota se descuenta por rol. |
| `rol_auditor` | `app_auditor` | `SELECT` exclusivo sobre `audit_logs`, `pg_stat_statements` y vistas de catálogo (`default_transaction_read_only = on`). | **0 MB** (Solo lectura) | Bloqueo nativo de escritura a nivel de rol. |
| `rol_replicacion` | `replicator` | `REPLICATION LOGIN` para streaming WAL hacia `fixit_pg_replica`. | N/A | Restringido por subred en `pg_hba.conf`. |
