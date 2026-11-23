"""FixIT_ArquiComp — tests/test_dba_scb1001.py
SCB-1001 — T-12: Suite de validacion academica (CP-01 a CP-11).

Uso:
    pytest -v tests/test_dba_scb1001.py
    pytest -v tests/test_dba_scb1001.py -k test_cp05
"""
import subprocess
import sys
import time
from pathlib import Path

import pytest
from dotenv import dotenv_values

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import database  # noqa: E402

EVID_DIR = PROJECT_DIR / "evidencias"

# Contraseñas operativas: se leen de infra/.env (gitignored, generado por
# init_env.sh), nunca hardcodeadas aqui.
_INFRA_ENV = dotenv_values(PROJECT_DIR / "infra" / ".env")
APP_TECNICO_PASSWORD = _INFRA_ENV["APP_TECNICO_PASSWORD"]


def run(cmd, timeout=180):
    return subprocess.run(cmd, shell=True, cwd=PROJECT_DIR, capture_output=True,
                           text=True, timeout=timeout)


def fetch_one(sql, params=()):
    conn = database.get_db()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        return c.fetchone()
    finally:
        conn.close()


def fetch_all(sql, params=()):
    conn = database.get_db()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        return c.fetchall()
    finally:
        conn.close()


def execute(sql, params=()):
    conn = database.get_db()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# =====================================================================
# CP-01 — RF-01, RNF-01, RNF-02 — U1.T1.S1..S4, U2.T2.S1..S8
# =====================================================================

def test_cp01_instancia_transaccional():
    assert database.check_engine() == "PostgreSQL 16.4"

    row = fetch_one("SHOW default_transaction_isolation")
    assert row["default_transaction_isolation"] == "read committed"

    row = fetch_one("SHOW shared_buffers")
    assert row["shared_buffers"] == "256MB"

    row = fetch_one("SHOW wal_level")
    assert row["wal_level"] == "replica"

    row = fetch_one("SHOW logging_collector")
    assert row["logging_collector"] == "on"


# =====================================================================
# CP-02 — RNF-03 — U3.T3.S1, S2, S4
# =====================================================================

def test_cp02_tablespaces_y_objetos():
    tablespaces = {r["spcname"] for r in fetch_all(
        "SELECT spcname FROM pg_tablespace")}
    for ts in ("ts_catalogos", "ts_transaccional", "ts_auditoria", "ts_indices"):
        assert ts in tablespaces

    rows = fetch_all("""
        SELECT c.relname, COALESCE(t.spcname, 'pg_default') AS tablespace
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_tablespace t ON t.oid = c.reltablespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
    """)
    assert len(rows) >= 19
    assert all(r["tablespace"] != "pg_default" for r in rows)


# =====================================================================
# CP-03 — RNF-04 — U3.T3.S3, S5
# =====================================================================

def test_cp03_cuota_y_rbac():
    execute("UPDATE user_disk_quotas SET max_bytes = 10, used_bytes = 0 "
            "WHERE role_name = 'app_tecnico'")
    try:
        result = run(
            f'PGPASSWORD={APP_TECNICO_PASSWORD} podman exec -e PGPASSWORD -i fixit_pg_master '
            'psql -h 127.0.0.1 -U app_tecnico -d fixit_db -c '
            '"INSERT INTO tickets (id, status, customer_id, device_id, symptom, date, branch_id) '
            "VALUES ('REP-CP03TEST', 'RECIBIDO', 'CUST-01', 'DEV-001', 'cp03', CURRENT_DATE, 'NORTE');\""
        )
        assert "Cuota de espacio en disco excedida" in (result.stdout + result.stderr)
    finally:
        execute("UPDATE user_disk_quotas SET max_bytes = 52428800, used_bytes = 0 "
                "WHERE role_name = 'app_tecnico'")

    result = run(
        f'PGPASSWORD={APP_TECNICO_PASSWORD} podman exec -e PGPASSWORD -i fixit_pg_master '
        'psql -h 127.0.0.1 -U app_tecnico -d fixit_db -c "DELETE FROM payments WHERE id = 1;"'
    )
    assert "permission denied" in (result.stdout + result.stderr)


