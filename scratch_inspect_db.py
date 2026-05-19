import sqlite3

conn = sqlite3.connect("taller_prototipo.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. Print all tables
print("=== TABLES ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
for row in cursor.fetchall():
    print(row['name'])

# 2. Print all triggers
print("\n=== TRIGGERS ===")
cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger'")
triggers = cursor.fetchall()
if not triggers:
    print("No triggers found.")
for row in triggers:
    print(f"Trigger Name: {row['name']} on Table: {row['tbl_name']}")
    print(f"SQL: {row['sql']}\n")

# 3. Print schema of important tables
print("\n=== SCHEMAS ===")
for tbl in ['inventory', 'ticket_parts', 'sales', 'sale_items', 'payments', 'tickets']:
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tbl}'")
    row = cursor.fetchone()
    if row:
        print(row['sql'])

conn.close()
