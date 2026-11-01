#!/usr/bin/env python3
"""FixIT_ArquiComp — infra/scripts/capture_evidence.py
SCB-1001 — T-11: genera toda la evidencia visual automatizada del proyecto:
  (1) los 4 diagramas de docs/06_arquitectura_y_datos.md -> evidencias/diagramas/*.png (mmdc)
  (2) las capturas de terminal de las 11 practicas -> evidencias/capturas/terminal/P01..P12*.png
  (3) las capturas de la interfaz web FixIT -> evidencias/capturas/ui/UI_01..04.png

Uso:
    python3 infra/scripts/capture_evidence.py --all
    python3 infra/scripts/capture_evidence.py --diagrams --terminal --ui
    python3 infra/scripts/capture_evidence.py --verify
"""
import argparse
import html as html_lib
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from dotenv import dotenv_values

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
EVID_DIR = PROJECT_DIR / "evidencias"
DIAG_DIR = EVID_DIR / "diagramas"
TERM_DIR = EVID_DIR / "capturas" / "terminal"
UI_DIR = EVID_DIR / "capturas" / "ui"

for d in (DIAG_DIR, TERM_DIR, UI_DIR):
    d.mkdir(parents=True, exist_ok=True)

PSQL = 'podman exec --user postgres fixit_pg_master psql -U postgres -d fixit_db'
PSQL_REPLICA = 'podman exec --user postgres fixit_pg_replica psql -U postgres -d fixit_db'

# Contraseñas operativas: se leen de infra/.env (gitignored), nunca
# hardcodeadas aqui (ver auditoria de seguridad post T-11/T-12).
_INFRA_ENV = dotenv_values(PROJECT_DIR / "infra" / ".env")
APP_TECNICO_PASSWORD = _INFRA_ENV["APP_TECNICO_PASSWORD"]


# =====================================================================
# Utilidades de ejecucion y renderizado de terminal
# =====================================================================

def run(cmd, timeout=180):
    proc = subprocess.run(cmd, shell=True, cwd=PROJECT_DIR, capture_output=True,
                           text=True, timeout=timeout)
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    combined = out
    if err:
        combined = f"{combined}\n{err}" if combined else err
    return combined.strip()


TERMINAL_CSS = """
* { box-sizing: border-box; }
body { margin:0; background:#0d1117; font-family: 'Fira Code', 'DejaVu Sans Mono', monospace; }
.window { width: 1280px; border-radius: 10px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,.6); }
.titlebar { background:#21262d; padding: 10px 16px; display:flex; align-items:center; gap:8px; }
.dot { width:12px; height:12px; border-radius:50%; display:inline-block; }
.dot.red{background:#ff5f56} .dot.yellow{background:#ffbd2e} .dot.green{background:#27c93f}
.title { color:#8b949e; font-size:13px; margin-left: 10px; }
.body { padding: 18px 22px; color:#c9d1d9; font-size:13px; line-height:1.5;
        white-space:pre-wrap; word-break:break-word; min-height: 100px; }
.prompt { color:#58a6ff; margin-top: 14px; }
.prompt:first-child { margin-top: 0; }
.cmd { color:#f0f6fc; font-weight:600; }
.out { color:#c9d1d9; }
"""


def build_terminal_html(title, blocks):
    body = ""
    for cmd, output in blocks:
        body += (f'<div class="prompt">fixit@dba-scb1001:~$ '
                 f'<span class="cmd">{html_lib.escape(cmd)}</span></div>\n')
        if output:
            body += f'<div class="out">{html_lib.escape(output)}</div>\n'
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<html><head><meta charset="utf-8"><style>{TERMINAL_CSS}</style></head>
<body><div class="window">
  <div class="titlebar"><span class="dot red"></span><span class="dot yellow"></span><span class="dot green"></span>
    <span class="title">{html_lib.escape(title)} — {ts}</span></div>
  <div class="body">{body}</div>
