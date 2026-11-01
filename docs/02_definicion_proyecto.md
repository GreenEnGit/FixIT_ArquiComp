# E02 — Definición del Proyecto Integrador

## 1. Nombre y Dominio del Proyecto
* **Nombre del Proyecto:** FixIT Enterprise DBA (`FixIT_ArquiComp` — Evolución a Clúster Transaccional PostgreSQL 16.4 con Generación Automatizada de Evidencias Visuales para SCB-1001).
* **Dominio de Negocio:** Gestión integral de talleres de reparación de hardware y computación, órdenes de servicio (`tickets`), control de inventario de refacciones (`inventory`), punto de venta (`payments`), garantías y auditoría transaccional (`audit_logs`).
* **Repositorio Base:** `[https://github.com/GreenEnGit/FixIT_ArquiComp](https://github.com/GreenEnGit/FixIT_ArquiComp)`

## 2. Evaluación Comparativa de Dominios Candidatos
| Dominio Evaluado | Ventajas para el Temario SCB-1001 | Limitaciones | Decisión |
| :--- | :--- | :--- | :---: |
| **1. FixIT (`FixIT_ArquiComp` - Taller de Reparación e Inventario)** | Aplicación real en FastAPI (`main.py`) con interfaz web navegable para capturas con Playwright, ~20 tablas relacionales en SQL puro (`database.py`), base de datos SQLite poblada (`taller_prototipo.db`) ideal para la práctica de migración (Subtema 5.5)[cite: 5, 9] y tabla `audit_logs` nativa (Subtema 6.2)[cite: 5, 9]. | Requiere estandarizar las consultas SQL de dialecto SQLite a PostgreSQL 16.4. | **ELEGIDO** |
| **2. Sistema de Control Escolar** | Entidades académicas conocidas. | Baja contención de escritura en inventarios y sin base legacy propia para migrar. | Descartado |
| **3. Catálogo E-Commerce Sintético** | Fácil de poblar con datos falsos. | No demuestra evolución de un sistema real del estudiante ni posee interfaz operativa previa. | Descartado |

## 3. Planteamiento del Problema
El sistema **FixIT** (`FixIT_ArquiComp`) opera originalmente sobre un archivo local de **SQLite 3** (`taller_prototipo.db`). Esta arquitectura impide cumplir con las exigencias de producción de una organización: carece de separación física de objetos en múltiples *tablespaces*[cite: 5, 7], no dispone de roles ni cuotas de disco a nivel de motor SGBD[cite: 5, 7], no soporta espejeo ni replicación maestro-esclavo en tiempo real[cite: 5, 8], carece de recuperación a un punto en el tiempo (*PITR*) basada en archivos log transaccionales (`WAL`)[cite: 5, 8, 9] y no genera evidencia visual automatizada (capturas `.png` de terminal, vistas web y diagramas de arquitectura) que acredite de forma auditable cada operación del Administrador de Base de Datos (DBA)[cite: 5, 6, 10].

## 4. Objetivo General
Reingenierizar, desplegar y documentar la capa de persistencia y administración del sistema **FixIT** migrando de SQLite 3.45.1 a un clúster contenedorizado de **PostgreSQL 16.4** bajo **Podman 4.9.3** en Linux Mint, cubriendo el 100 % de los temas y las 11 prácticas oficiales de **Administración de Base de Datos (SCB-1001)** y generando de manera automatizada las capturas de pantalla (`.png`) de terminal, vistas de la aplicación web y diagramas de arquitectura renderizados[cite: 1, 4, 5, 10].

