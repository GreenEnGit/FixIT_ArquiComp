import sqlite3
import jwt
import logging
from fastapi import Request, HTTPException, Cookie, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
import database
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("fixit")

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = "dev_default_key_change_in_production_fixit_2026"
    logger.warning("⚠️  SECRET_KEY no está configurada en .env. Usando clave por defecto (NO USAR EN PRODUCCIÓN).")
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
    except (jwt.DecodeError, jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError):
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
