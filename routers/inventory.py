from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import json
from dependencies import templates, get_db_conn, get_current_user, require_admin

router = APIRouter(prefix="/inventory")

@router.get("/sales", response_class=HTMLResponse)
async def inventory_sales(request: Request, branch_id: str = None, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    # Admin can view any branch; regular users see only their own branch
    target_branch = user["branch_id"] if branch_id is None or user["role"] != "ADMIN" else branch_id
    c.execute("SELECT i.*, b.name as branch_name FROM inventory i JOIN branches b ON i.branch_id = b.id WHERE i.branch_id = ?", (target_branch,))
    branch_inventory = c.fetchall()
    return templates.TemplateResponse("inventory_sales.html", {"request": request, "user": user, "items": branch_inventory, "selected_branch": target_branch})

@router.post("/new", response_class=RedirectResponse)
async def create_inventory(request: Request, name: str = Form(...), brand: str = Form(...), category: str = Form(...), cost: float = Form(...), price: float = Form(...), stock: int = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    import uuid
    new_id = f"ITM-{uuid.uuid4().hex[:8].upper()}"
    c.execute("INSERT INTO inventory (id, name, brand, category, specs, stock, cost, price, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (new_id, name, brand, category, "{}", stock, cost, price, user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/inventory/sales", status_code=303)

@router.get("/component/{item_id}", response_class=HTMLResponse)
async def view_component(request: Request, item_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
    item = c.fetchone()
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="El componente que buscas fue eliminado o no existe.")
    specs = {}
    if item["specs"]:
        try:
            specs = json.loads(item["specs"])
        except:
            pass
            
    return templates.TemplateResponse("component.html", {"request": request, "user": user, "item": item, "specs": specs})

@router.get("/barcode/{item_id}", response_class=HTMLResponse)
async def view_barcode(request: Request, item_id: str, db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
    item = c.fetchone()
    
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="El componente que buscas fue eliminado o no existe.")
    return templates.TemplateResponse("barcode.html", {"request": request, "item": item})

@router.post("/deduct/{item_id}", response_class=RedirectResponse)
async def deduct_stock(item_id: str, action: str = Form(...), details: str = Form(""), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    from datetime import datetime
    c = db.cursor()
    c.execute("SELECT stock, cost, price FROM inventory WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    row = c.fetchone()
    if row and row["stock"] > 0:
        # Deduct
        c.execute("UPDATE inventory SET stock = stock - 1 WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
        
        # Validate price non‑negative before impact calculation
        if row["price"] < 0:
            raise HTTPException(status_code=400, detail="El precio del artículo no puede ser negativo.")
        
        # Calculate impact
        impact = 0.00
        if action == "VENTA_DIRECTA":
            impact = row["price"]
            desc = "Venta Mostrador"
        elif action == "MERMA":
            impact = -row["cost"]
            desc = f"Merma: 1 uds. | Justificación: {details or 'Daño/Pérdida'}"
        else:
            desc = details
            
        # Audit Log
        c.execute("INSERT INTO audit_logs (username, action, item_id, details, monetary_impact, date, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (user["username"], action, item_id, desc, impact, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"]))
        log_id = c.lastrowid
        db.commit()
        
        if action == "VENTA_DIRECTA":
            return RedirectResponse(url=f"/inventory/receipt/{log_id}", status_code=303)
            
    return RedirectResponse(url="/inventory/sales", status_code=303)

@router.post("/restock/{item_id}", response_class=RedirectResponse)
async def restock_item(
    item_id: str,
    qty: int = Form(...),
    cost: float = Form(...),
    price: float = Form(...),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    if qty <= 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="La cantidad a surtir debe ser mayor a 0")
        
    if cost < 0 or price < 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="El costo y el precio no pueden ser negativos")
        
    c = db.cursor()
    c.execute("SELECT * FROM inventory WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    item = c.fetchone()
    
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="El componente no existe en esta sucursal.")
        
    # Update stock and costs
    c.execute(
        "UPDATE inventory SET stock = stock + ?, cost = ?, price = ? WHERE id = ? AND branch_id = ?",
        (qty, cost, price, item_id, user["branch_id"])
    )
    
    # Audit log
    from datetime import datetime
    c.execute(
        "INSERT INTO audit_logs (username, action, item_id, details, monetary_impact, date, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user["username"],
            "RESTOCK",
            item_id,
            f"Surtido: +{qty} uds. Nuevo Costo: ${cost:.2f}, Nuevo Precio: ${price:.2f}",
            0.0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user["branch_id"]
        )
    )
    db.commit()
    return RedirectResponse(url="/inventory/sales", status_code=303)


@router.get("/receipt/{log_id}", response_class=HTMLResponse)
async def view_sale_receipt(request: Request, log_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    from fastapi import HTTPException
    c = db.cursor()
    c.execute("""
        SELECT a.*, i.name as item_name, i.brand, b.name as branch_name, 'Sucursal FixIT' as branch_address
        FROM audit_logs a
        JOIN inventory i ON a.item_id = i.id
        JOIN branches b ON a.branch_id = b.id
        WHERE a.id = ? AND a.branch_id = ? AND a.action = 'VENTA_DIRECTA'
    """, (log_id, user["branch_id"]))
    log = c.fetchone()
    
    if not log:
        raise HTTPException(status_code=404, detail="Recibo no encontrado o no pertenece a esta sucursal.")
        
    return templates.TemplateResponse("sale_receipt.html", {"request": request, "user": user, "log": log})

from fastapi.responses import JSONResponse
@router.get("/api/search")
async def search_components(q: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if not q: return JSONResponse([])
    c = db.cursor()
    search_query = f"%{q}%"
    c.execute("""
        SELECT id, name, category, stock 
        FROM inventory 
        WHERE branch_id = ? AND (name LIKE ? OR category LIKE ? OR id LIKE ?) 
        LIMIT 10
    """, (user["branch_id"], search_query, search_query, search_query))
    return JSONResponse([dict(row) for row in c.fetchall()])

@router.post("/component/{item_id}/order", response_class=RedirectResponse)
async def order_stock(item_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    # SIMULACIÓN: Orden Mágica que llega instantáneamente (Prototipo)
    c = db.cursor()
    c.execute("SELECT id FROM inventory WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    if not c.fetchone():
        raise HTTPException(status_code=403, detail="No tienes permiso para ordenar stock de otra sucursal.")
    
    c.execute("UPDATE inventory SET stock = stock + 10 WHERE id = ?", (item_id,))
    # Registrar la orden simulada
    c.execute("INSERT INTO purchase_orders (vendor_id, part_id, qty, status, date) VALUES (?, ?, ?, ?, ?)",
              ("VEND-01", item_id, 10, "COMPLETADA", "Justo ahora"))
    db.commit()
    return RedirectResponse(url=f"/inventory/component/{item_id}", status_code=303)

@router.delete("/item/{item_id}", response_class=RedirectResponse)
async def delete_inventory_item(item_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden eliminar productos del inventario.")
    c = db.cursor()
    c.execute("SELECT stock FROM inventory WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    if row["stock"] != 0:
        raise HTTPException(status_code=400, detail="Solo se pueden eliminar productos con stock 0.")
    c.execute("DELETE FROM inventory WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/inventory/sales", status_code=303)


@router.post("/item/{item_id}/edit", response_class=RedirectResponse)
async def edit_inventory_item(
    item_id: str,
    name: str = Form(...),
    brand: str = Form(...),
    category: str = Form(...),
    cost: float = Form(...),
    price: float = Form(...),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    if cost < 0 or price < 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="El costo y el precio no pueden ser negativos")
        
    c = db.cursor()
    c.execute("SELECT * FROM inventory WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    item = c.fetchone()
    
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="El artículo no existe en esta sucursal.")
        
    c.execute(
        "UPDATE inventory SET name = ?, brand = ?, category = ?, cost = ?, price = ? WHERE id = ? AND branch_id = ?",
        (name, brand, category, cost, price, item_id, user["branch_id"])
    )
    db.commit()
    return RedirectResponse(url="/inventory/sales", status_code=303)


@router.post("/item/{item_id}/clear-to-merma", response_class=RedirectResponse)
async def clear_stock_to_merma(
    item_id: str,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    c = db.cursor()
    c.execute("SELECT name, stock, cost FROM inventory WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    row = c.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Componente no encontrado")
        
    stock_qty = row["stock"]
    if stock_qty <= 0:
        return RedirectResponse(url="/inventory/sales", status_code=303)
        
    cost = row["cost"] or 0.0
    impact = - (stock_qty * cost)
    
    # Update stock to 0
    c.execute("UPDATE inventory SET stock = 0 WHERE id = ? AND branch_id = ?", (item_id, user["branch_id"]))
    
    # Audit Log
    from datetime import datetime
    desc = f"Merma: {stock_qty} uds. | [Vaciado de Stock]"
    c.execute(
        "INSERT INTO audit_logs (username, action, item_id, details, monetary_impact, date, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["username"], "MERMA", item_id, desc, impact, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"])
    )
    db.commit()
    return RedirectResponse(url="/inventory/sales", status_code=303)


