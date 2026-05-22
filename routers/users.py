from fastapi import APIRouter, Request, Depends, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from database import get_password_hash, verify_password
from dependencies import templates, get_db_conn, get_current_user, SECRET_KEY, ALGORITHM
import jwt
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        return HTMLResponse("Acceso denegado. Solo administradores.", status_code=403)
    c = db.cursor()
    c.execute("SELECT id, username, role, branch_id FROM users")
    users_list = c.fetchall()
    c.execute("SELECT id, name FROM branches")
    branches = c.fetchall()
    return templates.TemplateResponse("users.html", {"request": request, "user": user, "users_list": users_list, "branches": branches})

@router.post("/users/new", response_class=RedirectResponse)
async def create_user(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form(...), branch_id: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Enforce constraints
    username = username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="El nombre de usuario debe tener al menos 3 caracteres.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")
    if role not in ["ADMIN", "TECNICO"]:
        raise HTTPException(status_code=400, detail="Rol no válido. Debe ser ADMIN o TECNICO.")
        
    c = db.cursor()
    c.execute("SELECT id FROM branches WHERE id = ?", (branch_id,))
    if not c.fetchone():
        raise HTTPException(status_code=400, detail="Sucursal no válida.")
        
    p_hash = get_password_hash(password)
    try:
        c.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (?, ?, ?, ?)", (username, p_hash, role, branch_id))
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")
    return RedirectResponse(url="/users", status_code=303)

