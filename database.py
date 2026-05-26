import sqlite3
import os
import json
from decimal import Decimal
import bcrypt

DB_NAME = "taller_prototipo.db"

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db_exists = os.path.exists(DB_NAME)
    conn = get_db()
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # Create Tables
    cursor.execute('''CREATE TABLE IF NOT EXISTS branches (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        tax_rate REAL DEFAULT 0.16
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        branch_id TEXT,
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS vendors (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        contact TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        brand TEXT NOT NULL,
        category TEXT NOT NULL,
        specs TEXT,
        stock INTEGER NOT NULL,
        cost REAL NOT NULL,
        price REAL NOT NULL,
        branch_id TEXT NOT NULL,
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id TEXT NOT NULL,
        part_id TEXT NOT NULL,
        qty INTEGER NOT NULL,
        status TEXT NOT NULL,
        date TEXT NOT NULL,
        FOREIGN KEY (vendor_id) REFERENCES vendors(id),
        FOREIGN KEY (part_id) REFERENCES inventory(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS customer_devices (
        id TEXT PRIMARY KEY,
        customer_id TEXT,
        type TEXT,
        model TEXT,
        serial_number TEXT,
        condition TEXT,
        password TEXT,
        branch_id TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        device_id TEXT NOT NULL,
        symptom TEXT NOT NULL,
        date TEXT NOT NULL,
        labor_cost REAL NOT NULL DEFAULT 0.00,
        branch_id TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (device_id) REFERENCES customer_devices(id),
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ticket_parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT NOT NULL,
        part_id TEXT NOT NULL,
        name TEXT NOT NULL,
        qty INTEGER NOT NULL,
        cost REAL NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id),
        FOREIGN KEY (part_id) REFERENCES inventory(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT NOT NULL,
        amount REAL NOT NULL,
        method TEXT NOT NULL,
        date TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS warranties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS loaners (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        model TEXT NOT NULL,
        status TEXT NOT NULL,
        branch_id TEXT NOT NULL,
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        service TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        status TEXT NOT NULL,
        branch_id TEXT NOT NULL,
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        keywords TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT DEFAULT 'General'
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT NOT NULL,
        action TEXT NOT NULL,
        time TEXT NOT NULL,
        branch_id TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id),
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ticket_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        item_id TEXT,
        details TEXT,
        monetary_impact REAL DEFAULT 0.00,
        date TEXT NOT NULL,
        branch_id TEXT NOT NULL,
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total REAL NOT NULL,
        date TEXT NOT NULL,
        branch_id TEXT NOT NULL,
        username TEXT NOT NULL,
        status TEXT DEFAULT 'COMPLETADA',
        FOREIGN KEY (branch_id) REFERENCES branches(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        item_id TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (sale_id) REFERENCES sales(id),
        FOREIGN KEY (item_id) REFERENCES inventory(id)
    )''')

    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN status TEXT DEFAULT 'COMPLETADA'")
    except sqlite3.OperationalError:
        pass

    # Create Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_branch ON tickets(branch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets(customer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticket_parts_ticket ON ticket_parts(ticket_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_branch ON inventory(branch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_branch_date ON audit_logs(branch_id, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_date ON tickets(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_ticket ON payments(ticket_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_ticket ON activities(ticket_id)")

    conn.commit()

    if not db_exists:
        import logging
        logging.getLogger("fixit").info("Creando base de datos y aplicando Seed Data inicial v2...")
        _seed_data(conn)

    conn.close()

def _calcular_precio_matricial(costo: float) -> float:
    c = Decimal(str(costo))
    if c <= Decimal('50'): return float((c * Decimal('2.50')).quantize(Decimal('0.01')))
    elif c <= Decimal('300'): return float((c * Decimal('1.80')).quantize(Decimal('0.01')))
    else: return float((c * Decimal('1.25')).quantize(Decimal('0.01')))

