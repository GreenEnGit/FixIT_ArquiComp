from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from decimal import Decimal
from dependencies import templates, get_db_conn, get_current_user

router = APIRouter()

@router.get("/customers", response_class=HTMLResponse)
async def list_customers(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM customers")
    customers_list = c.fetchall()
    return templates.TemplateResponse("customers.html", {"request": request, "user": user, "customers": customers_list})

@router.post("/customers/new", response_class=RedirectResponse)
async def add_customer(request: Request, name: str = Form(...), phone: str = Form(...), email: str = Form(""), address: str = Form(""), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    import uuid
    c_id = f"CUST-{uuid.uuid4().hex[:8].upper()}"
    c.execute("INSERT INTO customers (id, name, phone, email, address) VALUES (?, ?, ?, ?, ?)",
              (c_id, name, phone, email, address))
    db.commit()
    return RedirectResponse(url="/customers", status_code=303)

@router.get("/devices", response_class=HTMLResponse)
async def list_devices(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("""
        SELECT d.*, c.name as customer_name 
        FROM customer_devices d 
        JOIN customers c ON d.customer_id = c.id
        WHERE d.branch_id = ?
    """, (user["branch_id"],))
    devices_list = c.fetchall()
    return templates.TemplateResponse("devices.html", {"request": request, "user": user, "devices": devices_list})

@router.get("/customer/{customer_id}", response_class=HTMLResponse)
async def view_customer(request: Request, customer_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = c.fetchone()
    
    if not customer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="El perfil del cliente que buscas fue eliminado o no existe.")
    c.execute("""
        SELECT t.*, d.device_str 
        FROM tickets t
        JOIN (SELECT id, type || ' ' || model as device_str FROM customer_devices) d ON t.device_id = d.id
        WHERE t.customer_id = ?
    """, (customer_id,))
    customer_tickets = c.fetchall()
    
    c.execute("""
        SELECT SUM(labor_cost) as total_labor,
               SUM(parts_total) as total_parts
        FROM (
            SELECT t.id, t.labor_cost, COALESCE(SUM(tp.price * tp.qty), 0) as parts_total
            FROM tickets t
            LEFT JOIN ticket_parts tp ON t.id = tp.ticket_id
            WHERE t.customer_id = ? AND t.status = 'ENTREGADO Y PAGADO'
            GROUP BY t.id
        ) sub
    """, (customer_id,))
    ltv_data = c.fetchone()
    ltv = float(ltv_data["total_labor"] or 0) + float(ltv_data["total_parts"] or 0)
    return templates.TemplateResponse("customer.html", {"request": request, "user": user, "customer": customer, "tickets": customer_tickets, "ltv": float(ltv)})

@router.get("/tracking/{ticket_id}", response_class=HTMLResponse)
async def tracking_portal(request: Request, ticket_id: str, db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("""
        SELECT t.*, c.name as customer_name, d.device_str 
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN (SELECT id, type || ' ' || model as device_str FROM customer_devices) d ON t.device_id = d.id
        WHERE t.id = ?
    """, (ticket_id,))
    ticket = c.fetchone()
    c.execute("SELECT * FROM warranties WHERE ticket_id = ?", (ticket_id,))
    warranty = c.fetchone()
        
    return templates.TemplateResponse("tracking.html", {"request": request, "ticket": ticket, "warranty": warranty})

@router.post("/customer/{customer_id}/delete", response_class=RedirectResponse)
async def delete_customer(customer_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    from fastapi import HTTPException
    from datetime import datetime
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden eliminar clientes.")
    
    c = db.cursor()
    c.execute("SELECT name FROM customers WHERE id = ?", (customer_id,))
    cust = c.fetchone()
    if not cust:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
        
    customer_name = cust["name"]
    
    # Cascade delete tickets
    c.execute("SELECT id FROM tickets WHERE customer_id = ?", (customer_id,))
    tickets = c.fetchall()
    
    # Check warranties before deleting anything
    for t in tickets:
        c.execute("SELECT end_date FROM warranties WHERE ticket_id = ?", (t["id"],))
        warranty = c.fetchone()
        if warranty and warranty["end_date"] >= datetime.now().strftime("%Y-%m-%d"):
            raise HTTPException(status_code=400, detail="No se puede eliminar al cliente porque tiene tickets con garantía en curso.")
            
    for t in tickets:
        t_id = t["id"]
        c.execute("DELETE FROM ticket_parts WHERE ticket_id = ?", (t_id,))
        c.execute("DELETE FROM payments WHERE ticket_id = ?", (t_id,))
        c.execute("DELETE FROM warranties WHERE ticket_id = ?", (t_id,))
        c.execute("DELETE FROM activities WHERE ticket_id = ?", (t_id,))
        c.execute("DELETE FROM ticket_images WHERE ticket_id = ?", (t_id,))
    c.execute("DELETE FROM tickets WHERE customer_id = ?", (customer_id,))
    
    # Cascade delete devices
    c.execute("DELETE FROM customer_devices WHERE customer_id = ?", (customer_id,))
    
    # Delete customer
    c.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    
    # Audit log
    c.execute("INSERT INTO audit_logs (username, action, item_id, details, date, branch_id) VALUES (?, ?, ?, ?, ?, ?)",
              (user["username"], "ELIMINACION", customer_id, f"Eliminó cliente {customer_name} y todo su historial.", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"]))
              
    db.commit()
    return RedirectResponse(url="/customers", status_code=303)
