# 🛠️ FixIT Enterprise DBA — SCB-1001

![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.4-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Podman](https://img.shields.io/badge/Podman-4.9.3-892CA0?style=for-the-badge&logo=podman&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.12.3-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pruebas](https://img.shields.io/badge/pytest-CP--01_a_CP--11-2ea44f?style=for-the-badge&logo=pytest&logoColor=white)

> [!WARNING]
> **Proyecto exclusivamente académico.** FixIT se desarrolló como proyecto integrador de la asignatura **Administración de Base de Datos (SCB-1001)** del Tecnológico Nacional de México, con fines de aprendizaje y evaluación.
> **No debe usarse, bajo ningún contexto, en entornos de producción reales** ni para gestionar talleres, clientes, pagos o datos personales reales. Las credenciales de laboratorio, la configuración de red, los datos de ejemplo y las decisiones de seguridad están pensados únicamente para una máquina virtual de práctica. Se distribuye "tal cual", sin garantía de ningún tipo; los autores no se hacen responsables de su uso fuera del ámbito académico.

**FixIT** es un sistema de gestión para talleres de reparación de hardware: órdenes de servicio, inventario con fotos, punto de venta, clientes, citas y auditoría. Este repositorio documenta su evolución desde un prototipo sobre **SQLite 3.45.1** hacia un **clúster transaccional PostgreSQL 16.4** (maestro + réplica) contenedorizado con **Podman 4.9.3**, cubriendo el 100 % del temario oficial de **Administración de Base de Datos (SCB-1001)** del TecNM.

Cada operación de DBA (instalación, tablespaces, roles y cuotas, modos de operación, índices, replicación, respaldo y recuperación PITR, migración, cifrado, auditoría y monitoreo) se ejecutó contra el clúster real y quedó documentada con **45 imágenes de evidencia generadas automáticamente** (4 diagramas, 30 capturas de terminal y 11 de la interfaz web).

![Dashboard FixIT sobre PostgreSQL 16.4](evidencias/capturas/ui/UI_01_login_y_dashboard.png)

---

## Índice

1. [Inicio rápido](#inicio-rápido)
2. [Características](#características)
3. [Galería de la aplicación](#galería-de-la-aplicación)
4. [Arquitectura y modelo de datos](#arquitectura-y-modelo-de-datos)
5. [Prácticas SCB-1001 y evidencias](#prácticas-scb-1001-y-evidencias)
6. [Tecnologías y versiones](#tecnologías-y-versiones)
7. [Requisitos](#requisitos)
8. [Instalación paso a paso](#instalación-paso-a-paso)
9. [URLs, puertos y credenciales](#urls-puertos-y-credenciales-de-laboratorio)
10. [Administración de los contenedores](#administración-de-los-contenedores)
11. [Pruebas automatizadas](#pruebas-automatizadas)
12. [Evidencia visual y mantenimiento](#evidencia-visual-y-mantenimiento)
13. [Solución de problemas](#solución-de-problemas-frecuentes)
14. [Estructura del proyecto](#estructura-del-proyecto)
15. [Seguridad](#seguridad)
16. [Manuales del proyecto](#manuales-del-proyecto)
17. [Estado y verificación](#estado-y-verificación)

---

## Inicio rápido

En la máquina virtual del laboratorio todo arranca solo al encenderla (servicios systemd de usuario). Abre en el navegador:

> **http://fixittester.com** — usuario `admin` / contraseña `admin123`

| Usuario | Contraseña | Qué ve |
| :--- | :--- | :--- |
| `admin` | `admin123` | Todo: costos, reportes, auditoría, personal y cambio de sucursal |
| `tecnico_norte` | `tec123` | Su sucursal (Norte), sin costos ni administración |
| `tecnico_centro` | `tec123` | Su sucursal (Centro), sin costos ni administración |

Para instalarlo en otra máquina sigue la [instalación paso a paso](#instalación-paso-a-paso).

## Características

**Taller**
- 🎫 Órdenes de servicio por estados: *Recibido → En diagnóstico → Esperando piezas → En reparación → Listo para entrega → Entregado y pagado*, con historial de movimientos, refacciones, cobro y garantía de 90 días.
- 📥 Recepción rápida de equipos con fotos y **PIN o contraseña de desbloqueo cifrado** (`pgcrypto`), visible en el ticket solo al pulsar *Mostrar*.
- 📅 Agenda de citas (`DATE`/`TIME` nativos, validadas en el servidor) y equipos de préstamo.
- 🌐 Portal público de seguimiento de la reparación para el cliente.

**Tienda**
- 🛒 Punto de venta con fotos: cada clic agrega una unidad, ticket de caja imprimible y reversión con motivo obligatorio.
- 📦 Inventario multi-sucursal en tarjetas o tabla, filtro por categoría, buscador global con miniaturas y 33 productos de ejemplo con foto (créditos en [`static/img/products/CREDITOS.md`](static/img/products/CREDITOS.md)).

**Base de datos**
- 🗂️ Modelo en 3FN: catálogo maestro `products` (en `ts_catalogos`) y existencias, costo y precio por sucursal en `inventory` (PK `id` + `branch_id`), unidos por la vista `v_inventory`.
- 💽 21 tablas repartidas en 4 tablespaces (`ts_catalogos`, `ts_transaccional`, `ts_auditoria`, `ts_indices`).
- 🔐 RBAC con 5 roles y cuotas de espacio por rol aplicadas con triggers PL/pgSQL.
- 🔁 Streaming Replication maestro → réplica, respaldo lógico y físico, y recuperación a un punto en el tiempo (PITR).
- 📊 Auditoría dinámica activable/desactivable con trazas JSONB antes/después y monitoreo con `pg_stat_statements`.

**Seguridad de la aplicación**
- 🛡️ Defensa CSRF por verificación de origen en todas las peticiones que modifican datos.
- 🖼️ Toda imagen subida se valida (firma, estructura, límite anti *decompression bomb*) y se recodifica a WebP sin metadatos; nunca se usa la extensión enviada por el usuario.
- 🔑 `SECRET_KEY` y `DEVICE_DATA_KEY` aleatorias por instalación, generadas por `init_env.sh`.

## Galería de la aplicación

| | |
| :---: | :---: |
| ![Dashboard](evidencias/capturas/ui/UI_01_login_y_dashboard.png)<br>**UI_01** — Dashboard gerencial con indicadores calculados en SQL y menú por áreas con contadores en vivo | ![Tickets](evidencias/capturas/ui/UI_02_tickets_migrados.png)<br>**UI_02** — Órdenes de servicio migradas desde SQLite |
| ![Inventario](evidencias/capturas/ui/UI_03_inventario_refacciones.png)<br>**UI_03** — Inventario con fotos, filtros por categoría y vista de tarjetas/tabla | ![Auditoría](evidencias/capturas/ui/UI_04_vista_auditoria_pagos.png)<br>**UI_04** — Auditoría global (solo ADMIN) |
| ![Punto de venta](evidencias/capturas/ui/UI_05_punto_de_venta_fotos.png)<br>**UI_05** — Punto de venta con fotos y caja registradora | ![Detalle de producto](evidencias/capturas/ui/UI_06_detalle_producto_existencias.png)<br>**UI_06** — Detalle de producto con existencias por sucursal |
| ![Recepción](evidencias/capturas/ui/UI_07_recepcion_pin_cifrado.png)<br>**UI_07** — Recepción rápida con PIN de desbloqueo cifrado | ![Ticket](evidencias/capturas/ui/UI_08_ticket_pin_desbloqueo.png)<br>**UI_08** — Ticket con el PIN revelado bajo demanda |
| ![Citas](evidencias/capturas/ui/UI_09_citas_agenda.png)<br>**UI_09** — Agenda de citas y equipos de préstamo | ![Modal de reversión](evidencias/capturas/ui/UI_10_modal_reversion_venta.png)<br>**UI_10** — Reversión de venta con motivo obligatorio |
| ![Vista móvil](evidencias/capturas/ui/UI_11_vista_movil.png)<br>**UI_11** — Vista móvil (390 px) | |

## Arquitectura y modelo de datos

Los diagramas se compilan desde Mermaid (`docs/06_arquitectura_y_datos.md`); D02 y D03 se **generan desde el catálogo real de PostgreSQL** para que nunca se desfasen del esquema.

**D01 — Arquitectura de memoria, procesos y contenedores**

![D01 Arquitectura](evidencias/diagramas/D01_arquitectura_memoria_procesos.png)

**D02 — Distribución de tablas e índices en tablespaces**

![D02 Tablespaces](evidencias/diagramas/D02_distribucion_tablespaces.png)

**D03 — Modelo relacional en 3FN (21 tablas, 24 llaves foráneas)**

![D03 Modelo relacional](evidencias/diagramas/D03_modelo_relacional_3fn.png)

**D04 — Topología de réplica, respaldo y recuperación PITR**

![D04 Réplica y PITR](evidencias/diagramas/D04_topologia_replicacion_pitr.png)

## Prácticas SCB-1001 y evidencias

Todas las capturas de terminal muestran el comando real, la fecha y la respuesta del SGBD. Se generan con `python3 infra/scripts/capture_evidence.py` (ver [evidencia visual](#evidencia-visual-y-mantenimiento)). Despliega cada práctica para verla.

| Práctica | Unidad / tema | Capturas |
| :---: | :--- | :---: |
| P01 | U1–U2 · Instalación transaccional, memoria, procesos, configuración | 9 |
| P02 | U3 · Tablespaces, objetos, roles y cuotas | 4 |
| P03 | U4.3 · Índices, reorganización y reconstrucción | 1 |
| P04–P05 | U4.1–U4.2 · Modos de operación y archivos log | 2 |
| P06 | U5.1–U5.2 · Espejeo y réplica maestro-esclavo | 2 |
| P07–P08 | U5.3–U5.4 · Respaldo y recuperación PITR | 2 |
| P09 | U5.5 · Migración SQLite → PostgreSQL | 1 |
| P10–P11 | U6 · Auditoría dinámica y monitoreo | 3 |
| P12 | Transversal · Suite de pruebas completa | 1 |
| P13 | Mejoras · Modelo 3FN multi-sucursal, cifrado, tipos nativos, seguridad web | 5 |

<details>
<summary><b>Práctica 1 — Instalación y configuración del SGBD (Unidades 1 y 2)</b></summary>

![Versiones de los SGBD](evidencias/capturas/terminal/P01_versiones_sgbd.png)
![Requerimientos del host](evidencias/capturas/terminal/P01_requerimientos_host.png)
![Procedimiento de instalación](evidencias/capturas/terminal/P01_procedimiento_instalacion.png)
![Instalación transaccional](evidencias/capturas/terminal/P01_instalacion_transaccional.png)
![Memoria y procesos](evidencias/capturas/terminal/P01_memoria_y_procesos.png)
![Estructura física en disco](evidencias/capturas/terminal/P01_estructura_fisica_disco.png)
![Variables y archivos de configuración](evidencias/capturas/terminal/P01_variables_y_archivos_conf.png)
![Parámetros configurados](evidencias/capturas/terminal/P01_parametros_configurados.png)
![Comandos de alta y baja](evidencias/capturas/terminal/P01_comandos_alta_baja.png)
</details>

<details>
<summary><b>Práctica 2 — Espacio en disco, roles y cuotas (Unidad 3)</b></summary>

![Creación de tablespaces](evidencias/capturas/terminal/P02_creacion_tablespaces.png)
![Objetos por tablespace](evidencias/capturas/terminal/P02_objetos_por_tablespace.png)
![Roles y privilegios](evidencias/capturas/terminal/P02_roles_y_privilegios.png)
![Cuotas por usuario](evidencias/capturas/terminal/P02_cuotas_limite_usuarios.png)
</details>

<details>
<summary><b>Prácticas 3, 4 y 5 — Índices, modos de operación y logs (Unidad 4)</b></summary>

![Índices y reorganización](evidencias/capturas/terminal/P03_indices_y_reorganizacion.png)
![Modos de operación](evidencias/capturas/terminal/P04_modos_operacion_recovery.png)
![Archivos log y WAL](evidencias/capturas/terminal/P05_verificacion_archivos_log.png)
</details>

<details>
<summary><b>Prácticas 6 a 9 — Espejeo, réplica, respaldo, PITR y migración (Unidad 5)</b></summary>

![Espejeo WAL](evidencias/capturas/terminal/P06_espejeo_wal_receiver.png)
![Réplica maestro-esclavo](evidencias/capturas/terminal/P06_replica_maestro_esclavo.png)
![Respaldo](evidencias/capturas/terminal/P07_respaldo_base_datos.png)
![Recuperación PITR](evidencias/capturas/terminal/P08_recuperacion_datos_pitr.png)
![Migración SQLite a PostgreSQL](evidencias/capturas/terminal/P09_migracion_sqlite_postgres.png)
</details>

<details>
<summary><b>Prácticas 10 y 11 — Auditoría y monitoreo (Unidad 6)</b></summary>

![Activar y desactivar auditoría](evidencias/capturas/terminal/P10_auditoria_activar_verificar_desactivar.png)
![Auditoría JSONB](evidencias/capturas/terminal/P10_auditoria_jsonb.png)
![Monitoreo de recursos](evidencias/capturas/terminal/P11_monitoreo_recursos_sgbd.png)
</details>

<details>
<summary><b>Práctica 12 — Suite de pruebas completa (CP-01 a CP-11)</b></summary>

![Suite pytest completa](evidencias/capturas/terminal/P12_pytest_suite_completa.png)
</details>

<details open>
<summary><b>Práctica 13 — Mejoras: modelo multi-sucursal, cifrado, tipos nativos y seguridad web</b></summary>

**Catálogo maestro `products` y existencias por sucursal en `inventory`** — un mismo producto con stock y precio propios en cada sucursal:

![Catálogo products e inventory](evidencias/capturas/terminal/P13_catalogo_products_inventory.png)

**Cifrado con pgcrypto** — en disco solo hay bytes cifrados; se leen únicamente con la clave del `.env` (que nunca aparece en la captura):

![Cifrado pgcrypto](evidencias/capturas/terminal/P13_cifrado_pgcrypto.png)

**Citas con tipos nativos `DATE`/`TIME`** — el propio SGBD rechaza fechas imposibles:

![Citas con tipos nativos](evidencias/capturas/terminal/P13_citas_tipos_nativos.png)

**Seguridad web** — un POST desde otro sitio se bloquea (403) y un script disfrazado de imagen se rechaza (400):

![Seguridad web CSRF y subidas](evidencias/capturas/terminal/P13_seguridad_web_csrf_subidas.png)

**CP-11** — la aplicación web probada de punta a punta:

![CP-11 aplicación web](evidencias/capturas/terminal/P13_pytest_cp11_aplicacion_web.png)
</details>

## Tecnologías y versiones

Versiones fijadas en `requirements.txt` y verificadas en este entorno:

| Componente | Tecnología | Versión |
| :--- | :--- | :--- |
| SGBD principal | PostgreSQL (maestro + réplica) + `pgcrypto` | 16.4 (`postgres:16.4-bookworm`) |
| SGBD de origen (migración) | SQLite | 3.45.1 |
| Orquestación de contenedores | Podman / podman-compose | 4.9.3 / 1.0.6 |
| Lenguaje | Python | 3.12.3 |
| Backend / servidor ASGI | FastAPI / Uvicorn | 0.115.0 / 0.31.0 |
| Conector PostgreSQL | psycopg | 3.2.2 (`psycopg[binary,pool]`) |
| Plantillas | Jinja2 | 3.1.4 |
| Autenticación | PyJWT / bcrypt | 2.8.0 / 4.1.2 |
| Imágenes | Pillow | 12.2.0 |
| Interfaz | Tailwind CSS (compilado) / Alpine.js / Lucide / ApexCharts | 3.4.17 / — / — / — |
| Carga sintética | Faker | 30.1.0 |
| Evidencia visual | Playwright / mermaid-cli (`mmdc`) | 1.48.0 / 11.x |
| Pruebas | pytest | 8.3.3 |

## Requisitos

Herramientas en el **host** (el servidor PostgreSQL corre solo dentro de los contenedores):

| Herramienta | Uso | Paquete en Linux Mint / Ubuntu / Debian |
| :--- | :--- | :--- |
| **Python 3.12+** | App FastAPI y scripts de migración/carga | `python3 python3-venv python3-pip` |
| **Podman 4.9+** y **podman-compose 1.0+** | Orquestar `fixit_pg_master` y `fixit_pg_replica` | `podman podman-compose` |
| **Cliente de PostgreSQL 16** (`psql`, `pg_dump`, `pg_basebackup`, `pg_restore`, `pg_isready`) | Respaldo, PITR y réplica se ejecutan desde el host; también el respaldo descargable de la app | `postgresql-client-16` |
| **Git 2.x** | Clonar y versionar | `git` |
| **Node.js 18+ y npm** | Solo para regenerar diagramas (`mmdc`) o el CSS (`build_css.sh`) | `nodejs npm` y `npm install -g @mermaid-js/mermaid-cli` |

| Recurso | Mínimo observado | Recomendado |
| :--- | :--- | :--- |
| CPU | 2 núcleos | 4 núcleos (ver la nota de la VM en [solución de problemas](#solución-de-problemas-frecuentes)) |
| RAM | ~2.1 GiB con maestro + réplica + app | 4 GiB mínimo, 8 GiB cómodo |
| Disco | ~1.4 GiB para los volúmenes (crece con `backups/`) | 10 GiB libres |
| Sistema operativo | Linux Mint 22.3 (compatible con Ubuntu 24.04 / Debian 12) | Cualquier Linux con Podman rootless (subuid/subgid configurados) |

## Instalación paso a paso

### 1. Clonar el repositorio

```bash
git clone https://github.com/GreenEnGit/FixIT_ArquiComp.git
cd FixIT_ArquiComp
```

### 2. Dependencias de Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # solo para regenerar la evidencia visual
```

### 3. PostgreSQL 16.4 en Podman y variables de entorno

```bash
bash infra/scripts/init_env.sh            # verificable antes con: --check
```

El script:

1. Verifica que `podman`, `podman-compose` y `psql` estén instalados.
2. Crea los volúmenes (`infra/volumes/pgdata`, `infra/volumes/tablespaces/ts_*`) con el propietario correcto (uid 999 del contenedor).
3. Crea `infra/.env` y `.env` desde los `.example` si no existen y **genera valores aleatorios únicos**: contraseñas del superusuario y de los 5 roles, `SECRET_KEY` (firma de sesiones) y `DEVICE_DATA_KEY` (cifrado pgcrypto). Ningún secreto queda en un archivo versionado.
4. Levanta `fixit_pg_master`, que ejecuta en orden `src/sql/01_tablespaces.sql` → `02_schema.sql` → `03_roles_and_quotas.sh` → `04_indexes.sql` → `05_audit_and_monitoring.sql` en el primer arranque.
5. Muestra `SELECT version();` y `\db+` como verificación.

Variables de `.env` (raíz):

| Variable | Descripción |
| :--- | :--- |
| `SECRET_KEY` | Firma de las cookies de sesión (JWT). La genera `init_env.sh`; si faltara, la app crea una temporal por proceso (nunca una clave fija). |
| `DEVICE_DATA_KEY` | Clave simétrica para cifrar con `pgcrypto` el PIN de los equipos. Sin ella la app no guarda esos datos. |
| `PGHOST` / `PGPORT` / `PGDATABASE` | `localhost` / `5432` / `fixit_db` |
| `PGUSER` / `PGPASSWORD` | `admin_sys` y su contraseña (sincronizada con `ADMIN_SYS_PASSWORD` de `infra/.env`) |
| `GEMINI_API_KEY`, `TWILIO_*` | Opcionales: sin ellas, el chatbot y los SMS funcionan en modo simulación |

### 4. Datos de ejemplo y migración SQLite → PostgreSQL

```bash
python3 infra/scripts/seed_sqlite_source.py          # genera taller_prototipo.db (no se versiona)
python3 infra/scripts/migrate_sqlite_to_pg.py --verify
```

La migración carga las 20 tablas de origen preservando los IDs, resincroniza las secuencias `IDENTITY`, **cifra el PIN de los equipos** (el sistema legado lo guardaba en texto plano) y reconstruye en `audit_logs` las ventas de mostrador. Es idempotente: trunca y recarga en cada ejecución, y termina comparando el conteo fila por fila.

Los datos de ejemplo incluyen 33 productos con foto (9 se venden en ambas sucursales), 14 clientes con sus equipos, 14 tickets en todos los estados, pagos, garantías, ventas de las últimas semanas, citas y guías de reparación. Las fechas son relativas al día en que se genera el seed y nunca quedan en el futuro.

### 5. Réplica (opcional para la app, necesaria para la Unidad 5)

```bash
bash infra/scripts/setup_replication.sh
```

Clona el maestro hacia `fixit_pg_replica` (puerto `5433`) con `pg_basebackup` y configura Streaming Replication con el slot físico `fixit_replica_slot`.

### 6. Ejecutar la aplicación

**Opción A — arranque automático en `http://fixittester.com` (recomendada):**

```bash
bash infra/scripts/install_autostart.sh
```

Pide `sudo` una vez e instala tres servicios systemd de usuario desde `infra/systemd/` (`container-fixit_pg_master`, `container-fixit_pg_replica` y `fixit-web`, que espera a que PostgreSQL acepte conexiones), activa *linger* para que arranquen sin iniciar sesión, agrega `127.0.0.1 fixittester.com` a `/etc/hosts` y permite usar el puerto 80 sin root. El nombre solo resuelve dentro de la VM; para entrar desde otro equipo, agrega en su archivo hosts la IP de la VM.

```bash
systemctl --user status fixit-web container-fixit_pg_master container-fixit_pg_replica
systemctl --user restart fixit-web      # tras modificar el código
journalctl --user -u fixit-web -f       # logs de la aplicación
```

**Opción B — ejecución manual:**

```bash
source .venv/bin/activate
uvicorn main:app --port 8000            # http://localhost:8000
```

### Actualizar una base creada con una versión anterior

Las instalaciones nuevas ya nacen con el modelo actual. Para migrar una base existente (catálogo `products`, citas `DATE`/`TIME` y cifrado) usa el script de [`src/sql/upgrades/`](src/sql/upgrades/2026-11_v2_catalogo_y_cifrado.sql); el comando exacto está en su encabezado.

## URLs, puertos y credenciales de laboratorio

| Servicio | URL / Puerto |
| :--- | :--- |
| Aplicación FixIT (arranque automático) | http://fixittester.com |
| Aplicación FixIT (ejecución manual) | http://localhost:8000 |
| PostgreSQL — maestro (`fixit_pg_master`) | `localhost:5432` |
| PostgreSQL — réplica (`fixit_pg_replica`, solo lectura) | `localhost:5433` |

Roles de **PostgreSQL** (creados por `src/sql/03_roles_and_quotas.sh`; sus contraseñas están solo en `infra/.env`):

| Rol de login | Variable con su contraseña | Rol de BD | Cuota |
| :--- | :--- | :--- | :---: |
| `admin_sys` | `ADMIN_SYS_PASSWORD` | `rol_dba` (superusuario) | Ilimitada |
| `app_tecnico` | `APP_TECNICO_PASSWORD` | `rol_tecnico` | 50 MB |
| `app_recepcion` | `APP_RECEPCION_PASSWORD` | `rol_recepcion` | 100 MB |
| `app_auditor` | `APP_AUDITOR_PASSWORD` | `rol_auditor` (solo lectura) | — |
| `replicator` | `REPLICATOR_PASSWORD` | `rol_replicacion` | — |

Los usuarios de la aplicación web están en el [inicio rápido](#inicio-rápido).

## Administración de los contenedores

```bash
bash infra/scripts/ops_modes.sh start     # alta del servicio
bash infra/scripts/ops_modes.sh stop      # baja ordenada
bash infra/scripts/ops_modes.sh status    # estado + pg_is_in_recovery()
bash infra/scripts/ops_modes.sh recovery  # fuerza modo standby (práctica de recuperación)
bash infra/scripts/ops_modes.sh normal    # promueve de vuelta a lectura-escritura y verifica
bash infra/scripts/ops_modes.sh logs      # archivos log, WAL y pg_stat_wal

bash infra/scripts/reindex.sh             # diagnóstico EXPLAIN + REINDEX en ts_indices
bash infra/scripts/backup_job.sh          # respaldo lógico (pg_dump) y físico (pg_basebackup)
bash infra/scripts/restore_pitr.sh "AAAA-MM-DD HH:MM:SS"   # recuperación a un punto en el tiempo
bash infra/scripts/toggle_audit.sh on|off|status           # auditoría dinámica
bash infra/scripts/monitor_resources.sh   # consultas costosas, cache hit, conexiones, bloqueos

podman ps -a --filter name=fixit_pg       # estado de ambos contenedores
```

Desde la app, el administrador puede descargar un respaldo lógico (`pg_dump`) de la base real en *Personal y Seguridad*.

## Pruebas automatizadas

```bash
pytest -v tests/test_dba_scb1001.py               # suite completa
pytest -v tests/test_dba_scb1001.py -k test_cp11  # un solo caso
```

Se ejecutan **contra el clúster real, sin mocks**, y en cada push en GitHub Actions sobre una instalación desde cero (`.github/workflows/tests.yml`).

| Caso | Qué valida |
| :---: | :--- |
| CP-01 | Instancia PostgreSQL 16.4 en modo transaccional y parámetros clave |
| CP-02 | 4 tablespaces y ninguna tabla en `pg_default` |
| CP-03 | Bloqueo por cuota excedida y rechazo de privilegios RBAC |
| CP-04 | Transición recovery/normal (siempre restaura el modo normal) y concurrencia sin stock negativo |
| CP-05 | Carga sintética, `REINDEX` e `Index Scan` |
| CP-06 | Streaming Replication y rechazo de escritura en la réplica |
| CP-07 | Respaldo y recuperación PITR exacta |
| CP-08 | Migración SQLite → PostgreSQL verificada al 100 % |
| CP-09 | Auditoría dinámica y monitoreo de recursos |
| CP-10 | Las 45 imágenes de evidencia existen, son PNG válidos y pesan más de 10 KB |
| CP-11 | Aplicación web: recorrido de enlaces, recursos y formularios (dos sucursales y rol técnico), subidas maliciosas, CSRF, venta que solo descuenta su sucursal, búsqueda y cifrado |

Tiempo típico: 25 s a 1 min (más si la réplica debe reclonarse).

## Evidencia visual y mantenimiento

| Tarea | Comando |
| :--- | :--- |
| Regenerar toda la evidencia (diagramas, terminal P01–P13, interfaz) | `python3 infra/scripts/capture_evidence.py --all` |
| Solo las capturas de la interfaz / de las mejoras P13 / la de pytest | `--ui` / `--mejoras` / `--pytest-capture` |
| Verificar que las 45 imágenes existan y sean válidas | `python3 infra/scripts/capture_evidence.py --verify` |
| Regenerar D02/D03 desde el catálogo real tras cambiar el esquema | `python3 infra/scripts/generate_schema_diagrams.py && python3 infra/scripts/capture_evidence.py --diagrams` |
| Regenerar el CSS tras cambiar clases de Tailwind en las plantillas | `bash infra/scripts/build_css.sh` |

Las capturas de terminal ejecutan respaldos, PITR y reinicios reales; al terminar, restaura los datos de ejemplo con `python3 infra/scripts/migrate_sqlite_to_pg.py --verify`.

## Solución de problemas frecuentes

| Problema | Causa | Solución |
| :--- | :--- | :--- |
| `migrate_sqlite_to_pg.py` falla con `no such table` | `taller_prototipo.db` no existe (no se versiona) | `python3 infra/scripts/seed_sqlite_source.py` |
| `FATAL: Peer authentication failed` al usar `podman exec` | Falta `--user postgres` | `podman exec --user postgres fixit_pg_master psql ...` |
| `FATAL: the database system is shutting down` tras `init_env.sh` | El entrypoint de PostgreSQL reinicia la instancia al terminar los scripts de inicio | `init_env.sh` ya reintenta; si usas `psql` a mano, reintenta en 1–2 s |
| La réplica entra en *crash loop* con `could not open directory "pg_tblspc/..."` | Symlinks de `pg_tblspc` apuntando a rutas del host | `bash infra/scripts/setup_replication.sh` (los corrige) |
| `pg_stat_replication` vacío tras `ops_modes.sh recovery/normal` o un PITR | La promoción crea una nueva *timeline* | `bash infra/scripts/setup_replication.sh` (CP-06 lo hace solo) |
| El maestro rechaza escrituras (`read-only transaction`) | Quedó en modo recovery (`standby.signal`) | `bash infra/scripts/ops_modes.sh normal` |
| Pruebas o capturas lentas o con *timeout* intermitente | La CPU virtual de la VM se congela 60–150 s cuando el anfitrión está saturado (`journalctl -k \| grep "starved for"`) | Asigna más CPU a la VM o detén contenedores ajenos al proyecto mientras pruebas; los *timeouts* de la suite ya toleran estas pausas |
| `Permiso denegado` en `infra/volumes/` | Pertenecen al uid 999 del namespace rootless | `podman unshare <comando>` |
| Puertos `5432`, `5433`, `80` u `8000` en uso | Otro servicio los ocupa | Libera el puerto o cambia el mapeo en `infra/compose.yaml` / `--port` |

## Estructura del proyecto

```
FixIT_ArquiComp/
├── main.py, database.py, dependencies.py, image_utils.py   # App FastAPI (psycopg3, saneo de imágenes)
├── routers/                 # Endpoints por módulo (tickets, pos, inventory, users, appointments, ...)
├── templates/               # Plantillas Jinja2
├── static/
│   ├── tailwind.css         # CSS compilado (fuente: static/src/ + tailwind.config.js)
│   ├── js/ui-dialogs.js     # Modales y avisos propios (sin prompt/alert)
│   └── img/products/        # 33 fotos saneadas + CREDITOS.md / creditos.json
├── tests/test_dba_scb1001.py   # Suite CP-01 a CP-11
├── src/
│   ├── sql/                 # 01_tablespaces … 05_audit_and_monitoring (+ upgrades/)
│   └── data_generator/      # seed_workload.py (carga sintética con Faker)
├── infra/
│   ├── compose.yaml         # fixit_pg_master (:5432) + fixit_pg_replica (:5433)
│   ├── config/              # postgresql.conf, pg_hba.conf
│   ├── systemd/             # servicios de arranque automático
│   └── scripts/             # init_env, install_autostart, setup_replication, backup_job, restore_pitr,
│                            #   ops_modes, reindex, toggle_audit, monitor_resources, build_css,
│                            #   seed_sqlite_source.py, migrate_sqlite_to_pg.py,
│                            #   generate_schema_diagrams.py, capture_evidence.py
├── evidencias/
│   ├── diagramas/           # D01–D04 (.mmd + .png)
│   └── capturas/{terminal,ui}/   # P01–P13 y UI_01–UI_11 (.png)
├── docs/                    # E01–E09: especificación académica SCB-1001
├── .github/workflows/tests.yml   # CI: suite completa en cada push/PR
└── README.md, MANUAL_*.md, DICCIONARIO_DATOS.md, PLAN_CONTINGENCIA.md, REPORTE_AUDITORIA.md, LICENSE
```

## Seguridad

- **Ningún secreto vive en archivos versionados.** Los `.example` solo tienen marcadores; `init_env.sh` genera contraseñas, `SECRET_KEY` y `DEVICE_DATA_KEY` únicas por instalación en `.env` e `infra/.env` (ambos en `.gitignore`).
- Las capturas que involucran secretos muestran la variable (`$DEVICE_DATA_KEY`, contraseñas enmascaradas) mientras ejecutan el comando real.
- El repositorio es público y en el pasado 5 contraseñas de laboratorio estuvieron en el historial: se consideran comprometidas y **ninguna se reutilizó**. Genera siempre las tuyas con `init_env.sh`.
- `infra/config/pg_hba.conf` acepta conexiones desde `0.0.0.0/0` con `scram-sha-256` porque la red rootless de Podman varía entre entornos; restríngelo al CIDR real antes de exponer el servicio fuera de un laboratorio.
- Los usuarios web (`admin`, `tecnico_*`) son cuentas de demostración del laboratorio.

## Manuales del proyecto

| Documento | Contenido |
| :--- | :--- |
| [`MANUAL_INSTALACION.md`](MANUAL_INSTALACION.md) | Unidades 1 y 2 — DBA, selección de SGBD, arquitectura, instalación transaccional (Práctica 1) |
| [`DICCIONARIO_DATOS.md`](DICCIONARIO_DATOS.md) | Unidad 3 — Tablespaces y modelo relacional de las 21 tablas, cifrado y tipos (Prácticas 2 y 13) |
| [`MANUAL_ADMINISTRACION.md`](MANUAL_ADMINISTRACION.md) | Unidades 3 y 4 — Cuotas, roles, logs, modos de operación, índices y operación de la app (Prácticas 2–5) |
| [`PLAN_CONTINGENCIA.md`](PLAN_CONTINGENCIA.md) | Unidad 5 — Replicación, respaldo, PITR y migración (Prácticas 6–9) |
| [`REPORTE_AUDITORIA.md`](REPORTE_AUDITORIA.md) | Unidad 6 — Auditoría, monitoreo, seguridad web y suite de pruebas (Prácticas 10–13) |
| [`BITACORA_SESION_SCB1001.md`](BITACORA_SESION_SCB1001.md) | Recapitulación cronológica de las tareas T-01 a T-12 |

## Estado y verificación

- **CI en verde:** la suite completa (CP-01 a CP-11, 17 pruebas) pasa en GitHub Actions sobre una instalación hecha desde cero en cada push.
- **Instalación nueva validada:** los scripts de `src/sql/` se ejecutaron en un contenedor limpio y la migración terminó con el 100 % de las filas verificadas.
- **Interfaz probada en navegador real:** cobro y reversión en el POS, reversión de surtidos, recepción con PIN y fotos (incluido el rechazo de un archivo malicioso), citas, edición de productos y página de error; sin enlaces rotos ni errores de JavaScript.
- **Diagramas consistentes con el esquema:** D02 y D03 se generan desde el catálogo de PostgreSQL.

---

## Aviso de uso

Proyecto académico desarrollado para la asignatura **Administración de Base de Datos (SCB-1001)** — TecNM. Su único propósito es demostrar los temas del programa en un entorno de laboratorio. **No está destinado a producción** y no debe desplegarse para operar negocios, procesar pagos ni almacenar datos personales reales.
