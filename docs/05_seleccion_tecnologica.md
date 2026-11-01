# E05 — Selección Tecnológica y Matrices de Decisión Ponderada

## 1. Matriz de Decisión Ponderada: Sistema Gestor de Base de Datos (SGBD)

| Criterio de Evaluación | Peso | PostgreSQL 16.4 | MySQL 8.0.39 | SQLite 3.45.1 (Origen en FixIT) |
| :--- | :---: | :---: | :---: | :---: |
| **Cobertura Nativa del Temario SCB-1001** (Tablespaces, Roles, WAL/PITR, Reindex, Réplica)[cite: 5] | 35 % | 10.0 | 8.0 | 2.0 |
| **Monitoreo y Auditoría sin Licencia Comercial** (`pg_stat_statements`, triggers JSONB)[cite: 5, 9] | 20 % | 9.5 | 7.5 | 3.0 |
| **Concurrencia Transaccional y Bloqueos** (MVCC real, `FOR UPDATE`, aislamiento ACID)[cite: 4, 5] | 20 % | 10.0 | 9.0 | 4.0 |
| **Compatibilidad con el Esquema SQL Puro de `FixIT_ArquiComp` (`database.py`)**[cite: 5, 9] | 15 % | 9.0 | 8.5 | 10.0 |
| **Ejecución Rootless en Contenedores Linux y Facilidad de Captura en CLI** | 10 % | 10.0 | 9.0 | 10.0 |
| **PUNTAJE PONDERADO TOTAL** | **100 %** | **9.75** | **8.28** | **4.60** |

* **Decisión Final de SGBD:** **PostgreSQL 16.4** (`postgres:16.4-bookworm`) como motor principal en clúster Maestro-Réplica, manteniendo **SQLite 3.45.1** (`taller_prototipo.db`) como segundo SGBD del laboratorio y fuente de datos real para la práctica de migración del subtema `5.5`[cite: 2, 5, 9, 10].

## 2. Matriz de Decisión Ponderada: Orquestación de Contenedores en Linux Mint

| Criterio de Evaluación | Peso | Podman 4.9.3 + podman-compose 1.0.6 | Docker Engine 27.x | Instalación Directa en Host |
| :--- | :---: | :---: | :---: | :---: |
| **Seguridad Rootless en Máquina Virtual Linux Mint** | 30 % | 10.0 | 7.5 | 5.0 |
| **Simulación de Clúster Maestro-Esclavo en una Misma VM**[cite: 5, 8] | 35 % | 9.5 | 9.5 | 4.0 |
| **Ahorro de RAM en la VM (Sin demonio residente)** | 20 % | 10.0 | 8.0 | 9.5 |
| **Automatización Declarativa con `compose.yaml`** | 15 % | 9.0 | 10.0 | 1.0 |
| **PUNTAJE PONDERADO TOTAL** | **100 %** | **9.68** | **8.68** | **4.95** |

* **Decisión Final de Orquestación:** **Podman 4.9.3** y **`podman-compose 1.0.6`**.

## 3. Matriz de Selección: Automatización de Evidencias Visuales (Capturas y Diagramas) y Agente

| Subsistema | Opciones Evaluadas | Elección Final | Versión Exacta | Justificación Técnica |
| :--- | :--- | :--- | :---: | :--- |
| **Motor de Capturas Web y Terminal (`.png`)** | Playwright Chromium vs Selenium vs Captura Manual | **Playwright (`playwright` + `@playwright/mcp`)** | `1.48.0` | Captura vistas reales de FastAPI (`localhost:8000`) y renderiza salidas ANSI de terminal en imágenes `.png` de alta definición sin intervención humana. |
| **Compilador de Diagramas a Imagen (`.png`/`.svg`)** | `@mermaid-js/mermaid-cli` (`mmdc`) vs Graphviz plano | **Mermaid CLI (`mmdc`)** | `11.2.0` | Convierte los diagramas Mermaid de arquitectura, tablespaces, ER y replicación directamente en archivos `.png` listos para los reportes académicos. |
| **Compresión de Tokens y Memoria del Agente** | Headroom + MemPalace + Graphify + Ponytail | **Stack Top 5 Integrado** | Vigente oct-nov 2026 | Headroom reduce ~50 % el consumo de tokens de logs SQL; MemPalace brinda memoria persistente local; Graphify indexa el AST y Ponytail evita sobreingeniería. |

## 4. Tabla Maestra de Versiones Oficiales (Consistencia Estricta E05 / E06 / E08 / E10)
| Componente | Tecnología | Versión Exacta |
| :--- | :--- | :--- |
| Sistema Operativo Host (VM) | Linux Mint (Base Ubuntu 24.04 LTS) | `22 (Wilma)` |
| Motor de Contenedores | Podman / podman-compose | `4.9.3` / `1.0.6` |
| SGBD Principal (Maestro y Réplica) | PostgreSQL | `16.4` (`postgres:16.4-bookworm`) |
| SGBD Origen de Migración (U5.T5.S5) | SQLite | `3.45.1` |
| Lenguaje de Aplicación y Scripts | Python | `3.12.3` |
| Framework Web y Servidor ASGI | FastAPI / Uvicorn | `0.115.0` / `0.31.0` |
| Conector y Pool PostgreSQL | `psycopg[binary,pool]` | `3.2.2` |
| Generador de Carga y Pruebas | Faker / pytest | `30.1.0` / `8.3.3` |
| Motor de Capturas Automatizadas | Playwright (Python + MCP) | `1.48.0` |
| Compilador de Diagramas a PNG | `@mermaid-js/mermaid-cli` (`mmdc`) | `11.2.0` |
| Plantillas Web y Variables de Entorno | Jinja2 / python-dotenv | `3.1.4` / `1.0.1` |
