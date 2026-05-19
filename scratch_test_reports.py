import sqlite3
from decimal import Decimal

conn = sqlite3.connect("taller_prototipo.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Test the query from main.py lines 315-333
start_date = "2026-05-01"
end_date = "2026-05-31"
selected_branch = "TODAS"

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
ticket_query += " GROUP BY t.id ORDER BY t.date DESC"

c.execute(ticket_query, tuple(ticket_params))
raw_tickets = c.fetchall()

print("=== TICKETS IN REPORT ===")
for t in raw_tickets:
    print(dict(t))

# Test CRM LTV calculation
customer_id = "CUST-01"
c.execute("""
    SELECT SUM(t.labor_cost) as total_labor,
           SUM(tp.price * tp.qty) as total_parts
    FROM tickets t
    LEFT JOIN ticket_parts tp ON t.id = tp.ticket_id
    WHERE t.customer_id = ? AND t.status = 'ENTREGADO Y PAGADO'
""", (customer_id,))
ltv_data = c.fetchone()
print("\n=== LTV DATA (CRM CURRENT) ===")
print(dict(ltv_data))

# Test CRM LTV with the proposed fix
c.execute("""
    SELECT t.id, t.labor_cost,
           COALESCE(SUM(tp.price * tp.qty), 0) as parts_total
    FROM tickets t
    LEFT JOIN ticket_parts tp ON t.id = tp.ticket_id
    WHERE t.customer_id = ? AND t.status = 'ENTREGADO Y PAGADO'
    GROUP BY t.id
""", (customer_id,))
tickets_ltv = c.fetchall()
ltv_fixed = sum([Decimal(str(t["labor_cost"])) + Decimal(str(t["parts_total"])) for t in tickets_ltv])
print("\n=== LTV DATA (CRM FIXED) ===")
print(f"LTV: {ltv_fixed}")

conn.close()