# Profile view and update endpoints for self‑service profile management
@router.get("/profile", response_class=HTMLResponse)
async def view_profile(request: Request, user: dict = Depends(get_current_user)):
    # Render profile editing page for the logged‑in user
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@router.post("/profile", response_class=RedirectResponse)
async def update_profile(request: Request, username: str = Form(...), current_password: str = Form(...), new_password: str = Form(None), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    # Validate current password
    c.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],))
    stored = c.fetchone()
    if not stored or not verify_password(current_password, stored["password_hash"]):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta.")
    # Update username if changed and not taken
    if username != user["username"]:
        c.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, user["id"]))
        if c.fetchone():
            raise HTTPException(status_code=400, detail="Nombre de usuario ya en uso.")
        c.execute("UPDATE users SET username = ? WHERE id = ?", (username, user["id"]))
        # Regenerate JWT token with new sub claim
        expire = datetime.utcnow() + timedelta(hours=12)
        payload = {"sub": username, "exp": expire}
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        response = RedirectResponse(url="/profile", status_code=303)
        response.set_cookie(key="session_token", value=token, httponly=True)
    else:
        response = RedirectResponse(url="/profile", status_code=303)
    # Update password if a new one is provided
    if new_password:
        new_hash = get_password_hash(new_password)
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
    db.commit()
    # Audit log
    c.execute("INSERT INTO audit_logs (username, action, item_id, details, date, branch_id) VALUES (?, ?, ?, ?, ?, ?)",
              (user["username"], "ACTUALIZACION_PERFIL", str(user["id"]), f"Actualizó su perfil (username: {username})", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"]))
    db.commit()
    return response

@router.get("/users/backup", response_class=Response)
async def download_backup(user: dict = Depends(get_current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="No autorizado")
    import os
    db_path = "taller_prototipo.db"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database not found")
    return Response(content=open(db_path, "rb").read(), media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename=FixIT_Backup_{os.path.basename(db_path)}"})

@router.post("/users/{user_id}/delete", response_class=RedirectResponse)
async def delete_user(user_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    c = db.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    target_user = c.fetchone()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    if target_user["username"] == user["username"]:
        raise HTTPException(status_code=400, detail="No te puedes eliminar a ti mismo.")
        
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    
    # Audit log
    c.execute("INSERT INTO audit_logs (username, action, item_id, details, date, branch_id) VALUES (?, ?, ?, ?, ?, ?)",
              (user["username"], "ELIMINACION", str(user_id), f"Eliminó al usuario: {target_user['username']}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"]))
              
    db.commit()
    return RedirectResponse(url="/users", status_code=303)

@router.get("/audit", response_class=HTMLResponse)
async def view_audit_logs(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        return HTMLResponse("Acceso denegado. Solo administradores.", status_code=403)
    c = db.cursor()
    c.execute("""
        SELECT a.*, i.name as item_name 
        FROM audit_logs a
        LEFT JOIN inventory i ON a.item_id = i.id
        ORDER BY a.id DESC 
        LIMIT 200
    """)
    logs = c.fetchall()
    return templates.TemplateResponse("audit.html", {"request": request, "user": user, "logs": logs})

@router.post("/set_branch/{branch_id}", response_class=RedirectResponse)
async def set_branch(request: Request, branch_id: str, response: Response, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    c = db.cursor()
    c.execute("SELECT id FROM branches WHERE id = ?", (branch_id,))
    if not c.fetchone():
        raise HTTPException(status_code=400, detail="Sucursal inválida")
        
    referer = request.headers.get("referer", "/")
    from urllib.parse import urlparse
    parsed = urlparse(referer)
    redirect_url = parsed.path
    if parsed.query:
        redirect_url += f"?{parsed.query}"
    if not redirect_url.startswith("/"):
        redirect_url = "/"
        
    res = RedirectResponse(url=redirect_url, status_code=303)
    res.set_cookie(key="active_branch_id", value=branch_id, httponly=True)
    return res


@router.post("/audit/{log_id}/revert", response_class=RedirectResponse)
async def revert_merma_log(
    log_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden revertir mermas")
        
    c = db.cursor()
    c.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,))
    log = c.fetchone()
    if not log:
        raise HTTPException(status_code=404, detail="Registro de auditoría no encontrado")
        
    if log["action"] != "MERMA":
        raise HTTPException(status_code=400, detail="Solo se pueden revertir registros de tipo Merma")
        
    details = log["details"] or ""
    if details.startswith("[REVERTIDO]"):
        raise HTTPException(status_code=400, detail="Esta merma ya fue revertida previamente")
        
    import re
    match = re.search(r"Merma:\s*(\d+)\s*uds", details)
    if not match:
        raise HTTPException(status_code=400, detail="No se pudo determinar la cantidad a revertir desde el registro")
        
    qty = int(match.group(1))
    item_id = log["item_id"]
    branch_id = log["branch_id"]
    
    # Check if item exists
    c.execute("SELECT id FROM inventory WHERE id = ? AND branch_id = ?", (item_id, branch_id))
    item = c.fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="El componente asociado a esta merma ya no existe en el inventario de esta sucursal")
        
    # Restore stock
    c.execute("UPDATE inventory SET stock = stock + ? WHERE id = ? AND branch_id = ?", (qty, item_id, branch_id))
    
    # Mark log as reverted and zero out its monetary impact
    new_details = f"[REVERTIDO] {details}"
    c.execute("UPDATE audit_logs SET details = ?, monetary_impact = 0.0 WHERE id = ?", (new_details, log_id))
    
    db.commit()
    return RedirectResponse(url="/audit", status_code=303)


@router.post("/audit/{log_id}/revert-restock", response_class=RedirectResponse)
async def revert_restock_log(
    log_id: int,
    reason: str = Form(...),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db_conn)
):
    if user["role"] != "ADMIN" and user["role"] != "TECNICO":
        raise HTTPException(status_code=403, detail="No autorizado")
        
    c = db.cursor()
    c.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,))
    log = c.fetchone()
    if not log:
        raise HTTPException(status_code=404, detail="Registro de auditoría no encontrado")
        
    if log["action"] != "RESTOCK":
        raise HTTPException(status_code=400, detail="Solo se pueden revertir registros de tipo RESTOCK")
        
    details = log["details"] or ""
    if details.startswith("[REVERTIDO]"):
        raise HTTPException(status_code=400, detail="Este surtido ya fue revertido previamente")
        
    import re
    match = re.search(r"Surtido:\s*\+(\d+)\s*uds", details)
    if not match:
        raise HTTPException(status_code=400, detail="No se pudo determinar la cantidad a revertir desde el registro")
        
    qty = int(match.group(1))
    item_id = log["item_id"]
    branch_id = log["branch_id"]
    
    # Check if item exists
    c.execute("SELECT * FROM inventory WHERE id = ? AND branch_id = ?", (item_id, branch_id))
    item = c.fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="El componente asociado a este surtido ya no existe en el inventario")
        
    if item["stock"] < qty:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente para revertir (se requiere restar {qty} uds., stock actual es {item['stock']} uds.)")

    # Subtract stock
    c.execute("UPDATE inventory SET stock = stock - ? WHERE id = ? AND branch_id = ?", (qty, item_id, branch_id))
    
    # Mark log as reverted
    new_details = f"[REVERTIDO - ERROR] {details} | Motivo: {reason}"
    c.execute("UPDATE audit_logs SET details = ? WHERE id = ?", (new_details, log_id))
    
    # Insert new audit log for the correction
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    desc = f"Corrección de surtido erróneo (Ticket #{log_id}): -{qty} uds. Motivo: {reason}"
    c.execute(
        "INSERT INTO audit_logs (username, action, item_id, details, monetary_impact, date, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["username"], "CORRECCION_RESTOCK", item_id, desc, 0.0, now, branch_id)
    )
    
    db.commit()
    return RedirectResponse(url="/audit", status_code=303)


