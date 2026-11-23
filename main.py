from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import os
import uuid
import sqlite3
import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from urllib.parse import urlparse
from datetime import datetime

import database
from dependencies import templates, get_db_conn, get_current_user
from image_utils import sanitize_image, write_upload
from fastapi.staticfiles import StaticFiles
from routers import auth, inventory, tickets, customers, users, pos, knowledge, appointments, reports, chat

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("fixit")

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    logger.info("✅ Base de datos inicializada correctamente.")
    yield


app = FastAPI(title="FixIT v3", description="Sistema de gestión para talleres de reparación de hardware", lifespan=lifespan)

os.makedirs("static/uploads/tickets", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(users.router)
app.include_router(pos.router)
app.include_router(knowledge.router)
app.include_router(appointments.router)
app.include_router(reports.router)
app.include_router(chat.router)

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def csrf_origin_check(request: Request, call_next):
    """Defensa CSRF por verificación de origen (OWASP): toda petición que modifica
    datos y declara Origin/Referer debe venir de este mismo sitio. Los navegadores
    siempre envían Origin en un POST entre sitios, así que un formulario de otro
    dominio no puede actuar con la sesión del usuario."""
    if request.method in _UNSAFE_METHODS:
        source = request.headers.get("origin") or request.headers.get("referer")
        if source and urlparse(source).netloc != request.headers.get("host", ""):
            logger.warning("CSRF bloqueado: %s %s desde %s", request.method, request.url.path, source)
            return templates.TemplateResponse(request, "error.html", {
                "request": request, "status_code": 403,
                "detail": "Solicitud bloqueada: el formulario no proviene de FixIT."}, status_code=403)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "error.html", {"request": request, "status_code": exc.status_code, "detail": exc.detail}, status_code=exc.status_code)

@app.get("/api/nav-counts")
async def nav_counts(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    """Contadores del menú lateral para la sucursal activa."""
    c = db.cursor()
    c.execute("""
        SELECT
          (SELECT COUNT(*) FROM tickets WHERE branch_id = ? AND status NOT IN ('LISTO PARA ENTREGA', 'ENTREGADO Y PAGADO')) AS tickets,
          (SELECT COUNT(*) FROM inventory WHERE branch_id = ? AND stock <= 3) AS stock,
          (SELECT COUNT(*) FROM appointments WHERE branch_id = ? AND status = 'PENDIENTE') AS citas
    """, (user["branch_id"],) * 3)
    return JSONResponse(dict(c.fetchone()))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    branch = user["branch_id"]

    # Todos los indicadores se calculan con agregados en PostgreSQL (no se
    # traen filas completas a Python): escala con la carga sintética de CP-05.

    # Tickets por estatus -> KPIs y gráfica de dona
    c.execute("SELECT status, COUNT(*) AS n FROM tickets WHERE branch_id = ? GROUP BY status ORDER BY status", (branch,))
    status_counts = {r["status"]: r["n"] for r in c.fetchall()}
    active_tickets = sum(n for st, n in status_counts.items() if st not in ("LISTO PARA ENTREGA", "ENTREGADO Y PAGADO"))
    ready_tickets = status_counts.get("LISTO PARA ENTREGA", 0)
    chart_status_labels = list(status_counts.keys())
    chart_status_values = list(status_counts.values())

    # Inventario: valor total, alertas y top 5 de menor stock
    c.execute("SELECT COALESCE(SUM(stock * cost), 0) AS value FROM inventory WHERE branch_id = ?", (branch,))
    inventory_value = c.fetchone()["value"]
    c.execute("SELECT * FROM v_inventory WHERE branch_id = ? AND stock <= 3 ORDER BY stock, name", (branch,))
    low_stock_items = c.fetchall()
    c.execute("SELECT name, stock FROM v_inventory WHERE branch_id = ? ORDER BY stock, name LIMIT 5", (branch,))
    lowest = c.fetchall()
    chart_stock_labels = [r["name"][:25] for r in lowest]
    chart_stock_values = [r["stock"] for r in lowest]

    c.execute("SELECT * FROM activities WHERE branch_id = ? ORDER BY id DESC LIMIT 5", (branch,))
    branch_activities = c.fetchall()

    # 1. Mano de obra, ingreso y costo de refacciones de tickets cobrados
    c.execute("""
        SELECT COALESCE(SUM(t.labor_cost), 0) AS labor,
               COALESCE((SELECT SUM(tp.price * tp.qty) FROM ticket_parts tp JOIN tickets tt ON tt.id = tp.ticket_id
                         WHERE tt.branch_id = ? AND tt.status = 'ENTREGADO Y PAGADO'), 0) AS parts_rev,
               COALESCE((SELECT SUM(tp.cost * tp.qty) FROM ticket_parts tp JOIN tickets tt ON tt.id = tp.ticket_id
                         WHERE tt.branch_id = ? AND tt.status = 'ENTREGADO Y PAGADO'), 0) AS parts_cost
        FROM tickets t
        WHERE t.branch_id = ? AND t.status = 'ENTREGADO Y PAGADO'
    """, (branch, branch, branch))
    row = c.fetchone()
    ticket_labor = Decimal(str(row["labor"]))
    ticket_parts_rev = Decimal(str(row["parts_rev"]))
    ticket_parts_cst = Decimal(str(row["parts_cost"]))
    ticket_revenue = ticket_labor + ticket_parts_rev

    # 2. Ventas directas (POS) y mermas del mes actual, desde la bitácora
    first_day_of_month = datetime.now().strftime("%Y-%m-01")
    c.execute("""
        SELECT
          COALESCE(SUM(a.monetary_impact) FILTER (WHERE a.action = 'VENTA_DIRECTA'), 0) AS sales_rev,
          COALESCE(SUM(COALESCE(si.qty, 1) * COALESCE(i.cost, 0)) FILTER (WHERE a.action = 'VENTA_DIRECTA'), 0) AS sales_cost,
          COALESCE(SUM(ABS(a.monetary_impact)) FILTER (WHERE a.action = 'MERMA'), 0) AS mermas
        FROM audit_logs a
        LEFT JOIN v_inventory i ON a.item_id = i.id AND i.branch_id = a.branch_id
        LEFT JOIN sales s ON a.details = 'Ticket #' || s.id::text
        LEFT JOIN sale_items si ON s.id = si.sale_id AND a.item_id = si.item_id
        WHERE a.branch_id = ? AND a.date >= ?
    """, (branch, first_day_of_month))
    row = c.fetchone()
    direct_sales_rev = Decimal(str(row["sales_rev"]))
    direct_sales_cost = Decimal(str(row["sales_cost"]))
    mermas_cost = Decimal(str(row["mermas"]))

    total_revenue = ticket_revenue + direct_sales_rev
    total_cost = ticket_parts_cst + direct_sales_cost + mermas_cost
    net_profit = total_revenue - total_cost

    # 3. Composición de ingresos (solo admin)
    chart_revenue_labels = ["Mano de Obra", "Refacciones (Tickets)", "Ventas POS"]
    chart_revenue_values = [float(ticket_labor), float(ticket_parts_rev), float(direct_sales_rev)]

    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request, "user": user, 
        "active_tickets": active_tickets, "ready_tickets": ready_tickets,
        "inventory_value": inventory_value, "low_stock_items": low_stock_items,
        "recent_activities": branch_activities, "net_profit": net_profit,
        "total_revenue": total_revenue,
        "chart_status_labels": chart_status_labels,
        "chart_status_values": chart_status_values,
        "chart_stock_labels": chart_stock_labels,
        "chart_stock_values": chart_stock_values,
        "chart_revenue_labels": chart_revenue_labels,
        "chart_revenue_values": chart_revenue_values,
    })

