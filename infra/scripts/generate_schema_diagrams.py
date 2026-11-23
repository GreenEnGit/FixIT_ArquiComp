#!/usr/bin/env python3
"""FixIT_ArquiComp — infra/scripts/generate_schema_diagrams.py
Genera D02 (tablas por tablespace) y D03 (modelo relacional) en Mermaid a
partir del catálogo real de PostgreSQL, para que los diagramas nunca se
desfasen del esquema. Escribe los .mmd en evidencias/diagramas/ y actualiza
los bloques correspondientes de docs/06_arquitectura_y_datos.md.

Uso:
    python3 infra/scripts/generate_schema_diagrams.py
    (después: python3 infra/scripts/capture_evidence.py --diagrams)
"""
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))
import database  # noqa: E402

DIAG_DIR = PROJECT_DIR / "evidencias" / "diagramas"
DOC = PROJECT_DIR / "docs" / "06_arquitectura_y_datos.md"
TYPE_MAP = {"character varying": "varchar", "integer": "int", "timestamp without time zone": "timestamp",
            "time without time zone": "time", "double precision": "float"}
TS_PATHS = "/var/lib/postgresql/tablespaces/"


def fetch(sql, params=()):
    conn = database.get_db()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        return c.fetchall()
    finally:
        conn.close()


def d02():
    rows = fetch("""
        SELECT COALESCE(t.spcname, 'pg_default') AS ts, c.relname, c.relkind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_tablespace t ON t.oid = c.reltablespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'i')
        ORDER BY 1, 2""")
    tables, indexes = defaultdict(list), defaultdict(int)
    for r in rows:
        if r["relkind"] == "r":
            tables[r["ts"]].append(r["relname"])
        else:
            indexes[r["ts"]] += 1
    lines = ["graph LR", '    DB[("Base de Datos: fixit_db\\n(PostgreSQL 16.4)")]']
    for ts in ("ts_catalogos", "ts_transaccional", "ts_auditoria"):
        names = tables.get(ts, [])
        wrapped = "\\n".join(", ".join(names[i:i + 3]) for i in range(0, len(names), 3))
        lines.append(f'    DB --> {ts.upper()}["Tablespace: {ts}\\n{TS_PATHS}{ts}\\n{len(names)} tablas:\\n{wrapped}"]')
    lines.append(f'    DB --> TS_INDICES["Tablespace: ts_indices\\n{TS_PATHS}ts_indices\\n'
                 f'{indexes.get("ts_indices", 0)} índices (PK, UNIQUE y B-Tree secundarios)"]')
    return "\n".join(lines) + "\n"


def d03():
    cols = fetch("""
        SELECT c.table_name, c.column_name, c.data_type
        FROM information_schema.columns c
        JOIN information_schema.tables t ON t.table_name = c.table_name AND t.table_schema = c.table_schema
        WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
        ORDER BY c.table_name, c.ordinal_position""")
    keys = fetch("""
        SELECT rel.relname AS tbl, con.contype, att.attname AS col, ref.relname AS ref_tbl
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN LATERAL unnest(con.conkey) AS k(attnum) ON true
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = k.attnum
        LEFT JOIN pg_class ref ON ref.oid = con.confrelid
        WHERE n.nspname = 'public' AND con.contype IN ('p', 'f', 'u')""")
    marks, rels = defaultdict(set), []
    for k in keys:
        tag = {"p": "PK", "f": "FK", "u": "UK"}[k["contype"]]
        marks[(k["tbl"], k["col"])].add(tag)
        if k["contype"] == "f":
            rels.append((k["ref_tbl"], k["tbl"], k["col"]))
    lines = ["erDiagram"]
    for parent, child, col in sorted(set(rels)):
        lines.append(f'    {parent} ||--o{{ {child} : "{col}"')
    by_table = defaultdict(list)
    for c in cols:
        by_table[c["table_name"]].append(c)
    for table in sorted(by_table):
        lines.append(f"    {table} {{")
        for c in by_table[table]:
            typ = TYPE_MAP.get(c["data_type"], c["data_type"]).replace(" ", "_")
            tag = ", ".join(t for t in ("PK", "FK", "UK") if t in marks[(table, c["column_name"])])
            lines.append(f"        {typ} {c['column_name']}{' ' + tag if tag else ''}")
        lines.append("    }")
    return "\n".join(lines) + "\n"


def replace_doc_block(doc_text, heading_fragment, new_body):
    pattern = re.compile(r"(## [^\n]*" + re.escape(heading_fragment) + r"[^\n]*\n.*?```mermaid\n)(.*?)(```)", re.S)
    new_text, n = pattern.subn(lambda m: m.group(1) + new_body + m.group(3), doc_text, count=1)
    if n != 1:
        sys.exit(f"[ERROR] no se encontró el bloque Mermaid de '{heading_fragment}' en {DOC}")
    return new_text


def main():
    blocks = {"D02_distribucion_tablespaces": d02(), "D03_modelo_relacional_3fn": d03()}
    doc = DOC.read_text(encoding="utf-8")
    for name, body in blocks.items():
        (DIAG_DIR / f"{name}.mmd").write_text(body, encoding="utf-8")
        doc = replace_doc_block(doc, f"`{name}.png`", body)
        print(f"[OK] {name}.mmd generado desde el catálogo ({body.count(chr(10))} líneas)")
    DOC.write_text(doc, encoding="utf-8")
    print(f"[OK] {DOC.relative_to(PROJECT_DIR)} actualizado")


if __name__ == "__main__":
    os.chdir(PROJECT_DIR)
    main()
