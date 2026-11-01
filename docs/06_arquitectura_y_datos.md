# E06 — Arquitectura del Sistema, Modelo de Datos y Pipeline de Diagramas

## 1. Arquitectura de Memoria, Procesos y Despliegue en Contenedores (`D01_arquitectura_memoria_procesos.png` — Unidad 2)

> *Nota para el Agente:* Este diagrama debe exportarse también como archivo independiente `evidencias/diagramas/D01_arquitectura_memoria_procesos.mmd` y compilarse a `evidencias/diagramas/D01_arquitectura_memoria_procesos.png` mediante `mmdc`[cite: 5, 6].

```mermaid
graph TB
    subgraph VM["VM Linux Mint 22 — Podman 4.9.3 / Python 3.12.3"]
        subgraph AppLayer["Capa de Aplicación FixIT_ArquiComp y Evidencias"]
            FastAPI["FastAPI 0.115.0 (main.py + routers)\nPool psycopg 3.2.2"]
            ETL["migrate_sqlite_to_pg.py\n& Faker 30.1.0 (seed_workload.py)"]
            Capturer["Playwright 1.48.0 + mmdc 11.2.0\n(capture_evidence.py -> evidencias/*.png)"]
            SQLiteDB[("taller_prototipo.db\nSQLite 3.45.1 (Origen U5.T5.S5)")]
        end

        subgraph PodmanNet["Red Podman: fixit_dba_net"]
            subgraph Master["Contenedor: fixit_pg_master (PostgreSQL 16.4 — Puerto 5432)"]
                PGMem["Memoria: shared_buffers=256MB | work_mem=16MB | wal_buffers=16MB\nProcesos: checkpointer, bgwriter, walwriter, autovacuum, stats collector"]
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
    FastAPI -.->|Lectura Reportes :5433| Replica
    Master ==>|Streaming Replication (WAL)| Replica
    WAL ==>|Archivado Continuo / PITR| Backups
    Capturer -.->|Captura Web :8000 y Terminal :5432| FastAPI
```

## 2. Arquitectura Física de Almacenamiento y Tablespaces (`D02_distribucion_tablespaces.png` — Unidad 3)

> *Nota para el Agente:* Exportar y compilar también en `evidencias/diagramas/D02_distribucion_tablespaces.png`[cite: 5, 7].

```mermaid
graph LR
    DB[("Base de Datos: fixit_db\n(PostgreSQL 16.4)")]
    DB --> TS_CAT["Tablespace: ts_catalogos\n/var/lib/postgresql/tablespaces/ts_catalogos\nTablas: branches, users, customers,\ncustomer_devices, suppliers, categories,\nservice_catalog, kb_articles,\nwarranty_policies, system_settings"]
    DB --> TS_TRX["Tablespace: ts_transaccional\n/var/lib/postgresql/tablespaces/ts_transaccional\nTablas: tickets, ticket_parts,\nticket_status_history, inventory,\ninventory_movements, purchase_orders,\npurchase_order_items, payments,\ncash_register_sessions, warranties"]
    DB --> TS_AUD["Tablespace: ts_auditoria\n/var/lib/postgresql/tablespaces/ts_auditoria\nTablas: audit_logs,\nuser_disk_quotas, backup_history"]
    DB --> TS_IDX["Tablespace: ts_indices\n/var/lib/postgresql/tablespaces/ts_indices\nObjetos: Todos los índices B-Tree\nsecundarios del esquema public"]
```

## 3. Modelo Relacional Físico Normalizado en 3FN (`D03_modelo_relacional_3fn.png` — Unidad 3)

> *Nota para el Agente:* Exportar y compilar también en `evidencias/diagramas/D03_modelo_relacional_3fn.png`[cite: 5, 7].