</div></body></html>"""


def capture_terminal(page, name, title, commands):
    # Cada entrada es un str (se muestra y se ejecuta igual) o una tupla
    # (texto_a_mostrar, comando_a_ejecutar) cuando el comando real contiene
    # un secreto que no debe quedar visible en la captura (ver P02_cuotas).
    blocks = []
    for item in commands:
        if isinstance(item, tuple):
            display_cmd, exec_cmd = item
        else:
            display_cmd = exec_cmd = item
        blocks.append((display_cmd, run(exec_cmd)))
    page.set_content(build_terminal_html(title, blocks))
    path = TERM_DIR / f"{name}.png"
    page.locator(".window").screenshot(path=str(path))
    print(f"[OK] terminal -> {path.relative_to(PROJECT_DIR)}")


# =====================================================================
# 1. Diagramas Mermaid (docs/06_arquitectura_y_datos.md) -> mmdc
# =====================================================================

DIAGRAM_NAMES = [
    "D01_arquitectura_memoria_procesos",
    "D02_distribucion_tablespaces",
    "D03_modelo_relacional_3fn",
    "D04_topologia_replicacion_pitr",
]


def _mmdc_puppeteer_config(chrome_path):
    # mmdc (Puppeteer) no trae su propio Chrome instalado en este entorno;
    # se reutiliza el Chromium que ya gestiona Playwright (confirmado
    # funcional) en vez de requerir una segunda descarga de navegador.
    config_path = PROJECT_DIR / "evidencias" / "diagramas" / ".puppeteer-config.json"
    config_path.write_text(
        f'{{"executablePath": "{chrome_path}", "args": ["--no-sandbox", "--disable-setuid-sandbox"]}}',
        encoding="utf-8",
    )
    return config_path


def render_diagrams(chrome_path):
    doc = (PROJECT_DIR / "docs" / "06_arquitectura_y_datos.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```mermaid\n(.*?)\n```", doc, re.DOTALL)
    if len(blocks) != len(DIAGRAM_NAMES):
        print(f"[ADVERTENCIA] se esperaban {len(DIAGRAM_NAMES)} bloques mermaid, "
              f"se encontraron {len(blocks)}")
    puppeteer_config = _mmdc_puppeteer_config(chrome_path)
    for name, src in zip(DIAGRAM_NAMES, blocks):
        mmd_path = DIAG_DIR / f"{name}.mmd"
        png_path = DIAG_DIR / f"{name}.png"
        mmd_path.write_text(src, encoding="utf-8")
        subprocess.run(
            ["mmdc", "-i", str(mmd_path), "-o", str(png_path), "-w", "1600", "-b", "white",
             "--puppeteerConfigFile", str(puppeteer_config)],
            check=True, cwd=PROJECT_DIR,
        )
        print(f"[OK] diagrama -> {png_path.relative_to(PROJECT_DIR)}")
    puppeteer_config.unlink()


# =====================================================================
# 2. Capturas de terminal de las 11 practicas
# =====================================================================

def render_terminal_captures(page):
    # --- Practica 1: instalar y configurar el SGBD ---
    capture_terminal(page, "P01_versiones_sgbd",
        "Practica 1 — Versiones de los 2 SGBD del laboratorio", [
        "sqlite3 --version",
        f'{PSQL} -c "SELECT version();"',
    ])
    capture_terminal(page, "P01_requerimientos_host",
        "Practica 1 — Verificacion de requerimientos del host", [
        "bash infra/scripts/init_env.sh --check",
    ])
    capture_terminal(page, "P01_procedimiento_instalacion",
        "Practica 1 — Procedimiento de instalacion en Podman", [
        'podman ps --filter name=fixit_pg --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"',
    ])
    capture_terminal(page, "P01_instalacion_transaccional",
        "Practica 1 — Instalacion en modo transaccional (ACID)", [
        f'{PSQL} -c "SHOW default_transaction_isolation;"',
    ])
    capture_terminal(page, "P01_memoria_y_procesos",
        "Practica 1 — Estructura de memoria y procesos de la instancia", [
        f'{PSQL} -c "SHOW shared_buffers;" -c "SHOW work_mem;" -c "SHOW wal_buffers;"',
        'podman exec fixit_pg_master ps -eo pid,comm --sort=pid',
    ])
    capture_terminal(page, "P01_estructura_fisica_disco",
        "Practica 1 — Estructura fisica de directorios (PGDATA y tablespaces)", [
        'podman exec --user postgres fixit_pg_master ls -la /var/lib/postgresql/data',
        'podman exec --user postgres fixit_pg_master ls -la /var/lib/postgresql/tablespaces',
    ])
    capture_terminal(page, "P01_variables_y_archivos_conf",
        "Practica 1 — Variables de ambiente y archivos de configuracion", [
        "cat infra/.env.example",
        "head -20 infra/config/postgresql.conf",
    ])
    capture_terminal(page, "P01_parametros_configurados",
        "Practica 1 — Parametros cargados desde postgresql.conf", [
        f'{PSQL} -c "SELECT name, setting, source FROM pg_settings '
        f'WHERE source = \'configuration file\' ORDER BY name LIMIT 15;"',
    ])
    capture_terminal(page, "P01_comandos_alta_baja",
        "Practica 1 — Comandos generales de alta y baja del SGBD", [
        "bash infra/scripts/ops_modes.sh stop",
        "bash infra/scripts/ops_modes.sh start",
        "bash infra/scripts/ops_modes.sh status",
    ])

    # --- Practica 2: espacios en disco, cuotas y roles ---
    capture_terminal(page, "P02_creacion_tablespaces",
        "Practica 2 — Creacion de los 4 tablespaces (\\db+)", [
        f'{PSQL} -c "\\\\db+"',
    ])
    capture_terminal(page, "P02_objetos_por_tablespace",
        "Practica 2 — Catalogo de tablas por tablespace", [
        f'{PSQL} -c "SELECT c.relname AS tabla, t.spcname AS tablespace '
        f'FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace '
        f'LEFT JOIN pg_tablespace t ON t.oid = c.reltablespace '
        f"WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY tablespace, tabla;\"",
    ])
    capture_terminal(page, "P02_roles_y_privilegios",
        "Practica 2 — Roles RBAC (\\du+)", [
        f'{PSQL} -c "\\\\du+"',
    ])
    _insert_cmd_display = (
        'PGPASSWORD=****** podman exec -e PGPASSWORD -i fixit_pg_master '
        'psql -h 127.0.0.1 -U app_tecnico -d fixit_db -c '
        '"INSERT INTO tickets (id, status, customer_id, device_id, symptom, date, branch_id) '
        "VALUES ('REP-EVID01', 'RECIBIDO', 'CUST-01', 'DEV-001', 'demo cuota', CURRENT_DATE, 'NORTE');\""
    )
    _insert_cmd_exec = (
        f'PGPASSWORD={APP_TECNICO_PASSWORD} podman exec -e PGPASSWORD -i fixit_pg_master '
        'psql -h 127.0.0.1 -U app_tecnico -d fixit_db -c '
        '"INSERT INTO tickets (id, status, customer_id, device_id, symptom, date, branch_id) '
        "VALUES ('REP-EVID01', 'RECIBIDO', 'CUST-01', 'DEV-001', 'demo cuota', CURRENT_DATE, 'NORTE');\""
    )
    capture_terminal(page, "P02_cuotas_limite_usuarios",
        "Practica 2 — Bloqueo por cuota de espacio excedida", [
        f'{PSQL} -c "UPDATE user_disk_quotas SET max_bytes = 10, used_bytes = 0 '
        f"WHERE role_name = 'app_tecnico';\"",
        (_insert_cmd_display, _insert_cmd_exec),
        f'{PSQL} -c "UPDATE user_disk_quotas SET max_bytes = 52428800, used_bytes = 0 '
        f"WHERE role_name = 'app_tecnico';\"",
        f'{PSQL} -c "SELECT * FROM user_disk_quotas;"',
    ])

    # --- Practica 9: migracion (se ejecuta antes de sembrar carga sintetica) ---
    capture_terminal(page, "P09_migracion_sqlite_postgres",
        "Practica 9 — Migracion real SQLite -> PostgreSQL con verificacion", [
        "python3 infra/scripts/migrate_sqlite_to_pg.py --verify",
    ])

    # --- Practica 3: indices y reorganizacion (carga sintetica + reindex) ---
    run("python3 src/data_generator/seed_workload.py --rows 10000")
    run(f'{PSQL} -c "UPDATE tickets SET status = \'EN REPARACIÓN\' '
        f'WHERE id IN (SELECT id FROM tickets ORDER BY id LIMIT 3000); ANALYZE tickets;"')
    capture_terminal(page, "P03_indices_y_reorganizacion",
        "Practica 3 — Carga sintetica (Faker), EXPLAIN y REINDEX", [
        "bash infra/scripts/reindex.sh",
    ])

    # --- Practica 4: modos de operacion ---
    capture_terminal(page, "P04_modos_operacion_recovery",
        "Practica 4 — Transicion entre modos alta / recovery / normal", [
        "bash infra/scripts/ops_modes.sh recovery",
        "bash infra/scripts/ops_modes.sh normal",
    ])

    # --- Practica 5: archivos log ---
    capture_terminal(page, "P05_verificacion_archivos_log",
        "Practica 5 — Verificacion de archivos log y WAL", [
        "bash infra/scripts/ops_modes.sh logs",
    ])

    # --- Practica 7 y 8: respaldo y PITR ---
    run("bash infra/scripts/backup_job.sh")
    capture_terminal(page, "P07_respaldo_base_datos",
        "Practica 7 — Respaldo logico (pg_dump) y fisico (pg_basebackup)", [
        "ls -la backups/",
    ])

    t_safe = run('date "+%Y-%m-%d %H:%M:%S"')
    run(f'{PSQL} -c "DELETE FROM payments;"')
    pitr_output = run(f'bash infra/scripts/restore_pitr.sh "{t_safe}"')
    verify_payments = run(f'{PSQL} -c "SELECT * FROM payments ORDER BY id;"')
    blocks = [
        (f'date  # T_safe registrado: {t_safe}', ""),
        ('psql -c "DELETE FROM payments;"   # desastre simulado', ""),
        (f'bash infra/scripts/restore_pitr.sh "{t_safe}"', pitr_output),
        (f'{PSQL} -c "SELECT * FROM payments ORDER BY id;"', verify_payments),
    ]
    page.set_content(build_terminal_html(
        "Practica 8 — Recuperacion Point-In-Time (PITR)", blocks))
    page.locator(".window").screenshot(path=str(TERM_DIR / "P08_recuperacion_datos_pitr.png"))
    print(f"[OK] terminal -> {(TERM_DIR / 'P08_recuperacion_datos_pitr.png').relative_to(PROJECT_DIR)}")

    # El PITR invalida la timeline de la replica: se reclona antes de continuar.
    run("bash infra/scripts/setup_replication.sh")
    time.sleep(3)

    # --- Practica 6: espejeo y replica ---
    capture_terminal(page, "P06_espejeo_wal_receiver",
        "Practica 6 — Espejeo: streaming de bloques WAL (wal_sender/wal_receiver)", [
        f'{PSQL} -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"',
        f'{PSQL_REPLICA} -c "SELECT pg_is_in_recovery(), pg_last_wal_receive_lsn();"',
    ])
    capture_terminal(page, "P06_replica_maestro_esclavo",
        "Practica 6 — Streaming Replication Maestro-Esclavo", [
        f'{PSQL} -c "INSERT INTO branches (id, name) VALUES (\'EVID-06\', \'Evidencia Replica\');"',
        f'{PSQL_REPLICA} -c "SELECT id, name FROM branches WHERE id = \'EVID-06\';"',
        f'{PSQL_REPLICA} -c "INSERT INTO branches (id, name) VALUES (\'X\', \'no deberia poder\');"',
        f'{PSQL} -c "DELETE FROM branches WHERE id = \'EVID-06\';"',
    ])

    # --- Practica 10: auditoria dinamica ---
    capture_terminal(page, "P10_auditoria_activar_verificar_desactivar",
        "Practica 10 — Activar, verificar y desactivar auditoria dinamica", [
        "bash infra/scripts/toggle_audit.sh on",
        f'{PSQL} -c "UPDATE inventory SET price = price WHERE id = \'CAB-USB-C\';"',
        f'{PSQL} -c "SELECT action, item_id FROM audit_logs WHERE action = \'TRIGGER_UPDATE\' ORDER BY id DESC LIMIT 1;"',
        "bash infra/scripts/toggle_audit.sh off",
        "bash infra/scripts/toggle_audit.sh status",
    ])
    capture_terminal(page, "P10_auditoria_jsonb",
        "Practica 10 — Payload JSONB anterior/nuevo en audit_logs", [
        f'{PSQL} -c "SELECT action, old_data, new_data FROM audit_logs '
        f"WHERE action = 'TRIGGER_UPDATE' ORDER BY id DESC LIMIT 1;\"",
    ])
    run("bash infra/scripts/toggle_audit.sh on")

    # --- Practica 11: monitoreo de recursos ---
    capture_terminal(page, "P11_monitoreo_recursos_sgbd",
        "Practica 11 — Monitoreo de rendimiento y recursos del SGBD", [
        "bash infra/scripts/monitor_resources.sh",
    ])


def render_pytest_capture(page):
    output = run(f"{PROJECT_DIR}/.venv/bin/pytest -v tests/test_dba_scb1001.py 2>&1", timeout=600)
    page.set_content(build_terminal_html(
        "Practica 12 (transversal) — Suite pytest completa", [("pytest -v tests/test_dba_scb1001.py", output)]))
    path = TERM_DIR / "P12_pytest_suite_completa.png"
    page.locator(".window").screenshot(path=str(path))
    print(f"[OK] terminal -> {path.relative_to(PROJECT_DIR)}")


# =====================================================================
# 3. Capturas de la interfaz web FixIT (Playwright)
# =====================================================================

def _wait_port(host, port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


def render_ui_captures(browser):
    env = os.environ.copy()
    proc = subprocess.Popen(
        [str(PROJECT_DIR / ".venv" / "bin" / "uvicorn"), "main:app", "--port", "8000"],
        cwd=PROJECT_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_port("127.0.0.1", 8000, timeout=30):
            raise RuntimeError("uvicorn no respondio a tiempo en :8000")
        time.sleep(1)

        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = context.new_page()

        page.goto("http://127.0.0.1:8000/login")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "admin123")
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(UI_DIR / "UI_01_login_y_dashboard.png"), full_page=True)
        print(f"[OK] ui -> {(UI_DIR / 'UI_01_login_y_dashboard.png').relative_to(PROJECT_DIR)}")

        page.goto("http://127.0.0.1:8000/ticket")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(UI_DIR / "UI_02_tickets_migrados.png"), full_page=True)
        print(f"[OK] ui -> {(UI_DIR / 'UI_02_tickets_migrados.png').relative_to(PROJECT_DIR)}")

        page.goto("http://127.0.0.1:8000/inventory/sales")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(UI_DIR / "UI_03_inventario_refacciones.png"), full_page=True)
        print(f"[OK] ui -> {(UI_DIR / 'UI_03_inventario_refacciones.png').relative_to(PROJECT_DIR)}")

        page.goto("http://127.0.0.1:8000/audit")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(UI_DIR / "UI_04_vista_auditoria_pagos.png"), full_page=True)
        print(f"[OK] ui -> {(UI_DIR / 'UI_04_vista_auditoria_pagos.png').relative_to(PROJECT_DIR)}")

        context.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# =====================================================================
# Verificacion (CP-10)
# =====================================================================

def verify():
    expected = (
        [DIAG_DIR / f"{n}.png" for n in DIAGRAM_NAMES]
        + [UI_DIR / f"UI_0{i}_{s}.png" for i, s in enumerate(
            ["login_y_dashboard", "tickets_migrados", "inventario_refacciones", "vista_auditoria_pagos"], 1)]
    )
    expected += list(TERM_DIR.glob("P*.png"))

    ok = True
    for path in expected:
        if not path.exists():
            print(f"[FALTA] {path.relative_to(PROJECT_DIR)}")
            ok = False
            continue
        size = path.stat().st_size
        header_ok = path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        if size <= 10 * 1024 or not header_ok:
            print(f"[INVALIDO] {path.relative_to(PROJECT_DIR)} ({size} bytes, header_ok={header_ok})")
            ok = False
        else:
            print(f"[OK] {path.relative_to(PROJECT_DIR)} ({size} bytes)")

    n_terminal = len(list(TERM_DIR.glob("*.png")))
    print(f"\nTotal capturas de terminal: {n_terminal}")
    print(f"Total diagramas: {len(list(DIAG_DIR.glob('*.png')))}")
    print(f"Total capturas UI: {len(list(UI_DIR.glob('*.png')))}")
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--diagrams", action="store_true")
    parser.add_argument("--terminal", action="store_true")
    parser.add_argument("--ui", action="store_true")
    parser.add_argument("--pytest-capture", action="store_true",
                         help="Captura P12 (debe ejecutarse despues de escribir tests/test_dba_scb1001.py)")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        sys.exit(0 if verify() else 1)

    do_all = args.all
    with sync_playwright() as p:
        browser = p.chromium.launch()

        if do_all or args.diagrams:
            render_diagrams(p.chromium.executable_path)

        if do_all or args.terminal:
            context = browser.new_context(device_scale_factor=2)
            page = context.new_page()
            render_terminal_captures(page)
            context.close()

        if do_all or args.ui:
            render_ui_captures(browser)

        if args.pytest_capture:
            context = browser.new_context(device_scale_factor=2)
            page = context.new_page()
            render_pytest_capture(page)
            context.close()

        browser.close()

    print("\n== capture_evidence.py completado ==")
