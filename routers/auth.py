from fastapi import APIRouter, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
import jwt
from datetime import datetime, timedelta, timezone
import sqlite3
import database
from dependencies import templates, get_db_conn, SECRET_KEY, ALGORITHM

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    
    if user and database.verify_password(password, user["password_hash"]):
        # Create token
        expire = datetime.now(timezone.utc) + timedelta(hours=12)
        payload = {"sub": user["username"], "exp": expire}
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
        return response
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales inválidas"})

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response
