from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
import sqlite3
from decimal import Decimal
from datetime import datetime
from dependencies import templates, get_db_conn, get_current_user

router = APIRouter()


@router.get("/reports", response_class=HTMLResponse)
async def financial_reports(request: Request, start_date: str = None, end_date: str = None, branch_id: str = None, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db_conn)):
    user_branch = user["branch_id"]
    user_role = user["role"]
    
    if user_role == "ADMIN":
        selected_branch = branch_id if branch_id else "TODAS"
    else:
        selected_branch = user_branch
        
    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-01") # Primer día del mes
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d") # Día actual

    c = db.cursor()
    
    # Obtener todas las sucursales para el filtro en el frontend
    c.execute("SELECT id, name FROM branches")
    all_branches = [dict(row) for row in c.fetchall()]
    
    # 1. Obtener tickets pagados en el rango de fechas con sus totales pre-calculados
    ticket_query = """
        SELECT t.*, c.name as customer_name, d.type || ' ' || d.model as device_str,
               COALESCE(SUM(tp.price * tp.qty), 0) as parts_revenue,
               COALESCE(SUM(tp.cost * tp.qty), 0) as parts_cost
        FROM tickets t
        JOIN customers c ON t.customer_id = c.id
        JOIN customer_devices d ON t.device_id = d.id
        LEFT JOIN ticket_parts tp ON t.id = tp.ticket_id
        WHERE t.status = 'ENTREGADO Y PAGADO'
        AND t.date >= ? AND t.date <= ?
    """
    ticket_params = [start_date, end_date + " 23:59:59"]
    
    if selected_branch != "TODAS":
        ticket_query += " AND t.branch_id = ?"
        ticket_params.append(selected_branch)
        
    ticket_query += " GROUP BY t.id ORDER BY t.date DESC"
    c.execute(ticket_query, tuple(ticket_params))
    raw_tickets = c.fetchall()
    
    ticket_labor = Decimal('0.00')
    ticket_parts_rev = Decimal('0.00')
    ticket_parts_cost = Decimal('0.00')
    
    report_tickets = []
    for t in raw_tickets:
        labor = Decimal(str(t["labor_cost"] or 0))
        t_parts_revenue = Decimal(str(t["parts_revenue"] or 0))
        t_parts_cost = Decimal(str(t["parts_cost"] or 0))
        
        t_revenue = labor + t_parts_revenue
        
        ticket_labor += labor
        ticket_parts_rev += t_parts_revenue
        ticket_parts_cost += t_parts_cost
        
        t_dict = dict(t)
        t_dict["parts_revenue"] = float(t_parts_revenue)
        t_dict["parts_cost"] = float(t_parts_cost)
        t_dict["ticket_profit"] = float(t_revenue - t_parts_cost)
        report_tickets.append(t_dict)
        
    ticket_revenue = ticket_labor + ticket_parts_rev
    ticket_profit = ticket_revenue - ticket_parts_cost
    
    # 2. Obtener Ventas Directas y Mermas de Auditoría con qty pre-calculada via JOIN
    audit_query = """
        SELECT a.*, i.name as item_name, i.brand as item_brand, i.cost as current_cost,
               si.qty as sale_qty
        FROM audit_logs a
        LEFT JOIN inventory i ON a.item_id = i.id
        LEFT JOIN sales s ON a.details = 'Ticket #' || s.id
        LEFT JOIN sale_items si ON s.id = si.sale_id AND a.item_id = si.item_id
        WHERE a.date >= ? AND a.date <= ?
    """
    audit_params = [start_date, end_date + " 23:59:59"]
    
    if selected_branch != "TODAS":
        audit_query += " AND a.branch_id = ?"
        audit_params.append(selected_branch)
        
    audit_query += " ORDER BY a.date DESC"
    c.execute(audit_query, tuple(audit_params))
    raw_audit = c.fetchall()
    
    direct_sales_list = []
    mermas_list = []
    
    direct_sales_rev = Decimal('0.00')
    direct_sales_cost = Decimal('0.00')
    mermas_cost = Decimal('0.00')
    
    for row in raw_audit:
        log = dict(row)
        action = log["action"]
        monetary_impact = Decimal(str(log["monetary_impact"] or 0))
        
        if action == "VENTA_DIRECTA":
            qty = log.get("sale_qty") or 1
            
            item_cost = Decimal(str(log["current_cost"] or 0))
            cost_of_this_sale = item_cost * qty
            profit_of_this_sale = monetary_impact - cost_of_this_sale
            
            direct_sales_rev += monetary_impact
            direct_sales_cost += cost_of_this_sale
            
            log["qty"] = qty
            log["cost"] = float(cost_of_this_sale)
            log["profit"] = float(profit_of_this_sale)
            log["price"] = float(monetary_impact / qty) if qty > 0 else 0.0
            
            direct_sales_list.append(log)
            
        elif action == "MERMA":
            loss = abs(monetary_impact)
            mermas_cost += loss
            log["loss"] = float(loss)
            mermas_list.append(log)
            
    total_revenue = ticket_revenue + direct_sales_rev
    total_cost = ticket_parts_cost + direct_sales_cost + mermas_cost
    net_profit = total_revenue - total_cost

    return templates.TemplateResponse("reports.html", {
        "request": request, "user": user,
        "start_date": start_date, "end_date": end_date,
        "branch_id": selected_branch,
        "all_branches": all_branches,
        "tickets": report_tickets,
        "direct_sales": direct_sales_list,
        "mermas": mermas_list,
        
        # Detalle de KPIs
        "ticket_labor": float(ticket_labor),
        "ticket_parts_rev": float(ticket_parts_rev),
        "ticket_parts_cost": float(ticket_parts_cost),
        "ticket_revenue": float(ticket_revenue),
        "ticket_profit": float(ticket_profit),
        
        "direct_sales_rev": float(direct_sales_rev),
        "direct_sales_cost": float(direct_sales_cost),
        "direct_sales_profit": float(direct_sales_rev - direct_sales_cost),
        
        "mermas_cost": float(mermas_cost),
        
        # Totales Consolidados
        "total_revenue": float(total_revenue),
        "total_cost": float(total_cost),
        "net_profit": float(net_profit)
    })