def _seed_data(conn):
    c = conn.cursor()
    # Branches
    c.executemany("INSERT OR IGNORE INTO branches (id, name, tax_rate) VALUES (?, ?, ?)", [
        ('NORTE', 'Sucursal Norte', 0.16),
        ('CENTRO', 'Sucursal Centro', 0.16)
    ])

    # Users
    admin_hash = get_password_hash("admin123")
    tecnico_hash = get_password_hash("tec123")
    
    c.executemany("INSERT OR IGNORE INTO users (username, password_hash, role, branch_id) VALUES (?, ?, ?, ?)", [
        ('admin', admin_hash, 'ADMIN', 'NORTE'),
        ('tecnico_norte', tecnico_hash, 'TECNICO', 'NORTE'),
        ('tecnico_centro', tecnico_hash, 'TECNICO', 'CENTRO')
    ])

    # Customers
    c.executemany("INSERT OR IGNORE INTO customers (id, name, phone, email, address) VALUES (?, ?, ?, ?, ?)", [
        ("CUST-01", "María González", "555-123-4567", "maria@ejemplo.com", "Av. Principal 123"),
        ("CUST-02", "Carlos Ruiz", "555-987-6543", "carlos@ejemplo.com", "Calle Centro 456"),
        ("CUST-03", "Fernando Ortiz", "555-444-3333", "fer@ejemplo.com", "Blvd Norte 789"),
        ("CUST-04", "Laura Sánchez", "555-111-2222", "laura@ejemplo.com", "Av. Sur 101")
    ])

    # Vendors
    c.executemany("INSERT OR IGNORE INTO vendors (id, name, contact) VALUES (?, ?, ?)", [
        ("VEND-01", "TechDistributor S.A.", "ventas@techdist.com"),
        ("VEND-02", "Componentes Globales", "soporte@compuglob.com")
    ])

    # Inventory with Specs
    items = [
        ("CAB-USB-C", "Cable USB-C a USB-C", "Ugreen", "ACCESORIO", json.dumps({"Longitud": "1m", "Potencia": "60W", "Color": "Negro"}), 25, 45.00, "NORTE"),
        ("CAB-HDMI-2M", "Cable HDMI 2.1 2 Metros", "AmazonBasics", "ACCESORIO", json.dumps({"Longitud": "2m", "Versión": "2.1", "Resolución": "8K@60Hz"}), 10, 80.00, "CENTRO"),
        ("PST-MX4", "Pasta Térmica Arctic MX-4 4g", "Arctic", "CONSUMIBLE", json.dumps({"Peso": "4g", "Conductividad": "8.5 W/mK"}), 2, 120.00, "NORTE"),
        ("PST-TG1", "Pasta Térmica Thermal Grizzly", "Kryonaut", "CONSUMIBLE", json.dumps({"Peso": "1g", "Conductividad": "12.5 W/mK"}), 5, 250.00, "CENTRO"),
        ("RAM-8G-D4", "Memoria RAM 8GB DDR4", "Kingston Fury", "RAM", json.dumps({"Capacidad": "8GB", "Tipo": "DDR4", "Velocidad": "3200MHz", "Formato": "UDIMM"}), 12, 450.00, "NORTE"),
        ("RAM-16G-D5", "Memoria RAM 16GB DDR5", "Corsair", "RAM", json.dumps({"Capacidad": "16GB", "Tipo": "DDR5", "Velocidad": "5200MHz", "Formato": "UDIMM"}), 6, 950.00, "NORTE"),
        ("SSD-500G-NVME", "Disco Sólido 500GB NVMe", "WD Blue", "ALMACENAMIENTO", json.dumps({"Capacidad": "500GB", "Interfaz": "PCIe Gen3 x4", "Formato": "M.2 2280"}), 3, 700.00, "NORTE"),
        ("SSD-1TB-SATA", "Disco Sólido 1TB SATA III", "Crucial BX500", "ALMACENAMIENTO", json.dumps({"Capacidad": "1TB", "Interfaz": "SATA III", "Formato": "2.5 pulgadas"}), 8, 850.00, "CENTRO"),
        ("CPU-I5-12400F", "Procesador Intel Core i5", "Intel", "CPU", json.dumps({"Socket": "LGA 1700", "Núcleos": "6", "Hilos": "12", "Frecuencia Base": "2.5GHz"}), 2, 2500.00, "NORTE"),
        ("CPU-R5-5600X", "Procesador AMD Ryzen 5", "AMD", "CPU", json.dumps({"Socket": "AM4", "Núcleos": "6", "Hilos": "12", "Frecuencia Base": "3.7GHz"}), 4, 2800.00, "CENTRO"),
        ("GPU-RTX-4060", "Tarjeta Gráfica RTX 4060", "MSI", "GPU", json.dumps({"VRAM": "8GB GDDR6", "Interfaz": "PCIe 4.0 x8", "Puertos": "3x DP, 1x HDMI"}), 1, 5800.00, "NORTE"),
        ("MB-B550M", "Tarjeta Madre B550M AM4", "Gigabyte", "MOTHERBOARD", json.dumps({"Socket": "AM4", "Chipset": "B550", "Formato": "Micro ATX", "RAM Max": "128GB"}), 3, 1900.00, "CENTRO"),
        ("PWR-650W", "Fuente de Poder 650W", "EVGA", "FUENTE", json.dumps({"Potencia": "650W", "Certificación": "80+ Bronze", "Modular": "No"}), 5, 950.00, "NORTE"),
        ("FAN-120MM", "Ventilador Case 120mm", "Cooler Master", "ENFRIAMIENTO", json.dumps({"Tamaño": "120mm", "Iluminación": "ARGB", "RPM": "650-1800"}), 15, 200.00, "NORTE"),
        ("WIFI-USB", "Adaptador WiFi USB", "TP-Link", "RED", json.dumps({"Banda": "Dual Band (2.4/5GHz)", "Estándar": "AC600", "Interfaz": "USB 2.0"}), 11, 220.00, "CENTRO")
    ]
    for item in items:
        precio = _calcular_precio_matricial(item[6])
        c.execute("INSERT OR IGNORE INTO inventory (id, name, brand, category, specs, stock, cost, price, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (item[0], item[1], item[2], item[3], item[4], item[5], item[6], precio, item[7]))

    # Loaners
    c.executemany("INSERT OR IGNORE INTO loaners (id, type, model, status, branch_id) VALUES (?, ?, ?, ?, ?)", [
        ("LOAN-01", "LAPTOP", "Dell Latitude 5490", "DISPONIBLE", "NORTE"),
        ("LOAN-02", "LAPTOP", "ThinkPad T480", "PRESTADO", "CENTRO"),
    ])

    # Appointments
    c.executemany("INSERT INTO appointments (customer_name, service, date, time, status, branch_id) VALUES (?, ?, ?, ?, ?, ?)", [
        ("Alejandro Medina", "Limpieza de Mac y Cambio de Pasta", "Hoy", "10:00 AM", "PENDIENTE", "NORTE"),
        ("Susana Robles", "Cambio de batería iPhone 12", "Hoy", "09:00 AM", "COMPLETADO", "NORTE"),
        ("Roberto Diaz", "Mantenimiento PC Gamer", "Mañana", "12:00 PM", "PENDIENTE", "CENTRO")
    ])

    # Customer Devices
    c.executemany("INSERT OR IGNORE INTO customer_devices (id, customer_id, type, model, serial_number, condition, password, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        ("DEV-001", "CUST-01", "LAPTOP", "HP Pavilion 15", "5CD1234567", "Rayones.", "", "NORTE"),
        ("DEV-002", "CUST-02", "DESKTOP", "Dell OptiPlex", "D123XYZ", "Sucio.", "", "CENTRO"),
        ("DEV-003", "CUST-03", "GPU", "RTX 3070 Ti", "GPU9876543", "Polvo excesivo.", "", "NORTE"),
        ("DEV-004", "CUST-04", "MOTHERBOARD", "ASUS ROG Strix B550-F", "MB112233", "Pines doblados.", "", "CENTRO"),
    ])

    # Tickets
    c.executemany("INSERT OR IGNORE INTO tickets (id, status, customer_id, device_id, symptom, date, labor_cost, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        ("REP-001021", "EN DIAGNÓSTICO", "CUST-01", "DEV-001", "No enciende y huele a quemado.", "2026-05-09", 500.00, "NORTE"),
        ("REP-001022", "ENTREGADO Y PAGADO", "CUST-02", "DEV-002", "Pantalla azul intermitente.", "2026-05-08", 800.00, "CENTRO"),
        ("REP-001023", "RECIBIDO", "CUST-03", "DEV-003", "Cuadros de colores en la pantalla.", "2026-05-09", 0.00, "NORTE"),
        ("REP-001024", "EN REPARACIÓN", "CUST-04", "DEV-004", "Pines doblados en el socket.", "2026-05-09", 1200.00, "CENTRO"),
    ])

    # Ticket Parts
    c.execute("INSERT INTO ticket_parts (ticket_id, part_id, name, qty, cost, price) VALUES (?, ?, ?, ?, ?, ?)",
              ("REP-001022", "RAM-8G-D4", "Memoria RAM 8GB DDR4", 1, 450.00, _calcular_precio_matricial(450.00)))

    # Payments
    c.execute("INSERT INTO payments (ticket_id, amount, method, date) VALUES (?, ?, ?, ?)",
              ("REP-001022", 1250.00, "Tarjeta", "2026-05-08"))

    # Knowledge Base
    try:
        from seed_kb import glossary
        c.executemany("INSERT INTO knowledge_base (title, keywords, content, category) VALUES (?, ?, ?, ?)", glossary)
    except ImportError:
        kb_data = [
            ("Pantalla Azul de la Muerte (BSOD)", "pantalla azul, bsod, reinicia", "1. Verificar códigos de error en visor de eventos. 2. Correr diagnóstico de Memoria RAM.", "General"),
            ("Sobrecalentamiento y Apagado", "apaga, calienta, ventilador", "1. Revisar estado físico de ventiladores. 2. Cambiar pasta térmica.", "General"),
            ("No enciende (Sin energía)", "no enciende, muerta, quemado", "1. Probar con otro cargador/fuente. 2. Drenaje de energía.", "General"),
        ]
        c.executemany("INSERT INTO knowledge_base (title, keywords, content, category) VALUES (?, ?, ?, ?)", kb_data)

    conn.commit()

if __name__ == '__main__':
    init_db()
