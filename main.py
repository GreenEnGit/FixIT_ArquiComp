from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import shutil
import uuid
import sqlite3
import logging
from decimal import Decimal
from datetime import datetime

import database
from dependencies import templates, get_db_conn, get_current_user
from fastapi.staticfiles import StaticFiles
from routers import auth, inventory, tickets, customers, users, pos, knowledge, appointments, reports, chat

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("fixit")

app = FastAPI(title="FixIT v3", description="Sistema de gestión para talleres de reparación de hardware")

@app.on_event("startup")
def startup():
    database.init_db()
    logger.info("✅ Base de datos inicializada correctamente.")

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

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("error.html", {"request": request, "status_code": exc.status_code, "detail": exc.detail}, status_code=exc.status_code)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    branch = user["branch_id"]
    
    c.execute("""
        SELECT t.*, c.name as customer_name, d.device_str 
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN (SELECT id, type || ' ' || model as device_str FROM customer_devices) d ON t.device_id = d.id
        WHERE t.branch_id = ?
    """, (branch,))
    branch_tickets = c.fetchall()
    
    active_tickets = len([t for t in branch_tickets if t["status"] not in ["LISTO PARA ENTREGA", "ENTREGADO Y PAGADO"]])
    ready_tickets = len([t for t in branch_tickets if t["status"] == "LISTO PARA ENTREGA"])
    
    c.execute("SELECT * FROM inventory WHERE branch_id = ?", (branch,))
    branch_inventory = c.fetchall()
    inventory_value = sum([item["stock"] * item["cost"] for item in branch_inventory])
    low_stock_items = [item for item in branch_inventory if item["stock"] <= 3]
    
    c.execute("SELECT * FROM activities WHERE branch_id = ? ORDER BY id DESC LIMIT 5", (branch,))
    branch_activities = c.fetchall()
    
    # 1. Ingresos y costos de refacciones y mano de obra de tickets cobrados
    c.execute("""
        SELECT t.*,
               COALESCE(SUM(tp.price * tp.qty), 0) as parts_revenue,
               COALESCE(SUM(tp.cost * tp.qty), 0) as parts_cost
        FROM tickets t
        LEFT JOIN ticket_parts tp ON t.id = tp.ticket_id
        WHERE t.branch_id = ? AND t.status = 'ENTREGADO Y PAGADO'
        GROUP BY t.id
    """, (branch,))
    paid_tickets = c.fetchall()
    
    ticket_labor = Decimal('0.00')
    ticket_parts_rev = Decimal('0.00')
    ticket_parts_cst = Decimal('0.00')
    for t in paid_tickets:
        ticket_labor += Decimal(str(t["labor_cost"] or 0))
        ticket_parts_rev += Decimal(str(t["parts_revenue"] or 0))
        ticket_parts_cst += Decimal(str(t["parts_cost"] or 0))
        
    ticket_revenue = ticket_labor + ticket_parts_rev
    
    # 2. Ventas directas (POS) y mermas — filtradas al mes actual para rendimiento
    first_day_of_month = datetime.now().strftime("%Y-%m-01")
    c.execute("""
        SELECT a.*, i.cost as current_cost, si.qty as sale_qty
        FROM audit_logs a
        LEFT JOIN inventory i ON a.item_id = i.id
        LEFT JOIN sales s ON a.details = 'Ticket #' || s.id
        LEFT JOIN sale_items si ON s.id = si.sale_id AND a.item_id = si.item_id
        WHERE a.branch_id = ? AND a.date >= ?
    """, (branch, first_day_of_month))
    branch_audit = c.fetchall()
    
    direct_sales_rev = Decimal('0.00')
    direct_sales_cost = Decimal('0.00')
    mermas_cost = Decimal('0.00')
    
    for row in branch_audit:
        log = dict(row)
        action = log["action"]
        monetary_impact = Decimal(str(log["monetary_impact"] or 0))
        
        if action == "VENTA_DIRECTA":
            qty = log.get("sale_qty") or 1
            item_cost = Decimal(str(log["current_cost"] or 0))
            direct_sales_rev += monetary_impact
            direct_sales_cost += item_cost * qty
        elif action == "MERMA":
            mermas_cost += abs(monetary_impact)
            
    total_revenue = ticket_revenue + direct_sales_rev
    total_cost = ticket_parts_cst + direct_sales_cost + mermas_cost
    net_profit = total_revenue - total_cost

    # --- Datos para Gráficas del Dashboard ---
    
    # 1. Distribución de tickets por estatus
    status_counts = {}
    for t in branch_tickets:
        st = t["status"]
        status_counts[st] = status_counts.get(st, 0) + 1
    chart_status_labels = list(status_counts.keys())
    chart_status_values = list(status_counts.values())
    
    # 2. Top 5 componentes con menor stock (excluyendo stock 0 para que sea accionable)
    sorted_inv = sorted(branch_inventory, key=lambda x: x["stock"])[:5]
    chart_stock_labels = [item["name"][:25] for item in sorted_inv]
    chart_stock_values = [item["stock"] for item in sorted_inv]
    
    # 3. Composición de ingresos (solo admin)
    chart_revenue_labels = ["Mano de Obra", "Refacciones (Tickets)", "Ventas POS"]
    chart_revenue_values = [float(ticket_labor), float(ticket_parts_rev), float(direct_sales_rev)]

    return templates.TemplateResponse("dashboard.html", {
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
    return templates.TemplateResponse("intake.html", {"request": request, "user": user, "ticket_created": False, "statuses": ["RECIBIDO", "EN DIAGNÓSTICO"], "customers": customers})

@app.post("/intake", response_class=HTMLResponse)
async def intake_post(request: Request, existing_customer_id: str=Form(None), nombre: str=Form(None), telefono: str=Form(None), email: str=Form(None), tipo_dispositivo: str=Form(...), marca: str=Form(...), serial_number: str=Form(...), estado_fisico: str=Form(...), sintoma: str=Form(...), images: list[UploadFile] = File(None), user: dict=Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    branch = user["branch_id"]
    
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
    c.execute("INSERT INTO customer_devices (id, customer_id, type, model, serial_number, condition, password, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (dev_id, cust_id, tipo_dispositivo, marca, serial_number, estado_fisico, "", branch))
              
    # 3. Create Ticket
    new_id = f"REP-{uuid.uuid4().hex[:8].upper()}"
    
    c.execute("INSERT INTO tickets (id, status, customer_id, device_id, symptom, date, labor_cost, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (new_id, "RECIBIDO", cust_id, dev_id, sintoma, datetime.now().strftime("%Y-%m-%d"), 0.00, branch))
              
    c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
              (new_id, "Nuevo ticket", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), branch))
    
    db.commit()
    
    # 4. Save Images
    if images:
        upload_dir = "static/uploads/tickets"
        os.makedirs(upload_dir, exist_ok=True)
        for img in images:
            if img.filename:
                ext = os.path.splitext(img.filename)[1]
                safe_filename = f"{uuid.uuid4().hex[:12]}{ext}"
                file_path = os.path.join(upload_dir, safe_filename)
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(img.file, buffer)
                    
                # Use forward slashes for web paths
                web_path = f"/{file_path}".replace("\\", "/")
                c.execute("INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)", (new_id, web_path))
        db.commit()
    
    return templates.TemplateResponse("intake.html", {"request": request, "user": user, "ticket_created": True, "new_ticket_id": new_id})
