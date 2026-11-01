#!/usr/bin/env python3
"""FixIT_ArquiComp — T-07 — Generador de carga sintetica con Faker 30.1.0.
SCB-1001 U3.T3.S3 / U4.T4.S3 / U6.T6.S1 — RF-05.

Uso:
    python3 src/data_generator/seed_workload.py --rows 10000
"""
import argparse
import os
import random
import sys
import time
import uuid
from datetime import timedelta

from faker import Faker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psycopg  # noqa: E402
import database  # noqa: E402

STATUSES = ["RECIBIDO", "EN DIAGNÓSTICO", "ESPERANDO PIEZAS", "EN REPARACIÓN",
            "LISTO PARA ENTREGA", "ENTREGADO Y PAGADO"]


def seed(rows: int):
    fake = Faker("es_MX")
    conn = psycopg.connect(
        host=database.PG_HOST, port=database.PG_PORT, dbname=database.PG_DATABASE,
        user=database.PG_USER, password=database.PG_PASSWORD,
    )
    cur = conn.cursor()

    cur.execute("SELECT id FROM customers")
    customer_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM customer_devices")
    device_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM branches")
    branch_ids = [r[0] for r in cur.fetchall()]

    if not (customer_ids and device_ids and branch_ids):
        print("[ERROR] No hay clientes/dispositivos/sucursales base. Ejecuta primero la migracion (T-05).")
        sys.exit(1)

    today = fake.date_this_decade()
    values = []
    for _ in range(rows):
        values.append((
            f"REP-{uuid.uuid4().hex[:10].upper()}",
            random.choice(STATUSES),
            random.choice(customer_ids),
            random.choice(device_ids),
            fake.sentence(nb_words=8),
            today - timedelta(days=random.randint(0, 700)),
            round(random.uniform(0, 2500), 2),
            random.choice(branch_ids),
        ))

    start = time.perf_counter()
    cur.executemany(
        "INSERT INTO tickets (id, status, customer_id, device_id, symptom, date, labor_cost, branch_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        values,
    )
    conn.commit()
    elapsed = time.perf_counter() - start

    cur.execute("SELECT COUNT(*) FROM tickets")
    total = cur.fetchone()[0]
    print(f"[OK] {rows} tickets sinteticos insertados en {elapsed:.2f}s (total en tabla: {total}).")

    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10000)
    args = parser.parse_args()
    seed(args.rows)
