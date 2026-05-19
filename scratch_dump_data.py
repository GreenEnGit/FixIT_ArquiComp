import sqlite3

conn = sqlite3.connect("taller_prototipo.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

def dump_table(name):
    print(f"\n=== TABLE: {name} ===")
    cursor.execute(f"SELECT * FROM {name}")
    rows = cursor.fetchall()
    if not rows:
        print("No records.")
        return
    keys = rows[0].keys()
    print(" | ".join(keys))
    for row in rows:
        print(" | ".join(str(row[k]) for k in keys))

for t in ['inventory', 'ticket_parts', 'sales', 'sale_items', 'payments', 'tickets']:
    dump_table(t)

conn.close()