```mermaid
erDiagram
    branches ||--o{ users : "emplea"
    branches ||--o{ tickets : "opera"
    branches ||--o{ inventory : "almacena"
    customers ||--o{ customer_devices : "posee"
    customers ||--o{ tickets : "solicita"
    customer_devices ||--o{ tickets : "ingresa_en"
    users ||--o{ tickets : "atiende"
    tickets ||--o{ ticket_parts : "consume"
    tickets ||--o{ ticket_status_history : "registra"
    tickets ||--o{ payments : "liquida"
    tickets ||--o| warranties : "ampara"
    inventory ||--o{ ticket_parts : "suministra"
    inventory ||--o{ inventory_movements : "mueve"
    users ||--o{ audit_logs : "ejecuta"

    branches {
        int id PK
        varchar name
        varchar address
        varchar phone
        boolean is_active
    }
    users {
        int id PK
        int branch_id FK
        varchar username UK
        varchar password_hash
        varchar role
        boolean is_active
    }
    customers {
        int id PK
        varchar full_name
        varchar phone
        varchar email
        timestamptz created_at
    }
    customer_devices {
        int id PK
        int customer_id FK
        varchar device_type
        varchar brand
        varchar model
        varchar serial_number
    }
    tickets {
        int id PK
        int branch_id FK
        int customer_id FK
        int device_id FK
        int assigned_tech_id FK
        varchar status
        text problem_description
        text diagnosis
        numeric estimated_cost
        numeric final_cost
        timestamptz created_at
        timestamptz updated_at
    }
    inventory {
        int id PK
        int branch_id FK
        varchar sku UK
        varchar part_name
        int stock
        int min_stock
        numeric unit_cost
        numeric sale_price
    }
    ticket_parts {
        int id PK
        int ticket_id FK
        int part_id FK
        int quantity
        numeric unit_price
    }
    payments {
        int id PK
        int ticket_id FK
        int received_by FK
        numeric amount
        varchar payment_method
        timestamptz paid_at
    }
    audit_logs {
        bigint id PK
        varchar db_user
        int app_user_id
        varchar table_name
        varchar operation
        varchar record_id
        jsonb old_data
        jsonb new_data
        inet client_ip
        timestamptz created_at
    }
```

## 4. Topología de Espejeo, Réplica, Respaldo y Recuperación PITR (`D04_topologia_replicacion_pitr.png` — Unidad 5)

> *Nota para el Agente:* Exportar y compilar también en `evidencias/diagramas/D04_topologia_replicacion_pitr.png`[cite: 5, 8, 9].

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
| `rol_dba` | `admin_sys` | `SUPERUSER`, control total de instancia, tablespaces, respaldos y auditoría. | Ilimitada | Control administrativo directo[cite: 5, 6]. |
| `rol_tecnico` | `app_tecnico` | `SELECT` en catálogos; `INSERT, UPDATE` en `tickets`, `ticket_parts`, `ticket_status_history`; `UPDATE (stock)` en `inventory`. Sin permiso de `DELETE` ni acceso a `payments`. | **50 MB** (`52428800` bytes) | Trigger `trg_enforce_user_quota` aborta inserciones si el espacio atribuido supera `max_bytes`[cite: 5, 7]. |
| `rol_recepcion` | `app_recepcion` | `SELECT, INSERT, UPDATE` en `customers`, `customer_devices`, `tickets`; `SELECT, INSERT` en `payments`. Sin permiso de `DELETE`. | **100 MB** (`104857600` bytes) | Trigger `trg_enforce_user_quota` activo sobre tablas de recepción y caja[cite: 5, 7]. |
| `rol_auditor` | `app_auditor` | `SELECT` exclusivo sobre `audit_logs`, `pg_stat_statements` y vistas de catálogo (`default_transaction_read_only = on`). | **0 MB** (Solo lectura) | Bloqueo nativo de escritura a nivel de rol[cite: 5, 9]. |
| `rol_replicacion` | `replicator` | `REPLICATION LOGIN` para streaming WAL hacia `fixit_pg_replica`. | N/A | Restringido por subred en `pg_hba.conf`[cite: 5, 8]. |