# =====================================================================
# CP-04 — RF-02, RNF-05 — U4.T4.S1, S2
# =====================================================================

def test_cp04_modos_operacion_y_concurrencia():
    try:
        result = run("bash infra/scripts/ops_modes.sh recovery", timeout=150)
        assert result.returncode == 0, result.stdout + result.stderr
        check = run('podman exec --user postgres fixit_pg_master psql -U postgres '
                    '-d fixit_db -t -c "SELECT pg_is_in_recovery();"')
        assert check.stdout.strip() == "t"
    finally:
        # Siempre regresar a modo normal: si el maestro se quedara en recovery,
        # todos los casos siguientes fallarian en cascada.
        result = run("bash infra/scripts/ops_modes.sh normal", timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    row = fetch_one("SELECT pg_is_in_recovery() AS recovering")
    assert row["recovering"] is False

    # Concurrencia: descuento de inventario no debe dejar stock negativo.
    execute("UPDATE inventory SET stock = 5 WHERE id = 'CAB-USB-C'")
    import concurrent.futures

    def deduct():
        conn = database.get_db()
        try:
            c = conn.cursor()
            c.execute("SELECT stock FROM inventory WHERE id = 'CAB-USB-C' FOR UPDATE")
            stock = c.fetchone()["stock"]
            if stock > 0:
                c.execute("UPDATE inventory SET stock = stock - 1 WHERE id = 'CAB-USB-C'")
            conn.commit()
        finally:
            conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(lambda _: deduct(), range(10)))

    row = fetch_one("SELECT stock FROM inventory WHERE id = 'CAB-USB-C'")
    assert row["stock"] == 0

    result = run("bash infra/scripts/ops_modes.sh logs", timeout=120)
    assert result.returncode == 0
    assert "pg_log" in result.stdout or "pg_stat_wal" in result.stdout


# =====================================================================
# CP-05 — RF-05, RNF-06 — U4.T4.S3
# =====================================================================

def test_cp05_carga_sintetica_e_indices():
    result = run("python3 src/data_generator/seed_workload.py --rows 2000", timeout=240)
    assert result.returncode == 0
    assert "insertados" in result.stdout

    execute("UPDATE tickets SET status = 'EN REPARACIÓN' "
            "WHERE id IN (SELECT id FROM tickets ORDER BY id LIMIT 500)")
    execute("ANALYZE tickets")

    result = run("bash infra/scripts/reindex.sh", timeout=240)
    assert result.returncode == 0
    assert "REINDEX" in result.stdout or "DO" in result.stdout

    plan_rows = fetch_all(
        "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM tickets WHERE branch_id = 'NORTE' AND status = 'RECIBIDO'"
    )
    plan_text = "\n".join(r["QUERY PLAN"] for r in plan_rows)
    assert "Index" in plan_text


# =====================================================================
# CP-06 — RNF-07 — U5.T5.S1, S2
# =====================================================================

def test_cp06_streaming_replication():
    # CP-04 pudo promover al maestro (nueva timeline) via ops_modes.sh
    # recovery/normal; se reclona la replica para no depender de ese orden.
    row = fetch_one("SELECT state FROM pg_stat_replication LIMIT 1")
    if row is None or row["state"] != "streaming":
        result = run("bash infra/scripts/setup_replication.sh", timeout=240)
        assert result.returncode == 0
        time.sleep(2)
        row = fetch_one("SELECT state FROM pg_stat_replication LIMIT 1")

    assert row is not None and row["state"] == "streaming"

    execute("INSERT INTO branches (id, name) VALUES ('CP06-TEST', 'Prueba CP06')")
    time.sleep(1)

    result = run('podman exec --user postgres fixit_pg_replica psql -U postgres -d fixit_db '
                 '-t -c "SELECT name FROM branches WHERE id = \'CP06-TEST\';"')
    assert "Prueba CP06" in result.stdout

    result = run('podman exec --user postgres fixit_pg_replica psql -U postgres -d fixit_db '
                 '-c "INSERT INTO branches (id, name) VALUES (\'X\', \'no\');"')
    assert "read-only transaction" in (result.stdout + result.stderr)

    execute("DELETE FROM branches WHERE id = 'CP06-TEST'")


