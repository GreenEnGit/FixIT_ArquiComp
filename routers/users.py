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
    c = db.cursor()
    p_hash = get_password_hash(password)
    c.execute("INSERT INTO users (username, password_hash, role, branch_id) VALUES (?, ?, ?, ?)", (username, p_hash, role, branch_id))
    db.commit()
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
