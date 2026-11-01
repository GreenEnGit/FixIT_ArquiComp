# E10 — Instrucciones Operativas para Claude Code (`FixIT_ArquiComp` — SCB-1001)

## 1. Resumen del Proyecto
Eres el Arquitecto de Bases de Datos y Agente de Ingeniería encargado de evolucionar el proyecto **`FixIT_ArquiComp`** (sistema de gestión de taller de reparación e inventario en Python/FastAPI + SQLite) hacia una arquitectura transaccional distribuida sobre **PostgreSQL 16.4** contenedorizada con **Podman 4.9.3** en Linux Mint 22, cumpliendo el 100 % del temario oficial **Administración de Base de Datos (SCB-1001)** del TecNM y generando evidencia visual automatizada (capturas `.png` de terminal, capturas `.png` de la interfaz web y diagramas `.png` renderizados).

## 2. Stack Tecnológico y Versiones Oficiales
* **SO Host:** Linux Mint 22 (x86_64)
* **Orquestación:** `Podman 4.9.3` y `podman-compose 1.0.6`
* **SGBD Principal (Maestro y Réplica):** `PostgreSQL 16.4` (`docker.io/library/postgres:16.4-bookworm`)
* **SGBD Origen de Migración (U5.T5.S5):** `SQLite 3.45.1` (archivo `taller_prototipo.db`)
* **Lenguaje y Paquetes Python:** `Python 3.12.3`, `fastapi==0.115.0`, `uvicorn==0.31.0`, `psycopg[binary,pool]==3.2.2`, `python-dotenv==1.0.1`, `Faker==30.1.0`, `pytest==8.3.3`, `jinja2==3.1.4`, `playwright==1.48.0`
* **Compilador de Diagramas a Imagen:** `@mermaid-js/mermaid-cli 11.2.0` (`mmdc`)
* **Top 5 Plugins/MCP Activos:** `Playwright MCP`, `Headroom`, `MemPalace`, `Graphify`, `Ponytail`

## 3. Orden Obligatorio de Lectura de Documentos
Al iniciar sesión, lee en este orden exacto:
1. `docs/01_temario_extraido.md` y `docs/02_definicion_proyecto.md`
2. `docs/03_requisitos.md` y `docs/04_matriz_trazabilidad.md`
3. `docs/05_seleccion_tecnologica.md` y `docs/06_arquitectura_y_datos.md`
4. `docs/07_plan_documentacion.md`, `docs/08_plan_implementacion.md` y `docs/09_plan_pruebas.md`
5. El grafo de `./graphify-out/` y los archivos actuales `database.py`, `main.py` y `routers/`.

## 4. Directriz Crítica: Capturas de Pantalla (`.png`) y Diagramas Automatizados
Tienes **obligación estricta** de documentar visualmente todo lo que construyas y ejecutes:
1. **Capturas de Terminal (`evidencias/capturas/terminal/*.png`):** En `infra/scripts/capture_evidence.py`, utiliza **Playwright (`playwright==1.48.0`)** para ejecutar cada comando de verificación de las 11 prácticas (`podman`, `psql`, `ops_modes.sh`, `reindex.sh`, `backup_job.sh`, `restore_pitr.sh`, `migrate_sqlite_to_pg.py`, `toggle_audit.sh`, `monitor_resources.sh`, `pytest`), envolver la salida real (incluyendo el comando, fecha/hora y respuesta tabular del SGBD) en una plantilla HTML de ventana de terminal Linux oscura con fuente monoespaciada (`Fira Code` / `monospace`) y tomar una captura `.png` de alta resolución (`device_scale_factor=2`).
2. **Capturas de la Aplicación Web FixIT (`evidencias/capturas/ui/*.png`):** Levanta temporalmente `uvicorn main:app --port 8000` y usa Playwright (vía script o Playwright MCP) para navegar por la interfaz de FixIT conectada a PostgreSQL 16.4 y guardar `UI_01_login_y_dashboard.png`, `UI_02_tickets_migrados.png`, `UI_03_inventario_refacciones.png` y `UI_04_vista_auditoria_pagos.png`.
3. **Diagramas de Arquitectura y Datos (`evidencias/diagramas/*.png`):** Extrae los 4 bloques Mermaid de `docs/06_arquitectura_y_datos.md` a archivos `.mmd` y compílalos a `.png` de alta resolución usando `mmdc -i archivo.mmd -o archivo.png -w 1600 -b white` (o renderizándolos con Playwright si `mmdc` requiere flags de sandbox `--puppeteerConfigFile`).
4. **Persistencia en Memoria y Git:** Registra el progreso de cada fase en **MemPalace** y haz `git add` incluyendo la carpeta `evidencias/` para que todas las capturas `.png` y diagramas se suban a GitHub y se visualicen directamente al abrir los manuales `.md`.

## 5. Comandos de Construcción, Ejecución, Captura y Prueba
* **Aprovisionar entorno y contenedor maestro:** `bash infra/scripts/init_env.sh`
* **Migrar datos desde SQLite (`taller_prototipo.db`):** `python3 infra/scripts/migrate_sqlite_to_pg.py --verify`
* **Inyectar carga sintética:** `python3 src/data_generator/seed_workload.py --rows 10000`
* **Levantar nodo réplica (Streaming Replication):** `bash infra/scripts/setup_replication.sh`
* **Controlar modos de operación y logs:** `bash infra/scripts/ops_modes.sh [start|stop|status|recovery|normal|logs]`
* **Reorganizar y reconstruir índices:** `bash infra/scripts/reindex.sh`
* **Ejecutar respaldos físicos y lógicos:** `bash infra/scripts/backup_job.sh`
* **Restaurar a punto en el tiempo (PITR):** `bash infra/scripts/restore_pitr.sh "<YYYY-MM-DD HH:MM:SS>"`
* **Activar/Desactivar auditoría dinámica:** `bash infra/scripts/toggle_audit.sh [on|off|status]`
* **Monitorear rendimiento y recursos:** `bash infra/scripts/monitor_resources.sh`
* **Generar todos los diagramas y capturas `.png`:** `python3 infra/scripts/capture_evidence.py --all`
* **Correr suite completa de validación académica:** `pytest -v tests/test_dba_scb1001.py`

## 6. Definición de Terminado (Definition of Done)
El proyecto está terminado únicamente cuando:
1. Los contenedores `fixit_pg_master` (:5432) y `fixit_pg_replica` (:5433) operan en Podman con *Streaming Replication* activa.
2. Las ~20 tablas de FixIT están distribuidas en los 4 tablespaces (`ts_catalogos`, `ts_transaccional`, `ts_auditoria`, `ts_indices`) con los datos migrados desde `taller_prototipo.db`.
3. Todas las capturas `.png` de terminal (`P01` a `P12`), capturas `.png` de interfaz web (`UI_01` a `UI_04`) y diagramas `.png` (`D01` a `D04`) existen en `evidencias/` y están incrustados en los 6 documentos de `docs/07_plan_documentacion.md`.
4. `pytest -v tests/test_dba_scb1001.py` aprueba el 100 % de los casos `CP-01` a `CP-10`.