# =====================================================================
# CP-07 — RNF-08 — U5.T5.S3, S4
# =====================================================================

def test_cp07_backup_y_pitr():
    result = run("bash infra/scripts/backup_job.sh", timeout=120)
    assert result.returncode == 0
    backups_dir = PROJECT_DIR / "backups"
    dumps = list(backups_dir.glob("fixit_db_logical_*.dump"))
    tarballs = list(backups_dir.glob("basebackup_*.tar.gz"))
    assert dumps and tarballs

    original = fetch_all("SELECT id, ticket_id, amount, method, date FROM payments ORDER BY id")

    t_safe = run('date "+%Y-%m-%d %H:%M:%S"').stdout.strip()
    execute("DELETE FROM payments")

    result = run(f'bash infra/scripts/restore_pitr.sh "{t_safe}"', timeout=180)
    assert result.returncode == 0

    row = fetch_one("SELECT pg_is_in_recovery() AS recovering")
    assert row["recovering"] is False

    restored = fetch_all("SELECT id, ticket_id, amount, method, date FROM payments ORDER BY id")
    assert len(restored) == len(original)
    assert [dict(r) for r in restored] == [dict(r) for r in original]

    # El PITR invalida la timeline de la replica: se reclona para dejar el cluster consistente.
    run("bash infra/scripts/setup_replication.sh", timeout=240)


# =====================================================================
# CP-08 — RF-04 — U5.T5.S5
# =====================================================================

def test_cp08_migracion_sqlite_postgres():
    result = run("python3 infra/scripts/migrate_sqlite_to_pg.py --verify", timeout=240)
    assert result.returncode == 0
    assert "100%" in result.stdout or "DIFIERE" not in result.stdout


# =====================================================================
# CP-09 — RF-03, RNF-09, RNF-10 — U6.T6.S1, S2
# =====================================================================

def test_cp09_auditoria_y_monitoreo():
    run("bash infra/scripts/toggle_audit.sh on")
    execute("UPDATE inventory SET price = price WHERE id = 'CAB-USB-C'")
    row = fetch_one("SELECT action FROM audit_logs WHERE action = 'TRIGGER_UPDATE' "
                     "ORDER BY id DESC LIMIT 1")
    assert row is not None

    run("bash infra/scripts/toggle_audit.sh off")
    before = fetch_one("SELECT count(*) AS n FROM audit_logs WHERE action = 'TRIGGER_UPDATE'")["n"]
    execute("UPDATE inventory SET price = price WHERE id = 'CAB-USB-C'")
    after = fetch_one("SELECT count(*) AS n FROM audit_logs WHERE action = 'TRIGGER_UPDATE'")["n"]
    assert after == before

    run("bash infra/scripts/toggle_audit.sh on")

    result = run("bash infra/scripts/monitor_resources.sh", timeout=240)
    assert result.returncode == 0
    assert "pg_stat_statements" in result.stdout or "cache_hit_ratio" in result.stdout


# =====================================================================
# CP-10 — RNF-11 — Transversal (11 practicas y diagramas)
# =====================================================================

def test_cp10_evidencia_visual_completa():
    diagramas = list((EVID_DIR / "diagramas").glob("D0*.png"))
    terminal = list((EVID_DIR / "capturas" / "terminal").glob("P*.png"))
    ui = list((EVID_DIR / "capturas" / "ui").glob("UI_*.png"))

    assert len(diagramas) == 4, f"se esperaban 4 diagramas, hay {len(diagramas)}"
    assert len(terminal) >= 30, f"se esperaban >=30 capturas de terminal (P01-P13), hay {len(terminal)}"
    assert len(ui) == 11, f"se esperaban 11 capturas de UI, hay {len(ui)}"

    for path in diagramas + terminal + ui:
        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} no es un PNG valido"
        assert len(data) > 10 * 1024, f"{path.name} pesa {len(data)} bytes (<= 10 KB)"


