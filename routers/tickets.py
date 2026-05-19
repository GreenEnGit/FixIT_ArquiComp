from fastapi import APIRouter, Request, Depends, Form, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from decimal import Decimal
from datetime import datetime
import asyncio
from dependencies import templates, get_db_conn, get_current_user

router = APIRouter(prefix="/ticket")

TICKET_STATUSES = [
    "RECIBIDO", "EN DIAGNÓSTICO", "ESPERANDO PIEZAS", 
    "EN REPARACIÓN", "LISTO PARA ENTREGA", "ENTREGADO Y PAGADO"
]

import os
from dotenv import load_dotenv
load_dotenv()

async def async_notif(phone: str, device: str):
    message_body = f"FixIT: Tu equipo {device} ya está LISTO PARA ENTREGA. ¡Te esperamos!"
    
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")
    
    if sid and token and from_phone:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            message = client.messages.create(
                body=message_body,
                from_=from_phone,
                to=phone
            )
            print(f"\n[TWILIO REAL] 📱 SMS enviado a {phone}: SID {message.sid}\n")
            return
        except Exception as e:
            print(f"\n[TWILIO ERROR] No se pudo enviar el mensaje: {e}\n")
            
    await asyncio.sleep(2)
    print(f"\n[TWILIO MOCK] 📱 SMS enviado a {phone}: '{message_body}'\n")

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def list_tickets(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("""
        SELECT t.*, c.name as customer_name, d.type || ' ' || d.model as device_str 
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN customer_devices d ON t.device_id = d.id
        WHERE t.branch_id = ?
        ORDER BY t.date DESC
    """, (user["branch_id"],))
    tickets_list = c.fetchall()
    return templates.TemplateResponse("tickets_list.html", {"request": request, "user": user, "tickets": tickets_list})

@router.get("/{ticket_id}", response_class=HTMLResponse)
async def view_ticket(request: Request, ticket_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("""
        SELECT t.*, c.name as customer_name, c.phone as customer_phone, 
               d.type || ' ' || d.model as device_str, d.serial_number, d.condition
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN customer_devices d ON t.device_id = d.id
        WHERE t.id = ?
    """, (ticket_id,))
    ticket = c.fetchone()
    if not ticket: raise HTTPException(status_code=404, detail="Ticket no encontrado")
    
    c.execute("SELECT * FROM ticket_parts WHERE ticket_id = ?", (ticket_id,))
    parts_used = c.fetchall()
    
    subtotal_parts = sum([Decimal(str(p["price"])) * p["qty"] for p in parts_used])
    subtotal = Decimal(str(ticket["labor_cost"])) + subtotal_parts
    
    c.execute("SELECT tax_rate FROM branches WHERE id = ?", (ticket["branch_id"],))
    tax_rate = Decimal(str(c.fetchone()["tax_rate"]))
    tax = (subtotal * tax_rate).quantize(Decimal('0.01'))
    total = subtotal + tax
    
    c.execute("SELECT * FROM payments WHERE ticket_id = ?", (ticket_id,))
    payments = c.fetchall()
    total_paid = sum([Decimal(str(p["amount"])) for p in payments])
    balance = total - total_paid

    c.execute("SELECT * FROM warranties WHERE ticket_id = ?", (ticket_id,))
    warranty = c.fetchone()
    
    t_dict = dict(ticket)
    t_dict["parts_used"] = [dict(p) for p in parts_used]
    
    c.execute("SELECT * FROM inventory WHERE branch_id = ? AND stock > 0", (ticket["branch_id"],))
    available_parts = c.fetchall()
    
    c.execute("SELECT * FROM activities WHERE ticket_id = ? ORDER BY id DESC", (ticket_id,))
    activities = c.fetchall()
    
    c.execute("SELECT * FROM ticket_images WHERE ticket_id = ?", (ticket_id,))
    ticket_images = c.fetchall()
    
    return templates.TemplateResponse("ticket.html", {
        "request": request, "user": user, "ticket": t_dict, "statuses": TICKET_STATUSES,
        "subtotal_parts": float(subtotal_parts), "tax": float(tax), "total": float(total),
        "available_parts": available_parts, "payments": payments, "total_paid": float(total_paid),
        "ticket_images": ticket_images,
        "balance": float(balance), "warranty": warranty, "activities": activities
    })

@router.post("/{ticket_id}/status", response_class=RedirectResponse)
async def change_ticket_status(ticket_id: str, background_tasks: BackgroundTasks, status: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ? AND branch_id = ?", (ticket_id, user["branch_id"]))
    ticket = c.fetchone()
    if not ticket:
        raise HTTPException(status_code=403, detail="No tienes permiso para modificar este ticket.")
        
    if status == "ENTREGADO Y PAGADO" and ticket["status"] != "ENTREGADO Y PAGADO":
        raise HTTPException(status_code=400, detail="Debes utilizar el módulo de 'Registrar Pago (Caja)' para liquidar el ticket y subir la evidencia. No se puede marcar manualmente desde aquí.")
    
    c.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
    c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
              (ticket_id, f"Cambió a {status}", "Justo ahora", ticket["branch_id"]))
    db.commit()
    
    if status == "LISTO PARA ENTREGA":
        c.execute("SELECT c.phone, d.type || ' ' || d.model as device_str FROM tickets t JOIN customers c ON t.customer_id=c.id JOIN customer_devices d ON t.device_id=d.id WHERE t.id=?", (ticket_id,))
        info = c.fetchone()
        if info:
            background_tasks.add_task(async_notif, info["phone"], info["device_str"])
                
    return RedirectResponse(url=f"/ticket/{ticket_id}", status_code=303)

@router.post("/{ticket_id}/pay", response_class=RedirectResponse)
async def register_payment(ticket_id: str, amount: float = Form(...), method: str = Form(...), payment_image: UploadFile = File(None), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ? AND branch_id = ?", (ticket_id, user["branch_id"]))
    ticket = c.fetchone()
    if not ticket:
        raise HTTPException(status_code=403, detail="No tienes permiso para registrar pagos en este ticket.")
    
    c.execute("SELECT * FROM ticket_parts WHERE ticket_id = ?", (ticket_id,))
    parts_used = c.fetchall()
    subtotal_parts = sum([Decimal(str(p["price"])) * p["qty"] for p in parts_used])
    subtotal = Decimal(str(ticket["labor_cost"])) + subtotal_parts
    c.execute("SELECT tax_rate FROM branches WHERE id = ?", (ticket["branch_id"],))
    tax_rate = Decimal(str(c.fetchone()["tax_rate"]))
    total = subtotal + (subtotal * tax_rate).quantize(Decimal('0.01'))
    
    c.execute("SELECT SUM(amount) FROM payments WHERE ticket_id = ?", (ticket_id,))
    total_paid_raw = c.fetchone()[0] or 0
    total_paid = Decimal(str(total_paid_raw)).quantize(Decimal('0.01'))
    total = total.quantize(Decimal('0.01'))
    
    # Validar que suba foto si liquida la cuenta
    if total_paid + Decimal(str(amount)) >= total:
        if not payment_image or not payment_image.filename:
            raise HTTPException(status_code=400, detail="Es obligatorio subir una foto o recibo de pago para liquidar el ticket.")
            
    c.execute("INSERT INTO payments (ticket_id, amount, method, date) VALUES (?, ?, ?, ?)",
              (ticket_id, amount, method, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
              
    # Guardar imagen si se subió
    if payment_image and payment_image.filename:
        import shutil
        import uuid
        import os
        ext = payment_image.filename.split('.')[-1]
        file_name = f"pay_{ticket_id}_{uuid.uuid4().hex[:8]}.{ext}"
        os.makedirs("static/uploads", exist_ok=True)
        file_path = f"static/uploads/{file_name}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(payment_image.file, buffer)
        c.execute("INSERT INTO ticket_images (ticket_id, file_path) VALUES (?, ?)",
                  (ticket_id, f"/{file_path}"))
    
    total_paid = total_paid + Decimal(str(amount))
    
    if total_paid >= total:
        c.execute("UPDATE tickets SET status = 'ENTREGADO Y PAGADO' WHERE id = ?", (ticket_id,))
        c.execute("INSERT INTO warranties (ticket_id, start_date, end_date) VALUES (?, date('now'), date('now', '+30 days'))", (ticket_id,))
        c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
                  (ticket_id, "Pago total recibido, Equipo entregado, Garantía Activa", "Justo ahora", ticket["branch_id"]))
    else:
        c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
                  (ticket_id, f"Abono parcial de ${amount} ({method})", "Justo ahora", ticket["branch_id"]))
                  
    db.commit()
    return RedirectResponse(url=f"/ticket/{ticket_id}", status_code=303)

@router.post("/{ticket_id}/labor_cost", response_class=RedirectResponse)
async def update_labor_cost(ticket_id: str, labor_cost: float = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = c.fetchone()
    if ticket and ticket["status"] != "ENTREGADO Y PAGADO":
        c.execute("UPDATE tickets SET labor_cost = ? WHERE id = ?", (labor_cost, ticket_id))
        c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
                  (ticket_id, f"Actualizó mano de obra a ${labor_cost}", "Justo ahora", ticket["branch_id"]))
        db.commit()
    return RedirectResponse(url=f"/ticket/{ticket_id}", status_code=303)

@router.post("/{ticket_id}/add_part", response_class=RedirectResponse)
async def add_part_to_ticket(ticket_id: str, part_id: str = Form(...), user: dict=Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = c.fetchone()
    
    if ticket and ticket["status"] != "ENTREGADO Y PAGADO":
        c.execute("SELECT * FROM inventory WHERE id = ? AND stock > 0", (part_id,))
        part = c.fetchone()
        if part:
            c.execute("SELECT * FROM ticket_parts WHERE ticket_id = ? AND part_id = ?", (ticket_id, part_id))
            existing = c.fetchone()
            if existing:
                c.execute("UPDATE ticket_parts SET qty = qty + 1 WHERE id = ?", (existing["id"],))
            else:
                c.execute("INSERT INTO ticket_parts (ticket_id, part_id, name, qty, cost, price) VALUES (?, ?, ?, ?, ?, ?)",
                          (ticket_id, part_id, part["name"], 1, part["cost"], part["price"]))
            
            c.execute("UPDATE inventory SET stock = stock - 1 WHERE id = ?", (part_id,))
            c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
                      (ticket_id, f"Agregó refacción: {part['name']}", "Justo ahora", ticket["branch_id"]))
            db.commit()
            
    return RedirectResponse(url=f"/ticket/{ticket_id}", status_code=303)

@router.post("/{ticket_id}/remove_part/{part_id}", response_class=RedirectResponse)
async def remove_part_from_ticket(ticket_id: str, part_id: str, user: dict=Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = c.fetchone()
    
    if ticket and ticket["status"] != "ENTREGADO Y PAGADO":
        c.execute("SELECT * FROM ticket_parts WHERE ticket_id = ? AND part_id = ?", (ticket_id, part_id))
        existing = c.fetchone()
        if existing:
            if existing["qty"] > 1:
                c.execute("UPDATE ticket_parts SET qty = qty - 1 WHERE id = ?", (existing["id"],))
            else:
                c.execute("DELETE FROM ticket_parts WHERE id = ?", (existing["id"],))
            
            c.execute("UPDATE inventory SET stock = stock + 1 WHERE id = ?", (part_id,))
            c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
                      (ticket_id, f"Removió refacción: {existing['name']}", "Justo ahora", ticket["branch_id"]))
            db.commit()
            
    return RedirectResponse(url=f"/ticket/{ticket_id}", status_code=303)

@router.get("/{ticket_id}/invoice", response_class=HTMLResponse)
async def generate_invoice(request: Request, ticket_id: str, db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("""
        SELECT t.*, c.name as customer_name, c.phone as customer_phone, 
               d.type || ' ' || d.model as device_str, d.serial_number, d.condition
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN customer_devices d ON t.device_id = d.id
        WHERE t.id = ?
    """, (ticket_id,))
    ticket = c.fetchone()
    if not ticket: raise HTTPException(status_code=404, detail="Ticket no encontrado")
    
    c.execute("SELECT * FROM ticket_parts WHERE ticket_id = ?", (ticket_id,))
    parts_used = c.fetchall()
    
    subtotal_parts = sum([Decimal(str(p["price"])) * p["qty"] for p in parts_used])
    subtotal = Decimal(str(ticket["labor_cost"])) + subtotal_parts
    
    c.execute("SELECT tax_rate FROM branches WHERE id = ?", (ticket["branch_id"],))
    tax_rate = Decimal(str(c.fetchone()["tax_rate"]))
    tax = (subtotal * tax_rate).quantize(Decimal('0.01'))
    total = subtotal + tax
    
    t_dict = dict(ticket)
    t_dict["parts_used"] = [dict(p) for p in parts_used]
    
    return templates.TemplateResponse("invoice.html", {
        "request": request, "ticket": t_dict, "subtotal_parts": float(subtotal_parts),
        "tax": float(tax), "total": float(total), "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@router.post("/{ticket_id}/comment", response_class=RedirectResponse)
async def add_comment(ticket_id: str, comment: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = c.fetchone()
    if ticket:
        c.execute("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
                  (ticket_id, f"Comentario ({user['username']}): {comment}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticket["branch_id"]))
        db.commit()
    return RedirectResponse(url=f"/ticket/{ticket_id}", status_code=303)

@router.post("/{ticket_id}/delete", response_class=RedirectResponse)
async def delete_ticket(ticket_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden eliminar tickets.")
    
    c = db.cursor()
    # Ensure ticket exists
    c.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
    if not c.fetchone():
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
        
    c.execute("SELECT end_date FROM warranties WHERE ticket_id = ?", (ticket_id,))
    warranty = c.fetchone()
    if warranty and warranty["end_date"] >= datetime.now().strftime("%Y-%m-%d"):
        raise HTTPException(status_code=400, detail="No se puede eliminar este ticket porque tiene una garantía en curso.")
        
    # Manual cascade delete
    c.execute("DELETE FROM ticket_parts WHERE ticket_id = ?", (ticket_id,))
    c.execute("DELETE FROM payments WHERE ticket_id = ?", (ticket_id,))
    c.execute("DELETE FROM warranties WHERE ticket_id = ?", (ticket_id,))
    c.execute("DELETE FROM activities WHERE ticket_id = ?", (ticket_id,))
    c.execute("DELETE FROM ticket_images WHERE ticket_id = ?", (ticket_id,))
    c.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    
    db.commit()
    return RedirectResponse(url="/ticket", status_code=303)
