from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import sqlite3
from datetime import datetime
from pydantic import BaseModel
from typing import List

from dependencies import templates, get_db_conn, get_current_user

router = APIRouter(prefix="/pos", tags=["pos"])

class CartItem(BaseModel):
    id: str
    qty: int

class CheckoutRequest(BaseModel):
    items: List[CartItem]

@router.get("", response_class=HTMLResponse)
async def pos_terminal(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    # Fetch top 50 items for quick access
    c.execute("SELECT * FROM inventory WHERE branch_id = ? AND stock > 0 ORDER BY name ASC LIMIT 50", (user["branch_id"],))
    items = c.fetchall()
    return templates.TemplateResponse("pos.html", {"request": request, "user": user, "items": items})

@router.post("/checkout")
async def checkout_cart(payload: CheckoutRequest, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    total = 0.0
    
    # Validar stock y calcular total
    cart_data = []
    for item in payload.items:
        if item.qty <= 0:
            raise HTTPException(status_code=400, detail="La cantidad de un artículo debe ser mayor a 0.")
            
        c.execute("SELECT * FROM inventory WHERE id = ? AND branch_id = ?", (item.id, user["branch_id"]))
        db_item = c.fetchone()
        if not db_item:
            raise HTTPException(status_code=400, detail=f"Artículo {item.id} no encontrado en sucursal.")
        if db_item["stock"] < item.qty:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {db_item['name']}.")
            
        subtotal = float(db_item["price"]) * item.qty
        total += subtotal
        cart_data.append({
            "item_id": item.id,
            "qty": item.qty,
            "price": float(db_item["price"]),
            "subtotal": subtotal
        })

    # Crear la Venta General
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO sales (total, date, branch_id, username) VALUES (?, ?, ?, ?)",
              (total, now, user["branch_id"], user["username"]))
    sale_id = c.lastrowid

    # Insertar Articulos y Descontar Stock
    for item in cart_data:
        c.execute("INSERT INTO sale_items (sale_id, item_id, qty, price, subtotal) VALUES (?, ?, ?, ?, ?)",
                  (sale_id, item["item_id"], item["qty"], item["price"], item["subtotal"]))
        
        c.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (item["qty"], item["item_id"]))
        
        # Opcional: También registrar en auditoría como "VENTA_DIRECTA" para el historial individual
        c.execute("INSERT INTO audit_logs (username, action, item_id, details, monetary_impact, date, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user["username"], "VENTA_DIRECTA", item["item_id"], f"Ticket #{sale_id}", item["subtotal"], now, user["branch_id"]))

    db.commit()
    return JSONResponse({"success": True, "sale_id": sale_id})

@router.get("/receipt/{sale_id}", response_class=HTMLResponse)
async def pos_receipt(request: Request, sale_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("""
        SELECT s.*, b.name as branch_name, 'Sucursal FixIT' as branch_address 
        FROM sales s 
        JOIN branches b ON s.branch_id = b.id 
        WHERE s.id = ? AND s.branch_id = ?
    """, (sale_id, user["branch_id"]))
    sale = c.fetchone()
    if not sale:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
        
    c.execute("""
        SELECT si.*, i.name, i.brand 
        FROM sale_items si
        JOIN inventory i ON si.item_id = i.id
        WHERE si.sale_id = ?
    """, (sale_id,))
    items = c.fetchall()
    
    return templates.TemplateResponse("pos_receipt.html", {"request": request, "user": user, "sale": sale, "items": items})


@router.post("/receipt/{sale_id}/revert", response_class=RedirectResponse)
async def revert_pos_sale(
    sale_id: int,
    reason: str = Form(...),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    c = db.cursor()
    c.execute("SELECT * FROM sales WHERE id = ? AND branch_id = ?", (sale_id, user["branch_id"]))
    sale = c.fetchone()
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada.")
        
    status = sale["status"] or "COMPLETADA"
    if status.startswith("REVERTIDA"):
        raise HTTPException(status_code=400, detail="Esta venta ya fue revertida previamente.")
        
    # Get sale items
    c.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
    items = c.fetchall()
    
    # Restore stock for each item
    for item in items:
        c.execute("UPDATE inventory SET stock = stock + ? WHERE id = ? AND branch_id = ?", (item["qty"], item["item_id"], user["branch_id"]))
        
    # Mark sale as reverted in database
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    revert_status = f"REVERTIDA por @{user['username']} el {now} | Motivo: {reason}"
    c.execute("UPDATE sales SET status = ?, total = 0.0 WHERE id = ?", (revert_status, sale_id))
    
    # Cancel original audit logs of this sale (set monetary impact to 0.0 and prefix details with [REVERTIDO])
    c.execute(
        "UPDATE audit_logs SET action = 'VENTA_REVERTIDA', details = '[REVERTIDO] ' || details, monetary_impact = 0.0 WHERE details = ? AND action = 'VENTA_DIRECTA' AND branch_id = ?",
        (f"Ticket #{sale_id}", user["branch_id"])
    )
    
    # Add a new audit log entry for the reversion
    desc = f"Venta #{sale_id} Revertida por @{user['username']}. Motivo: {reason}"
    c.execute(
        "INSERT INTO audit_logs (username, action, item_id, details, monetary_impact, date, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["username"], "REVERSION_VENTA", None, desc, 0.0, now, user["branch_id"])
    )
    
    db.commit()
    return RedirectResponse(url=f"/pos/receipt/{sale_id}", status_code=303)