# =====================================================================
# CP-11 — Aplicación web: navegación, subidas, CSRF, sucursales y cifrado
# =====================================================================
# Levanta la app real (uvicorn) contra el clúster y la recorre por HTTP.

import io  # noqa: E402
import re  # noqa: E402
import socket  # noqa: E402
from html.parser import HTMLParser  # noqa: E402
from urllib.parse import urljoin, urlparse  # noqa: E402

import requests  # noqa: E402

CP11_PORT = 8765


@pytest.fixture(scope="module")
def app_url():
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(CP11_PORT)],
                            cwd=PROJECT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", CP11_PORT), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("uvicorn no respondió en :%d" % CP11_PORT)
        yield f"http://127.0.0.1:{CP11_PORT}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _session(base, user="admin", password="admin123", branch=None):
    s = requests.Session()
    s.headers["Origin"] = base
    r = s.post(base + "/login", data={"username": user, "password": password})
    assert r.status_code == 200 and "session_token" in s.cookies
    if branch:
        s.post(base + "/set_branch/" + branch, headers={"Referer": base + "/"})
    return s


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.assets, self.forms = set(), set(), []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.add(a["href"])
        if tag in ("img", "script") and a.get("src"):
            self.assets.add(a["src"])
        if tag == "link" and a.get("href"):
            self.assets.add(a["href"])
        if tag == "form" and a.get("action"):
            self.forms.append(((a.get("method") or "GET").upper(), a["action"]))


def _route_exists(path, method):
    import main
    from starlette.routing import Match
    scope = {"type": "http", "path": path, "method": method, "root_path": "", "query_string": b"", "headers": []}
    return any(r.matches(scope)[0] == Match.FULL for r in main.app.routes)


@pytest.mark.parametrize("user,password,branch", [("admin", "admin123", "NORTE"), ("admin", "admin123", "CENTRO"),
                                                  ("tecnico_norte", "tec123", None)])
def test_cp11_navegacion_sin_enlaces_rotos(app_url, user, password, branch):
    s = _session(app_url, user, password, branch)
    queue, seen, problems, assets, forms = ["/"], set(), [], set(), set()
    while queue and len(seen) < 200:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        t0 = time.time()
        r = s.get(app_url + path, allow_redirects=False, timeout=180)
        if time.time() - t0 > 5:
            print(f"[CP-11] lento: {path} {time.time() - t0:.1f}s")
        if r.status_code >= 400 or "/login" in r.headers.get("location", ""):
            problems.append(f"{r.status_code} {path}")
            continue
        if "text/html" not in r.headers.get("content-type", ""):
            continue
        col = _Links()
        col.feed(r.text)
        for href in col.links:
            u = urlparse(urljoin(app_url + path, href))
            if href.startswith(("#", "javascript:", "mailto:")) or u.netloc != urlparse(app_url).netloc or u.path == "/logout":
                continue
            queue.append(u.path + ("?" + u.query if u.query else ""))
        assets |= {urljoin(app_url + path, a) for a in col.assets}
        forms |= {(m, urlparse(urljoin(app_url + path, a)).path) for m, a in col.forms}
    for url in assets:
        assert urlparse(url).netloc == urlparse(app_url).netloc, f"recurso externo (la app debe ser offline): {url}"
        code = s.get(url, timeout=180).status_code
        if code >= 400:
            problems.append(f"{code} recurso {url}")
    problems += [f"formulario sin ruta: {m} {p}" for m, p in forms if not _route_exists(p, m)]
    assert len(seen) > 30
    assert not problems, problems


