import sqlite3

def migrate():
    conn = sqlite3.connect('taller_prototipo.db')
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE knowledge_base ADD COLUMN category TEXT DEFAULT 'General'")
        conn.commit()
        print("Migración exitosa: columna category añadida.")
    except Exception as e:
        print(f"Error o ya migrado: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
