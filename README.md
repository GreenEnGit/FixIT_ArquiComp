# 🛠️ FixIT Enterprise DBA — SCB-1001

![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.4-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Podman](https://img.shields.io/badge/Podman-4.9.3-892CA0?style=for-the-badge&logo=podman&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.12.3-3776AB?style=for-the-badge&logo=python&logoColor=white)

**FixIT** es un sistema de gestión integral para talleres de reparación de hardware (tickets, inventario, punto de venta, clientes). Este repositorio documenta su evolución desde una arquitectura monolítica sobre **SQLite 3.45.1** hacia un **clúster transaccional distribuido en PostgreSQL 16.4**, contenedorizado con **Podman 4.9.3**, cubriendo el 100% del temario oficial **Administración de Base de Datos (SCB-1001)** del TecNM.

Toda operación de DBA descrita en este repositorio (instalación, tablespaces, roles y cuotas, modos de operación, índices, replicación, respaldo/recuperación PITR, migración, auditoría y monitoreo) se verificó con comandos reales ejecutados contra el clúster y quedó documentada con evidencia visual automatizada.

![Arquitectura FixIT_ArquiComp](evidencias/diagramas/D01_arquitectura_memoria_procesos.png)

![Dashboard FixIT sobre PostgreSQL 16.4](evidencias/capturas/ui/UI_01_login_y_dashboard.png)

## Manuales del proyecto

| Documento | Contenido |
| :--- | :--- |
| [`MANUAL_INSTALACION.md`](MANUAL_INSTALACION.md) | Unidades 1 y 2 — DBA, selección de SGBD, arquitectura, instalación transaccional (Práctica 1) |
| [`DICCIONARIO_DATOS.md`](DICCIONARIO_DATOS.md) | Unidad 3 — Tablespaces y modelo relacional de las ~19 tablas (Práctica 2) |
| [`MANUAL_ADMINISTRACION.md`](MANUAL_ADMINISTRACION.md) | Unidades 3 y 4 — Cuotas, roles, logs, modos de operación, índices (Prácticas 2-5) |
| [`PLAN_CONTINGENCIA.md`](PLAN_CONTINGENCIA.md) | Unidad 5 — Replicación, respaldo, PITR y migración (Prácticas 6-9) |
| [`REPORTE_AUDITORIA.md`](REPORTE_AUDITORIA.md) | Unidad 6 — Auditoría dinámica y monitoreo, suite de pruebas (Prácticas 10-11) |

## Despliegue en un comando

```bash
bash infra/scripts/init_env.sh                              # aprovisiona y levanta fixit_pg_master
python3 infra/scripts/migrate_sqlite_to_pg.py --verify       # migra taller_prototipo.db -> fixit_db
bash infra/scripts/setup_replication.sh                      # levanta fixit_pg_replica (:5433)
uvicorn main:app --port 8000                                  # app FastAPI contra PostgreSQL 16.4
```

## Stack tecnológico

| Componente | Tecnología | Versión |
| :--- | :--- | :--- |
| SGBD principal | PostgreSQL (maestro + réplica) | 16.4 |
| SGBD de origen (migración) | SQLite | 3.45.1 |
| Orquestación de contenedores | Podman / podman-compose | 4.9.3 / 1.0.6 |
| Backend | FastAPI / Uvicorn | 0.115.0 / 0.31.0 |
| Conector PostgreSQL | psycopg | 3.2.2 |
| Carga sintética | Faker | 30.1.0 |
| Evidencia visual | Playwright / mermaid-cli | 1.48.0 / 11.x |
| Pruebas | pytest | 8.3.3 |

## Características funcionales de FixIT

- 📱 Gestión de tickets de reparación por estados (Recibido → Entregado y Pagado)
- 🛒 Punto de venta (POS) integrado con el inventario
- 📦 Control de inventario con especificaciones en JSONB
- 👥 CRM de clientes y dispositivos
- 🔐 RBAC multi-sucursal con cuotas de espacio por rol
- 🔔 Notificaciones SMS vía Twilio (opcional)
- 📊 Auditoría dinámica activable/desactivable con trazas JSONB antes/después

## Roles de base de datos (RBAC)

| Rol | Uso | Cuota |
| :--- | :--- | :---: |
| `admin_sys` (`rol_dba`) | Administrador de Base de Datos | Ilimitada |
| `app_tecnico` (`rol_tecnico`) | Flujo de tickets y refacciones | 50 MB |
| `app_recepcion` (`rol_recepcion`) | Clientes, equipos, cobros | 100 MB |
| `app_auditor` (`rol_auditor`) | Solo lectura sobre auditoría y monitoreo | — |
| `replicator` (`rol_replicacion`) | Streaming Replication | — |

> Credenciales de laboratorio definidas en `src/sql/03_roles_and_quotas.sql`; rotar antes de cualquier uso en producción.