@app.get("/intake", response_class=HTMLResponse)
async def intake_get(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT id, name, phone FROM customers ORDER BY name ASC")
    customers = c.fetchall()
    return templates.TemplateResponse(request, "intake.html", {"request": request, "user": user, "ticket_created": False, "statuses": ["RECIBIDO", "EN DIAGNÓSTICO"], "customers": customers})

@app.post("/intake", response_class=HTMLResponse)
async def intake_post(request: Request, existing_customer_id: str=Form(None), nombre: str=Form(None), telefono: str=Form(None), email: str=Form(None), tipo_dispositivo: str=Form(...), marca: str=Form(...), serial_number: str=Form(...), estado_fisico: str=Form(...), sintoma: str=Form(...), device_password: str=Form(""), images: list[UploadFile] = File(None), user: dict=Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    branch = user["branch_id"]

    # 0. Validar y sanear las fotos ANTES de crear nada: un archivo inválido no deja un ticket a medias.
    clean_images = []
    for img in images or []:
        if img.filename:
            try:
                clean_images.append(sanitize_image(await img.read()))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Foto '{img.filename}': {exc}")
    device_password = (device_password or "").strip()
    if device_password and not database.DEVICE_DATA_KEY:
        raise HTTPException(status_code=500, detail="El servidor no tiene DEVICE_DATA_KEY: no se guardan contraseñas sin cifrar.")

    # 1. Check or Create Customer
    if existing_customer_id:
        cust_id = existing_customer_id
    else:
        c.execute("SELECT id FROM customers WHERE name = ? AND phone = ?", (nombre, telefono))
        cust_row = c.fetchone()
        if cust_row:
            cust_id = cust_row["id"]
        else:
            cust_id = f"CUST-{uuid.uuid4().hex[:8].upper()}"
            c.execute("INSERT INTO customers (id, name, phone, email) VALUES (?, ?, ?, ?)", (cust_id, nombre, telefono, email))
        
    # 2. Create Device
    dev_id = f"DEV-{uuid.uuid4().hex[:8].upper()}"
    c.execute("INSERT INTO customer_devices (id, customer_id, type, model, serial_number, condition, password, branch_id) "
              "VALUES (?, ?, ?, ?, ?, ?, pgp_sym_encrypt(?::text, ?), ?)",
              (dev_id, cust_id, tipo_dispositivo, marca, serial_number, estado_fisico,
               device_password or None, database.DEVICE_DATA_KEY, branch))
              
    # 3. Create Ticket
    new_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
    
    c.execute("INSERT INTO tickets (id, status, customer_id, device_id, symptom, date, labor_cost, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (new_id, "RECIBIDO", cust_id, dev_id, sintoma, datetime.now().strftime("%Y-%m-%d"), 0.00, branch))
              
    c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
              (new_id, "Nuevo ticket", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), branch))
    
    db.commit()
    
    # 4. Save Images
    if clean_images:
        for data in clean_images:
            web_path = write_upload("static/uploads/tickets", new_id, data)
            c.execute("INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)", (new_id, web_path))
        db.commit()
    
    return templates.TemplateResponse(request, "intake.html", {"request": request, "user": user, "ticket_created": True, "new_ticket_id": new_id})
