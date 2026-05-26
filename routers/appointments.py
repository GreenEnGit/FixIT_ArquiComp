from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import uuid
from datetime import datetime
from dependencies import templates, get_db_conn, get_current_user

router = APIRouter()


@router.get("/appointments", response_class=HTMLResponse)
async def appointments_view(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM loaners WHERE branch_id = ?", (user["branch_id"],))
    b_loaners = c.fetchall()
    c.execute("SELECT * FROM appointments WHERE branch_id = ? ORDER BY date, time", (user["branch_id"],))
    b_appointments = c.fetchall()
    return templates.TemplateResponse("appointments.html", {"request": request, "user": user, "loaners": b_loaners, "appointments": b_appointments})


@router.post("/appointments/new", response_class=RedirectResponse)
async def create_appointment(request: Request, customer_name: str = Form(...), service: str = Form(...), date: str = Form(...), time: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("INSERT INTO appointments (customer_name, service, date, time, status, branch_id) VALUES (?, ?, ?, ?, 'PENDIENTE', ?)",
              (customer_name, service, date, time, user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/{appt_id}/status", response_class=RedirectResponse)
async def update_appointment_status(appt_id: int, status: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    if status == 'ELIMINAR':
        c.execute("DELETE FROM appointments WHERE id = ? AND branch_id = ?", (appt_id, user["branch_id"]))
    else:
        c.execute("UPDATE appointments SET status = ? WHERE id = ? AND branch_id = ?", (status, appt_id, user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/loaner/add", response_class=RedirectResponse)
async def add_loaner(request: Request, type: str = Form(...), model: str = Form(...), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    l_id = f"LN-{uuid.uuid4().hex[:8].upper()}"
    c.execute("INSERT INTO loaners (id, type, model, status, branch_id) VALUES (?, ?, ?, ?, ?)",
              (l_id, type, model, "DISPONIBLE", user["branch_id"]))
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/loaner/{loaner_id}/toggle", response_class=RedirectResponse)
async def toggle_loaner(loaner_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT status FROM loaners WHERE id = ? AND branch_id = ?", (loaner_id, user["branch_id"]))
    row = c.fetchone()
    if row:
        new_status = "PRESTADO" if row["status"] == "DISPONIBLE" else "DISPONIBLE"
        c.execute("UPDATE loaners SET status = ? WHERE id = ?", (new_status, loaner_id))
        db.commit()
    return RedirectResponse(url="/appointments", status_code=303)


@router.post("/appointments/loaner/{loaner_id}/delete", response_class=RedirectResponse)
async def delete_loaner(loaner_id: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden eliminar equipos.")
    
    c = db.cursor()
    c.execute("SELECT type, model, status FROM loaners WHERE id = ? AND branch_id = ?", (loaner_id, user["branch_id"]))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
        
    if row["status"] == "PRESTADO":
        raise HTTPException(status_code=400, detail="No se puede eliminar el equipo de préstamo porque está en uso por un cliente (PRESTADO).")
        
    c.execute("DELETE FROM loaners WHERE id = ?", (loaner_id,))
    
    # Audit log
    c.execute("INSERT INTO audit_logs (username, action, item_id, details, date, branch_id) VALUES (?, ?, ?, ?, ?, ?)",
              (user["username"], "ELIMINACION", loaner_id, f"Eliminó equipo de préstamo: {row['type']} {row['model']}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["branch_id"]))
              
    db.commit()
    return RedirectResponse(url="/appointments", status_code=303)