def _png(color=(200, 30, 30), size=(64, 64)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_cp11_subida_de_imagenes_validada(app_url):
    from PIL import Image
    s = _session(app_url)
    original = fetch_one("SELECT p.name, p.brand, p.category, p.image_path, i.cost, i.price FROM products p "
                         "JOIN inventory i ON i.id = p.id WHERE p.id = 'CAB-USB-C' AND i.branch_id = 'NORTE'")
    form = {"name": original["name"], "brand": original["brand"], "category": original["category"],
            "cost": str(original["cost"]), "price": str(original["price"])}
    url = app_url + "/inventory/item/CAB-USB-C/edit"
    try:
        r = s.post(url, data=form, files={"image": ("foto.jpg", b"<?php system($_GET['c']); ?>", "image/jpeg")}, allow_redirects=False)
        assert r.status_code == 400, "un script disfrazado de .jpg debe rechazarse"

        bomb = io.BytesIO()
        Image.new("L", (10000, 10000), 0).save(bomb, "PNG", optimize=True)
        r = s.post(url, data=form, files={"image": ("bomba.png", bomb.getvalue(), "image/png")}, allow_redirects=False)
        assert r.status_code == 400, "una decompression bomb debe rechazarse"

        poly = _png() + b"<html><script>alert(document.cookie)</script></html>"
        r = s.post(url, data=form, files={"image": ("poly.png", poly, "image/png")}, allow_redirects=False)
        assert r.status_code == 303
        saved = fetch_one("SELECT image_path FROM products WHERE id = 'CAB-USB-C'")["image_path"]
        assert saved.startswith("/static/uploads/products/") and saved.endswith(".webp")
        data = (PROJECT_DIR / saved.lstrip("/")).read_bytes()
        assert data[:4] == b"RIFF" and b"<script" not in data, "la imagen debe recodificarse sin la carga oculta"
    finally:
        current = fetch_one("SELECT image_path FROM products WHERE id = 'CAB-USB-C'")["image_path"] or ""
        if current.startswith("/static/uploads/products/"):
            (PROJECT_DIR / current.lstrip("/")).unlink(missing_ok=True)
        execute("UPDATE products SET image_path = %s WHERE id = 'CAB-USB-C'", (original["image_path"],))


def test_cp11_csrf_por_verificacion_de_origen(app_url):
    s = _session(app_url)
    r = s.post(app_url + "/set_branch/NORTE", headers={"Origin": "http://sitio-malicioso.example"}, allow_redirects=False)
    assert r.status_code == 403
    r = s.post(app_url + "/set_branch/NORTE", headers={"Origin": app_url, "Referer": app_url + "/"}, allow_redirects=False)
    assert r.status_code == 303


def test_cp11_venta_solo_descuenta_su_sucursal(app_url):
    stock = lambda b: fetch_one("SELECT stock FROM inventory WHERE id = 'RAM-8G-D4' AND branch_id = %s", (b,))["stock"]
    norte, centro = stock("NORTE"), stock("CENTRO")
    s = _session(app_url, branch="NORTE")
    r = s.post(app_url + "/pos/checkout", json={"items": [{"id": "RAM-8G-D4", "qty": 1}]})
    assert r.status_code == 200 and r.json()["success"]
    sale_id = r.json()["sale_id"]
    assert stock("NORTE") == norte - 1
    assert stock("CENTRO") == centro, "una venta en NORTE no debe tocar el stock de CENTRO"
    r = s.post(f"{app_url}/pos/receipt/{sale_id}/revert", data={"reason": "CP-11"}, headers={"Referer": app_url + "/"})
    assert r.status_code == 200
    assert stock("NORTE") == norte


def test_cp11_busqueda_y_datos_cifrados(app_url):
    s = _session(app_url, branch="NORTE")
    ids = [r["id"] for r in s.get(app_url + "/inventory/api/search", params={"q": "ssd"}).json()]
    assert "SSD-500G-NVME" in ids, "la búsqueda debe ignorar mayúsculas/minúsculas"
    row = fetch_one("SELECT password FROM customer_devices WHERE id = 'DEV-001'")
    assert row["password"] is not None and b"4821" not in bytes(row["password"]), "el PIN no debe guardarse en texto plano"
    key = dotenv_values(PROJECT_DIR / ".env").get("DEVICE_DATA_KEY")
    assert fetch_one("SELECT pgp_sym_decrypt(password, %s) AS pin FROM customer_devices WHERE id = 'DEV-001'",
                     (key,))["pin"] == "PIN 4821"
    assert re.search(r"PIN 4821", s.get(app_url + "/ticket/REP-001021").text), "el técnico debe poder ver el PIN descifrado"
