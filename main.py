from fastapi import FastAPI, Request, Form, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import os
import shutil
import asyncio
import sqlite3
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel

import database
from dependencies import templates, get_db_conn, get_current_user
from fastapi.staticfiles import StaticFiles
from routers import auth, inventory, tickets, customers, users, pos

app = FastAPI(title="FixIT v3")

os.makedirs("static/uploads/tickets", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(tickets.router)
app.include_router(customers.router)
app.include_router(users.router)
app.include_router(pos.router)

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
    
    c.execute("""
        SELECT SUM(tp.price * tp.qty) as total_parts_revenue,
               SUM(tp.cost * tp.qty) as total_parts_cost
        FROM ticket_parts tp
        JOIN tickets t ON tp.ticket_id = t.id
        WHERE t.branch_id = ? AND t.status = 'ENTREGADO Y PAGADO'
    """, (branch,))
    parts_totals = c.fetchone()
    
    parts_rev = Decimal(str(parts_totals["total_parts_revenue"] or 0))
    parts_cst = Decimal(str(parts_totals["total_parts_cost"] or 0))
    
    total_labor = sum([Decimal(str(t["labor_cost"])) for t in branch_tickets if t["status"] == "ENTREGADO Y PAGADO"])
    
    total_revenue = total_labor + parts_rev
    total_parts_cost = parts_cst
    net_profit = total_revenue - total_parts_cost

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, 
        "active_tickets": active_tickets, "ready_tickets": ready_tickets,
        "inventory_value": inventory_value, "low_stock_items": low_stock_items,
        "recent_activities": branch_activities, "net_profit": net_profit,
        "total_revenue": total_revenue
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
    
    import uuid
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
              (new_id, "Nuevo ticket", "Justo ahora", branch))
    
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

