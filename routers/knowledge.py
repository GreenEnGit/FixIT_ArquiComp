from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from dependencies import templates, get_db_conn, get_current_user

router = APIRouter()


@router.get("/knowledge", response_class=HTMLResponse)
async def knowledge_base(request: Request, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("SELECT * FROM knowledge_base")
    sops = c.fetchall()
    
    sops_list = []
    categories = set()
    for sop in sops:
        s_dict = dict(sop)
        s_dict["keywords"] = [k.strip() for k in s_dict["keywords"].split(",")]
        cat = s_dict.get("category") or "General"
        categories.add(cat)
        sops_list.append(s_dict)
        
    return templates.TemplateResponse("knowledge.html", {"request": request, "user": user, "sops": sops_list, "categories": sorted(list(categories))})


@router.post("/knowledge/new", response_class=RedirectResponse)
async def add_sop(request: Request, title: str = Form(...), keywords: str = Form(...), content: str = Form(...), category: str = Form("General"), user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    c = db.cursor()
    c.execute("INSERT INTO knowledge_base (title, keywords, content, category) VALUES (?, ?, ?, ?)",
              (title, keywords, content, category))
    db.commit()
    return RedirectResponse(url="/knowledge", status_code=303)
