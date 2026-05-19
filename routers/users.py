from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
import sqlite3
from database import get_password_hash
from dependencies import templates, get_db_conn, get_current_user

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
    if user["role"] != "ADMIN": raise HTTPException(status_code=403, detail="No autorizado")
    c = db.cursor()
    from database import get_password_hash
    p_hash = get_password_hash(password)
    c.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (?, ?, ?, ?)",
              (username, p_hash, role, branch_id))
    db.commit()
    return RedirectResponse(url="/users", status_code=303)

@router.get("/users/backup", response_class=FileResponse)
async def download_backup(user: dict = Depends(get_current_user)):
    if user["role"] != "ADMIN": raise HTTPException(status_code=403, detail="No autorizado")
    import os
    db_path = "taller_prototipo.db"
    if not os.path.exists(db_path): raise HTTPException(status_code=404, detail="Database not found")
    return FileResponse(path=db_path, filename=f"FixIT_Backup_{os.path.basename(db_path)}", media_type="application/octet-stream")

@router.get("/audit", response_class=HTMLResponse)
async def view_audit_logs(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        return HTMLResponse("Acceso denegado. Solo administradores pueden ver los registros de auditoría.", status_code=403)
        
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

@router.post("/users/{user_id}/delete", response_class=RedirectResponse)
async def delete_user(user_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    from fastapi import HTTPException
    from datetime import datetime
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    c = db.cursor()
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    target_user = c.fetchone()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
    if target_user["username"] == user["username"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de administrador.")
        
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    
    # Audit log
    c.execute("INSERT INTO audit_logs (username, action, item_id, details, date, branch_id) VALUES (?, ?, ?, ?, ?, ?)",
              (user["username"], "ELIMINACION", str(user_id), f"Eliminó empleado: {target_user['username']}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"]))
              
    db.commit()
    return RedirectResponse(url="/users", status_code=303)