@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge_base(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM knowledge_base")
    sops = c.fetchall()
    
    sops_list = []
    categories = set()
    for sop in sops:
        s_dict = dict(sop)
        s_dict["keywords"] = [k.strip() for k in s_dict["keywords"].split(",")]
        cat = s_dict.get("category") or "General"
        categories.add(cat)
        sops_list.append(s_dict)
        
    return templates.TemplateResponse("knowledge.html", {"request": request, "user": user, "sops": sops_list, "categories": sorted(list(categories))})

@app.post("/knowledge/new", response_class=RedirectResponse)
async def add_sop(request: Request, title: str = Form(...), keywords: str = Form(...), content: str = Form(...), category: str = Form("General"), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("INSERT INTO knowledge_base (title, keywords, content, category) VALUES (?, ?, ?, ?)",
              (title, keywords, content, category))
    db.commit()
    return RedirectResponse(url="/knowledge", status_code=303)

@app.get("/appointments", response_class=HTMLResponse)
async def appointments_view(request: Request, user: dict=Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM loaners WHERE branch_id = ?", (user["branch_id"],))
    b_loaners = c.fetchall()
    c.execute("SELECT * FROM appointments WHERE branch_id = ? ORDER BY date, time", (user["branch_id"],))
    b_appointments = c.fetchall()
    return templates.TemplateResponse("appointments.html", {"request": request, "user": user, "loaners": b_loaners, "appointments": b_appointments})

@app.post("/appointments/new", response_class=RedirectResponse)
async def create_appointment(request: Request, customer_name: str = Form(...), service: str = Form(...), date: str = Form(...), time: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("INSERT INTO appointments (customer_name, service, date, time, status, branch_id) VALUES (?, ?, ?, ?, 'PENDIENTE', ?)",
              (customer_name, service, date, time, user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)

@app.post("/appointments/{appt_id}/status", response_class=RedirectResponse)
async def update_appointment_status(appt_id: int, status: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    if status == 'ELIMINAR':
        c.execute("DELETE FROM appointments WHERE id = ? AND branch_id = ?", (appt_id, user["branch_id"]))
    else:
        c.execute("UPDATE appointments SET status = ? WHERE id = ? AND branch_id = ?", (status, appt_id, user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)

@app.post("/appointments/loaner/add", response_class=RedirectResponse)
async def add_loaner(request: Request, type: str = Form(...), model: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    import uuid
    l_id = f"LN-{uuid.uuid4().hex[:8].upper()}"
    c.execute("INSERT INTO loaners (id, type, model, status, branch_id) VALUES (?, ?, ?, ?, ?)",
              (l_id, type, model, "DISPONIBLE", user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)

@app.post("/appointments/loaner/{loaner_id}/toggle", response_class=RedirectResponse)
async def toggle_loaner(loaner_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT status FROM loaners WHERE id = ? AND branch_id = ?", (loaner_id, user["branch_id"]))
    row = c.fetchone()
    if row:
        new_status = "PRESTADO" if row["status"] == "DISPONIBLE" else "DISPONIBLE"
        c.execute("UPDATE loaners SET status = ? WHERE id = ?", (new_status, loaner_id))
        db.commit()
    return RedirectResponse(url="/appointments", status_code=303)

@app.post("/appointments/loaner/{loaner_id}/delete", response_class=RedirectResponse)
async def delete_loaner(loaner_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    from fastapi import HTTPException
    from datetime import datetime
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden eliminar equipos.")
    
    c = db.cursor()
    c.execute("SELECT type, model, status FROM loaners WHERE id = ? AND branch_id = ?", (loaner_id, user["branch_id"]))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
        
    if row["status"] == "PRESTADO":
        raise HTTPException(status_code=400, detail="No se puede eliminar el equipo de préstamo porque está en uso por un cliente (PRESTADO).")
        
    c.execute("DELETE FROM loaners WHERE id = ?", (loaner_id,))
    
    # Audit log
    c.execute("INSERT INTO audit_logs (username, action, item_id, details, date, branch_id) VALUES (?, ?, ?, ?, ?, ?)",
              (user["username"], "ELIMINACION", loaner_id, f"Eliminó equipo de préstamo: {row['type']} {row['model']}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"]))
              
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)

@app.get("/reports", response_class=HTMLResponse)
async def financial_reports(request: Request, start_date: str = None, end_date: str = None, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    # require_admin might be needed but for now we follow the user's role logic. (Admins and Tecnicos can see branch specific reports)
    branch = user["branch_id"]
    
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-01") # Primer día del mes
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d") # Día actual

    c = db.cursor()
    
    # Obtener tickets pagados en el rango de fechas con sus totales pre-calculados (Solución N+1)
    c.execute("""
        SELECT t.*, c.name as customer_name, d.type || ' ' || d.model as device_str,
               COALESCE(SUM(tp.price * tp.qty), 0) as parts_revenue,
               COALESCE(SUM(tp.cost * tp.qty), 0) as parts_cost
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN customer_devices d ON t.device_id = d.id
        LEFT JOIN ticket_parts tp ON t.id = tp.ticket_id
        WHERE t.branch_id = ? AND t.status = 'ENTREGADO Y PAGADO'
        AND t.date >= ? AND t.date <= ?
        GROUP BY t.id
        ORDER BY t.date DESC
    """, (branch, start_date, end_date + " 23:59:59"))
    
    raw_tickets = c.fetchall()
    
    total_revenue = Decimal('0.00')
    total_parts_cost = Decimal('0.00')
    
    report_tickets = []
    
    for t in raw_tickets:
        labor = Decimal(str(t["labor_cost"]))
        t_parts_revenue = Decimal(str(t["parts_revenue"]))
        t_parts_cost = Decimal(str(t["parts_cost"]))
        
        t_revenue = labor + t_parts_revenue
        
        total_revenue += t_revenue
        total_parts_cost += t_parts_cost
        
        t_dict = dict(t)
        t_dict["parts_revenue"] = float(t_parts_revenue)
        t_dict["parts_cost"] = float(t_parts_cost)
        t_dict["ticket_profit"] = float(t_revenue - t_parts_cost)
        report_tickets.append(t_dict)
        
    # Obtener Ventas Directas y Mermas de Auditoría
    c.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN action = 'VENTA_DIRECTA' THEN monetary_impact ELSE 0 END), 0) as direct_sales,
            COALESCE(SUM(CASE WHEN action = 'MERMA' THEN monetary_impact ELSE 0 END), 0) as mermas
        FROM audit_logs
        WHERE branch_id = ? AND date >= ? AND date <= ?
    """, (branch, start_date, end_date + " 23:59:59"))
    audit_data = c.fetchone()
    
    direct_sales = Decimal(str(audit_data["direct_sales"]))
    mermas = Decimal(str(audit_data["mermas"])) # This is negative already
    
    net_profit = total_revenue - total_parts_cost + direct_sales + mermas

    return templates.TemplateResponse("reports.html", {
        "request": request, "user": user,
        "start_date": start_date, "end_date": end_date,
        "tickets": report_tickets,
        "total_revenue": float(total_revenue),
        "total_parts_cost": float(total_parts_cost),
        "direct_sales": float(direct_sales),
        "mermas": float(mermas),
        "net_profit": float(net_profit)
    })

class ChatRequest(BaseModel):
    message: str

import os
from dotenv import load_dotenv
load_dotenv()

@app.post("/api/chat")
async def chat_ia(req: ChatRequest, db: sqlite3.Connection = Depends(get_db_conn)):
    text = req.message.lower()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Eres un asistente técnico de reparación de hardware. Responde de forma concisa y profesional."},
                    {"role": "user", "content": text}
                ]
            )
            return JSONResponse(content={"reply": response.choices[0].message.content})
        except Exception as e:
            return JSONResponse(content={"reply": f"Error con la API de OpenAI: {e}"})

    await asyncio.sleep(2)
    respuesta = "No encontré un procedimiento exacto en mi base de conocimientos. Recomiendo un diagnóstico físico completo."
    
    c = db.cursor()
    c.execute("SELECT * FROM knowledge_base")
    sops = c.fetchall()
    
    for sop in sops:
        keywords = [k.strip().lower() for k in sop["keywords"].split(",")]
        if any(keyword in text for keyword in keywords):
            respuesta = f"Basado en los síntomas, he consultado el SOP '{sop['title']}'. Te sugiero intentar:\n\n{sop['content']}"
            break
            
    return JSONResponse(content={"reply": f"[Modo Simulación]\n{respuesta}"})
