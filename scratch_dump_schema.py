import sqlite3

def dump_schema():
    conn = sqlite3.connect('taller_prototipo.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in c.fetchall()]
    
    for t in tables:
        c.execute(f"PRAGMA table_info({t});")
        cols = c.fetchall()
        print(f"Table: {t}")
        for col in cols:
            print(f"  {col[1]} ({col[2]})")
            
if __name__ == '__main__':
    dump_schema()
