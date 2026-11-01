import os
import re
import logging
import bcrypt
import psycopg
from psycopg.rows import dict_row
from psycopg.types.numeric import NumericLoader, NumericBinaryLoader
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("fixit")

PG_HOST = os.getenv("PGHOST", "localhost")
PG_PORT = os.getenv("PGPORT", "5432")
PG_DATABASE = os.getenv("PGDATABASE", "fixit_db")
PG_USER = os.getenv("PGUSER", "admin_sys")
PG_PASSWORD = os.getenv("PGPASSWORD", "")


# El codigo de la app (heredado de SQLite, donde las columnas REAL siempre
# llegaban como float) mezcla valores monetarios con floats en templates y
# aritmetica. Las columnas NUMERIC de Postgres llegan por defecto como
# Decimal via psycopg, lo que rompe esas operaciones (Decimal + float ->
# TypeError). Se registran loaders que devuelven float para igualar el
# comportamiento original en vez de parchear cada sitio de uso.
class _NumericAsFloat(NumericLoader):
    def load(self, data):
        return float(super().load(data))


class _NumericBinaryAsFloat(NumericBinaryLoader):
    def load(self, data):
        return float(super().load(data))


psycopg.adapters.register_loader("numeric", _NumericAsFloat)
psycopg.adapters.register_loader("numeric", _NumericBinaryAsFloat)


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


class _CompatCursor:
    # shortcut: traduce placeholders estilo SQLite ("?") a los de psycopg
    # ("%s") para no reescribir las ~400 consultas existentes en routers/.
    # Se apoya en que ninguna consulta del proyecto usa "?" o "%" dentro de
    # un literal de texto (solo como marcador de parámetro); si una consulta
    # nueva lo hiciera, este shim la rompería y habría que escribirla con %s.
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=()):
        self._cur.execute(sql.replace("?", "%s"), params)
        return self

    def __getattr__(self, name):
        return getattr(self._cur, name)

    def __iter__(self):
        return iter(self._cur)


class _CompatConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _CompatCursor(self._conn.cursor())

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    conn = psycopg.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD,
        row_factory=dict_row,
    )
    return _CompatConnection(conn)


def init_db():
    # El esquema (tablespaces, tablas, roles, cuotas) ya se aplica fuera de
    # la app, vía src/sql/*.sql al arrancar fixit_pg_master (infra/compose.yaml).
    # Aqui solo se verifica que la instancia responda en modo transaccional.
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT 1")
        c.fetchone()
        logger.info("Conexión a PostgreSQL (%s) verificada.", PG_DATABASE)
    finally:
        conn.close()


def check_engine() -> str:
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT version()")
        version_string = c.fetchone()["version"]
        match = re.search(r"PostgreSQL (\d+\.\d+)", version_string)
        return f"PostgreSQL {match.group(1)}" if match else version_string
    finally:
        conn.close()


if __name__ == '__main__':
    init_db()
