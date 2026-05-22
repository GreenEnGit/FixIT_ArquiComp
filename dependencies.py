import sqlite3
import jwt
from fastapi import Request, HTTPException, Cookie, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import database
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key_fixit_for_production_v2_2026")
ALGORITHM = "HS256"

templates = Jinja2Templates(directory="templates")

def get_db_conn():
    conn = database.get_db()
    try:
        yield conn
    finally:
        conn.close()

def get_current_user_optional(session_token: str = Cookie(default=None), db: sqlite3.Connection = Depends(get_db_conn)):
    if not session_token:
        return None
    try:
        payload = jwt.decode(session_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username:
            c = db.cursor()
            c.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = c.fetchone()
            if user:
                return dict(user)
    except:
        return None
    return None

def get_current_user(request: Request, user: dict = Depends(get_current_user_optional), db: sqlite3.Connection = Depends(get_db_conn)):
    if not user:
        # FastAPI no permite RedirectResponse fácilmente en Depends que devuelven HTML
        # Se maneja en main.py usando exception handlers, levantando HTTPException(401)
        raise HTTPException(status_code=401, detail="No autenticado")
    
    if user["role"] == "ADMIN":
        active_branch = request.cookies.get("active_branch_id")
        if active_branch:
            c = db.cursor()
            c.execute("SELECT id FROM branches WHERE id = ?", (active_branch,))
            if c.fetchone():
                user["branch_id"] = active_branch
    return user

def require_admin(user: dict = Depends(get_current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Requiere ADMIN")
    return user