## 5. Objetivos Específicos
1. **Fundamentación y Arquitectura (Unidades 1 y 2):** Documentar las funciones del DBA y la matriz de selección de SGBD, e instalar PostgreSQL 16.4 en modo transaccional mediante Podman, capturando en imágenes `.png` la arquitectura de memoria, procesos, estructura física y comandos de alta y baja[cite: 5, 6, 10].
2. **Espacio en Disco, Objetos, Roles y Cuotas (Unidad 3):** Segregar las ~20 tablas e índices de FixIT en cuatro *tablespaces* físicos (`ts_catalogos`, `ts_transaccional`, `ts_auditoria`, `ts_indices`), implementando roles RBAC y cuotas límite de almacenamiento por usuario con capturas verificables del bloqueo por exceso de cuota[cite: 5, 7, 10].
3. **Operación, Logs, Modos e Índices (Unidad 4):** Configurar archivos log y registros `WAL`, automatizar la transición entre modos de operación (`alta`, `baja`, `recovery`) y programar la reorganización y reconstrucción periódica de índices (`REINDEX`), capturando en `.png` los planes de ejecución y las bitácoras del motor[cite: 5, 7, 8, 10].
4. **Seguridad, Espejeo, Réplica, Respaldo, Recuperación y Migración (Unidad 5):** Migrar íntegramente `taller_prototipo.db` (SQLite) hacia PostgreSQL 16.4, levantar un nodo secundario en *Streaming Replication*, automatizar respaldos físicos/lógicos y demostrar una recuperación *Point-In-Time Recovery (PITR)* con capturas de antes, durante y después del desastre[cite: 5, 8, 9, 10].
5. **Monitoreo, Auditoría y Documentación Visual (Unidad 6):** Instrumentar el monitoreo de recursos con `pg_stat_statements`, implementar triggers de auditoría dinámica sobre `audit_logs` (activar, verificar y desactivar) y compilar todos los diagramas y capturas `.png` de terminal y de la interfaz FastAPI con Playwright y Mermaid CLI[cite: 5, 9, 10].

## 6. Alcance y Exclusiones
* **Alcance:** Clúster Podman (`fixit_pg_master` y `fixit_pg_replica`), scripts SQL (`01` a `05`), refactorización de `database.py` a `psycopg 3.2.2`, ETL de migración SQLite -> PostgreSQL, generador de carga (`Faker 30.1.0`), motor de capturas y diagramas (`capture_evidence.py` con `Playwright 1.48.0` y `mmdc 11.2.0`), suite `pytest 8.3.3` y los 6 documentos académicos ilustrados.
* **Exclusiones:** No se alterará el diseño estético de las plantillas Jinja2 existentes más allá de asegurar su correcta visualización y captura sobre PostgreSQL 16.4.

## 7. Supuestos Normativos Adoptados
1. **Doble SGBD en el laboratorio:** Se utilizan de forma activa **SQLite 3.45.1** (`taller_prototipo.db`) y **PostgreSQL 16.4** (`fixit_db`), cumpliendo el requisito oficial de emplear al menos dos SGBD en el laboratorio[cite: 2].
2. **Identificación del subtema 3.4 duplicado:** Los dos subtemas numerados como `3.4` en el PDF oficial ("3.4. Espacios para objetos de la base de datos" y "3.4 Roles")[cite: 5] se distinguen como `U3.T3.S4` y `U3.T3.S5`.
3. **Cuotas de espacio en PostgreSQL (`U3.T3.S3`):** Se implementan de forma determinista mediante la tabla `user_disk_quotas` y el trigger PL/pgSQL `trg_enforce_user_quota` que audita el espacio ocupado por el rol activo y aborta inserciones al superar el límite en bytes[cite: 5, 7].

## 8. Actores y Glosario
* **`admin_sys` (`rol_dba`):** Administrador de Base de Datos (DBA)[cite: 5, 6].
* **`app_tecnico` (`rol_tecnico`):** Técnico de laboratorio con cuota de almacenamiento de 50 MB[cite: 5, 7].
* **`app_recepcion` (`rol_recepcion`):** Personal de mostrador y caja con cuota de almacenamiento de 100 MB[cite: 5, 7].
* **`app_auditor` (`rol_auditor`):** Auditor con acceso exclusivo de solo lectura a `audit_logs` y vistas de monitoreo[cite: 5, 9].
* **`replicator` (`rol_replicacion`):** Rol exclusivo para transmisión de bloques WAL hacia `fixit_pg_replica`[cite: 5, 8].
