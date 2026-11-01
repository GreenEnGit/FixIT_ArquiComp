#!/usr/bin/env python3
"""FixIT_ArquiComp — T-05 — Migracion real de taller_prototipo.db (SQLite 3.45.1)
hacia PostgreSQL 16.4 (fixit_db). SCB-1001 U5.T5.S5 / RF-04.

Uso:
    python3 infra/scripts/migrate_sqlite_to_pg.py [--verify]

--verify imprime el conteo de filas SQLite vs PostgreSQL por tabla y termina
con codigo de salida != 0 si algun conteo no coincide.
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg  # noqa: E402
import database  # noqa: E402

SQLITE_PATH = os.path.join(os.path.dirname(database.__file__), "taller_prototipo.db")

# (tabla, tiene_pk_identity) en orden de dependencia de FK (coincide con src/sql/02_schema.sql)
TABLES = [
    ("branches", False),
    ("users", True),
    ("customers", False),
    ("vendors", False),
    ("knowledge_base", True),
    ("inventory", False),
    ("purchase_orders", True),
    ("customer_devices", False),
    ("tickets", False),
    ("ticket_parts", True),
    ("payments", True),
    ("warranties", True),
    ("loaners", False),
    ("appointments", True),
    ("activities", True),
    ("ticket_images", True),
    ("sales", True),
    ("sale_items", True),
    ("audit_logs", True),
]


def _clean(col, value):
    # shortcut: solo inventory.specs necesita saneo (JSON vacio -> NULL para
    # el cast implicito text->jsonb); si otra columna JSONB se agrega al
    # esquema, sumarla aqui.
    if col == "specs" and (value is None or value == ""):
        return None
    return value


def migrate():
    sconn = sqlite3.connect(SQLITE_PATH)
    sconn.row_factory = sqlite3.Row

    pconn = psycopg.connect(
        host=database.PG_HOST, port=database.PG_PORT, dbname=database.PG_DATABASE,
        user=database.PG_USER, password=database.PG_PASSWORD,
    )
    pcur = pconn.cursor()

    # Idempotente: limpia las tablas de destino antes de recargar.
    all_tables = ", ".join(t for t, _ in TABLES)
    pcur.execute(f"TRUNCATE {all_tables} RESTART IDENTITY CASCADE")

    scur = sconn.cursor()
    for table, has_identity in TABLES:
        scur.execute(f"SELECT * FROM {table}")
        rows = scur.fetchall()
        if not rows:
            continue

        cols = rows[0].keys()
        col_list = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        overriding = " OVERRIDING SYSTEM VALUE" if has_identity else ""
        sql = f"INSERT INTO {table} ({col_list}){overriding} VALUES ({placeholders})"

        values = [tuple(_clean(col, row[col]) for col in cols) for row in rows]
        pcur.executemany(sql, values)
        print(f"[OK] {table}: {len(rows)} filas migradas")

        if has_identity:
            pcur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}','id'), "
                f"(SELECT COALESCE(MAX(id), 1) FROM {table}), "
                f"(SELECT MAX(id) FROM {table}) IS NOT NULL)"
            )

    pconn.commit()
    pcur.close()
    pconn.close()
    sconn.close()


def verify():
    sconn = sqlite3.connect(SQLITE_PATH)
    scur = sconn.cursor()

    pconn = psycopg.connect(
        host=database.PG_HOST, port=database.PG_PORT, dbname=database.PG_DATABASE,
        user=database.PG_USER, password=database.PG_PASSWORD,
    )
    pcur = pconn.cursor()

    print(f"\n{'tabla':<20}{'sqlite':>10}{'postgres':>12}{'estado':>10}")
    all_ok = True
    for table, _ in TABLES:
        scur.execute(f"SELECT COUNT(*) FROM {table}")
        n_sqlite = scur.fetchone()[0]
        pcur.execute(f"SELECT COUNT(*) FROM {table}")
        n_pg = pcur.fetchone()[0]
        ok = n_sqlite == n_pg
        all_ok &= ok
        print(f"{table:<20}{n_sqlite:>10}{n_pg:>12}{'OK' if ok else 'DIFIERE':>10}")

    sconn.close()
    pconn.close()
    return all_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    migrate()

    if args.verify:
        if not verify():
            print("\n[ERROR] El conteo de filas no coincide entre SQLite y PostgreSQL.")
            sys.exit(1)
        print("\n[OK] Migracion verificada: 100% de las filas coinciden.")
