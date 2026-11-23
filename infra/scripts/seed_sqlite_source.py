#!/usr/bin/env python3
"""FixIT_ArquiComp — infra/scripts/seed_sqlite_source.py
SCB-1001 — Genera taller_prototipo.db (SQLite 3.45.1) desde cero con el
esquema y los datos de semilla originales del proyecto.

taller_prototipo.db no se versiona en Git (.gitignore: *.db). database.py
fue migrado a psycopg3/PostgreSQL (T-05) y ya no crea este archivo al
arrancar la app, por lo que en un clon nuevo del repositorio no existe.
Este script lo reconstruye de forma reproducible para poder ejecutar
infra/scripts/migrate_sqlite_to_pg.py.

Uso:
    python3 infra/scripts/seed_sqlite_source.py
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal

import bcrypt

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "taller_prototipo.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS branches (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, tax_rate REAL DEFAULT 0.16);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, role TEXT NOT NULL, branch_id TEXT,
    FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, address TEXT);
CREATE TABLE IF NOT EXISTS vendors (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, contact TEXT);
CREATE TABLE IF NOT EXISTS inventory (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, brand TEXT NOT NULL, category TEXT NOT NULL,
    specs TEXT, stock INTEGER NOT NULL, cost REAL NOT NULL, price REAL NOT NULL,
    branch_id TEXT NOT NULL, image_path TEXT, FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_id TEXT NOT NULL, part_id TEXT NOT NULL,
    qty INTEGER NOT NULL, status TEXT NOT NULL, date TEXT NOT NULL,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id), FOREIGN KEY (part_id) REFERENCES inventory(id));
CREATE TABLE IF NOT EXISTS customer_devices (
    id TEXT PRIMARY KEY, customer_id TEXT, type TEXT, model TEXT, serial_number TEXT,
    condition TEXT, password TEXT, branch_id TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id), FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY, status TEXT NOT NULL, customer_id TEXT NOT NULL, device_id TEXT NOT NULL,
    symptom TEXT NOT NULL, date TEXT NOT NULL, labor_cost REAL NOT NULL DEFAULT 0.00,
    branch_id TEXT NOT NULL, FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (device_id) REFERENCES customer_devices(id), FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS ticket_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, part_id TEXT NOT NULL,
    name TEXT NOT NULL, qty INTEGER NOT NULL, cost REAL NOT NULL, price REAL NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id), FOREIGN KEY (part_id) REFERENCES inventory(id));
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, amount REAL NOT NULL,
    method TEXT NOT NULL, date TEXT NOT NULL, FOREIGN KEY (ticket_id) REFERENCES tickets(id));
CREATE TABLE IF NOT EXISTS warranties (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, start_date TEXT NOT NULL,
    end_date TEXT NOT NULL, notes TEXT, FOREIGN KEY (ticket_id) REFERENCES tickets(id));
CREATE TABLE IF NOT EXISTS loaners (
    id TEXT PRIMARY KEY, type TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
    branch_id TEXT NOT NULL, FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT NOT NULL, service TEXT NOT NULL,
    date TEXT NOT NULL, time TEXT NOT NULL, status TEXT NOT NULL, branch_id TEXT NOT NULL,
    FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, keywords TEXT NOT NULL,
    content TEXT NOT NULL, category TEXT DEFAULT 'General');
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, action TEXT NOT NULL,
    time TEXT NOT NULL, branch_id TEXT NOT NULL, FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS ticket_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, file_path TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id));
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, action TEXT NOT NULL,
    item_id TEXT, details TEXT, monetary_impact REAL DEFAULT 0.00, date TEXT NOT NULL,
    branch_id TEXT NOT NULL, FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL NOT NULL, date TEXT NOT NULL,
    branch_id TEXT NOT NULL, username TEXT NOT NULL, status TEXT DEFAULT 'COMPLETADA',
    FOREIGN KEY (branch_id) REFERENCES branches(id));
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, item_id TEXT NOT NULL,
    qty INTEGER NOT NULL, price REAL NOT NULL, subtotal REAL NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(id), FOREIGN KEY (item_id) REFERENCES inventory(id));
"""


def _precio_matricial(costo: float) -> float:
    c = Decimal(str(costo))
    if c <= Decimal("50"):
        return float((c * Decimal("2.50")).quantize(Decimal("0.01")))
    elif c <= Decimal("300"):
        return float((c * Decimal("1.80")).quantize(Decimal("0.01")))
    return float((c * Decimal("1.25")).quantize(Decimal("0.01")))


NOW = datetime.now()


def _d(days_ago: int) -> str:
    """Fecha relativa a hoy (YYYY-MM-DD) para que el dashboard siempre muestre actividad reciente."""
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def _dt(days_ago: int, hour: int, minute: int = 0) -> str:
    return (NOW - timedelta(days=days_ago)).replace(hour=hour, minute=minute, second=0).strftime("%Y-%m-%d %H:%M:%S")


IMG = "/static/img/products/{}.webp"

# (id, nombre, marca, categoria, specs, stock, costo, sucursal)
INVENTORY = [
    # --- Sucursal Norte ---
    ("CAB-USB-C", "Cable USB-C a USB-C 1 m (60 W)", "Ugreen", "ACCESORIO", {"Longitud": "1 m", "Potencia": "60 W", "Datos": "USB 2.0 480 Mbps", "Color": "Negro"}, 25, 45.00, "NORTE"),
    ("PST-MX4", "Pasta Térmica Arctic MX-4 4 g", "Arctic", "CONSUMIBLE", {"Peso": "4 g", "Conductividad": "8.5 W/mK", "Aplicaciones": "~20"}, 2, 120.00, "NORTE"),
    ("RAM-8G-D4", "Memoria RAM 8 GB DDR4 3200 MHz", "Kingston Fury", "RAM", {"Capacidad": "8 GB", "Tipo": "DDR4", "Velocidad": "3200 MHz", "Formato": "UDIMM", "Latencia": "CL16"}, 12, 450.00, "NORTE"),
    ("RAM-16G-D5", "Memoria RAM 16 GB DDR5 5200 MHz", "Corsair Vengeance", "RAM", {"Capacidad": "16 GB", "Tipo": "DDR5", "Velocidad": "5200 MHz", "Formato": "UDIMM", "Latencia": "CL40"}, 6, 950.00, "NORTE"),
    ("SSD-500G-NVME", "SSD 500 GB NVMe M.2 2280", "WD Blue SN580", "ALMACENAMIENTO", {"Capacidad": "500 GB", "Interfaz": "PCIe Gen4 x4", "Formato": "M.2 2280", "Lectura": "4000 MB/s"}, 3, 700.00, "NORTE"),
    ("HDD-1TB-35", "Disco Duro 1 TB 7200 rpm 3.5\"", "Seagate BarraCuda", "ALMACENAMIENTO", {"Capacidad": "1 TB", "Interfaz": "SATA III", "Velocidad": "7200 rpm", "Caché": "64 MB"}, 5, 820.00, "NORTE"),
    ("USB-64G", "Memoria USB 64 GB USB 3.2", "Kingston DataTraveler", "ALMACENAMIENTO", {"Capacidad": "64 GB", "Interfaz": "USB 3.2 Gen 1", "Lectura": "100 MB/s"}, 30, 95.00, "NORTE"),
    ("CPU-I5-12400F", "Procesador Intel Core i5-12400F", "Intel", "CPU", {"Socket": "LGA 1700", "Núcleos": "6", "Hilos": "12", "Frecuencia": "2.5 / 4.4 GHz", "TDP": "65 W"}, 2, 2500.00, "NORTE"),
    ("GPU-RTX-4060", "Tarjeta Gráfica GeForce RTX 4060 8 GB", "MSI Ventus 2X", "GPU", {"VRAM": "8 GB GDDR6", "Interfaz": "PCIe 4.0 x8", "Puertos": "3x DP, 1x HDMI", "Consumo": "115 W"}, 1, 5800.00, "NORTE"),
    ("PWR-650W", "Fuente de Poder 650 W 80+ Bronze", "EVGA", "FUENTE", {"Potencia": "650 W", "Certificación": "80+ Bronze", "Modular": "No", "Ventilador": "120 mm"}, 5, 950.00, "NORTE"),
    ("FAN-120MM", "Ventilador ARGB 120 mm para gabinete", "Cooler Master", "ENFRIAMIENTO", {"Tamaño": "120 mm", "Iluminación": "ARGB", "RPM": "650-1800", "Conector": "4 pines PWM"}, 15, 200.00, "NORTE"),
    ("CLR-TWR-120", "Disipador de Torre para CPU 120 mm", "DeepCool AK400", "ENFRIAMIENTO", {"Heatpipes": "4", "Altura": "155 mm", "TDP soportado": "220 W", "Sockets": "LGA1700 / AM4 / AM5"}, 4, 520.00, "NORTE"),
    ("BAT-LAP-HP", "Batería para Laptop HP 41 Wh (HT03XL)", "HP", "BATERIA", {"Capacidad": "41 Wh", "Voltaje": "11.34 V", "Celdas": "3", "Compatibilidad": "HP 240/250 G7"}, 3, 780.00, "NORTE"),
    ("KBD-MEC-RGB", "Teclado Mecánico RGB Switch Rojo", "Redragon Kumara", "PERIFERICO", {"Switch": "Outemu Red", "Formato": "TKL 87 teclas", "Iluminación": "RGB", "Conexión": "USB"}, 7, 650.00, "NORTE"),
    ("MOU-OPT-USB", "Mouse Óptico Inalámbrico", "Logitech M185", "PERIFERICO", {"Sensor": "Óptico 1000 DPI", "Conexión": "Receptor USB 2.4 GHz", "Batería": "1x AA (12 meses)"}, 18, 180.00, "NORTE"),
    ("ALC-ISO-99", "Alcohol Isopropílico 99% 500 ml", "Electroclean", "CONSUMIBLE", {"Pureza": "99.9%", "Contenido": "500 ml", "Uso": "Limpieza de placas y contactos"}, 9, 85.00, "NORTE"),
    ("KIT-DESARM-24", "Kit de Desarmadores de Precisión 24 pzs", "Truper", "HERRAMIENTA", {"Piezas": "24 puntas", "Tipos": "Phillips, Torx, Pentalobe, Plana", "Mango": "Aluminio"}, 6, 210.00, "NORTE"),
    # --- Sucursal Centro ---
    ("CAB-HDMI-2M", "Cable HDMI 2.1 de 2 metros", "AmazonBasics", "ACCESORIO", {"Longitud": "2 m", "Versión": "2.1", "Resolución": "8K@60Hz / 4K@120Hz"}, 10, 80.00, "CENTRO"),
    ("CAB-RJ45-3M", "Cable de Red Cat 6 de 3 metros", "Steren", "RED", {"Categoría": "Cat 6", "Longitud": "3 m", "Velocidad": "1 Gbps", "Conector": "RJ45"}, 20, 60.00, "CENTRO"),
    ("PST-TG1", "Pasta Térmica Kryonaut 1 g", "Thermal Grizzly", "CONSUMIBLE", {"Peso": "1 g", "Conductividad": "12.5 W/mK"}, 5, 250.00, "CENTRO"),
    ("PAD-TERM-1MM", "Thermal Pads 1 mm (paquete 4 pzs)", "Gelid GP-Extreme", "CONSUMIBLE", {"Grosor": "1 mm", "Conductividad": "12 W/mK", "Medida": "80 x 40 mm"}, 7, 140.00, "CENTRO"),
    ("AIR-COMP-400", "Aire Comprimido 400 ml", "Silimex", "CONSUMIBLE", {"Contenido": "400 ml", "Uso": "Limpieza de polvo en equipos"}, 12, 95.00, "CENTRO"),
    ("SSD-1TB-SATA", "SSD 1 TB SATA III 2.5\"", "Crucial BX500", "ALMACENAMIENTO", {"Capacidad": "1 TB", "Interfaz": "SATA III", "Formato": "2.5 pulgadas", "Lectura": "540 MB/s"}, 8, 850.00, "CENTRO"),
    ("RAM-8G-SO4", "Memoria RAM 8 GB DDR4 SO-DIMM (Laptop)", "Crucial", "RAM", {"Capacidad": "8 GB", "Tipo": "DDR4", "Velocidad": "3200 MHz", "Formato": "SO-DIMM"}, 9, 420.00, "CENTRO"),
    ("CPU-R5-5600X", "Procesador AMD Ryzen 5 5600X", "AMD", "CPU", {"Socket": "AM4", "Núcleos": "6", "Hilos": "12", "Frecuencia": "3.7 / 4.6 GHz", "TDP": "65 W"}, 4, 2800.00, "CENTRO"),
    ("MB-B550M", "Tarjeta Madre B550M AM4", "Gigabyte B550M DS3H", "MOTHERBOARD", {"Socket": "AM4", "Chipset": "B550", "Formato": "Micro ATX", "RAM Máx.": "128 GB"}, 3, 1900.00, "CENTRO"),
    ("GPU-RX-7600", "Tarjeta Gráfica Radeon RX 7600 8 GB", "Sapphire Pulse", "GPU", {"VRAM": "8 GB GDDR6", "Interfaz": "PCIe 4.0 x8", "Puertos": "3x DP, 1x HDMI", "Consumo": "165 W"}, 2, 5200.00, "CENTRO"),
    ("CASE-ATX-MID", "Gabinete ATX Media Torre con Cristal", "Yeyian", "GABINETE", {"Formato": "ATX / Micro ATX", "Panel": "Cristal templado", "Ventiladores": "3x 120 mm incluidos"}, 3, 1100.00, "CENTRO"),
    ("CHG-LAP-65W", "Cargador para Laptop 65 W USB-C", "Lenovo", "ENERGIA", {"Potencia": "65 W", "Conector": "USB-C PD", "Voltaje": "20 V / 3.25 A"}, 8, 390.00, "CENTRO"),
    ("WIFI-USB", "Adaptador WiFi USB Dual Band AC600", "TP-Link Archer T2U", "RED", {"Banda": "2.4 / 5 GHz", "Estándar": "AC600", "Interfaz": "USB 2.0"}, 11, 220.00, "CENTRO"),
    ("RTR-AX1800", "Router WiFi 6 AX1800", "TP-Link Archer AX21", "RED", {"Estándar": "WiFi 6 (802.11ax)", "Velocidad": "1800 Mbps", "Puertos": "4x LAN Gigabit"}, 4, 1150.00, "CENTRO"),
    ("MON-24-IPS", "Monitor 24\" IPS Full HD 75 Hz", "LG 24MK600", "MONITOR", {"Tamaño": "23.8\"", "Panel": "IPS", "Resolución": "1920x1080", "Frecuencia": "75 Hz"}, 3, 2300.00, "CENTRO"),
    ("CAM-1080P", "Cámara Web Full HD 1080p", "Logitech C920", "PERIFERICO", {"Resolución": "1080p @ 30 fps", "Micrófono": "Estéreo", "Enfoque": "Automático"}, 6, 520.00, "CENTRO"),
]


def seed(conn):
    c = conn.cursor()
    c.executemany("INSERT OR IGNORE INTO branches (id, name, tax_rate) VALUES (?, ?, ?)", [
        ("NORTE", "Sucursal Norte", 0.16), ("CENTRO", "Sucursal Centro", 0.16)])

    admin_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    tecnico_hash = bcrypt.hashpw(b"tec123", bcrypt.gensalt()).decode()
    c.executemany("INSERT OR IGNORE INTO users (username, password_hash, role, branch_id) VALUES (?, ?, ?, ?)", [
        ("admin", admin_hash, "ADMIN", "NORTE"),
        ("tecnico_norte", tecnico_hash, "TECNICO", "NORTE"),
        ("tecnico_centro", tecnico_hash, "TECNICO", "CENTRO")])

    c.executemany("INSERT OR IGNORE INTO customers (id, name, phone, email, address) VALUES (?, ?, ?, ?, ?)", [
        ("CUST-01", "María González", "55 1234 5678", "maria.gonzalez@ejemplo.com", "Av. Insurgentes Norte 123, Col. Lindavista"),
        ("CUST-02", "Carlos Ruiz", "55 9876 5432", "carlos.ruiz@ejemplo.com", "Calle Madero 456, Centro"),
        ("CUST-03", "Fernando Ortiz", "55 4444 3333", "fer.ortiz@ejemplo.com", "Blvd. Norte 789, Col. Industrial"),
        ("CUST-04", "Laura Sánchez", "55 1111 2222", "laura.sanchez@ejemplo.com", "Av. Juárez 101, Centro"),
        ("CUST-05", "Diego Hernández", "55 2345 6789", "diego.hdz@ejemplo.com", "Calle Fresno 22, Col. Santa María"),
        ("CUST-06", "Valeria Torres", "55 3456 7890", "valeria.torres@ejemplo.com", "Av. Politécnico 310, Col. Zacatenco"),
        ("CUST-07", "Jorge Ramírez", "55 4567 8901", "jorge.ramirez@ejemplo.com", "Calle 5 de Mayo 77, Centro"),
        ("CUST-08", "Sofía Castillo", "55 5678 9012", "sofia.castillo@ejemplo.com", "Privada Los Pinos 9, Col. Lindavista"),
        ("CUST-09", "Ricardo Morales", "55 6789 0123", "ricardo.morales@ejemplo.com", "Av. Revolución 1500, Col. Guadalupe"),
        ("CUST-10", "Ana Lucía Vega", "55 7890 1234", "analucia.vega@ejemplo.com", "Calle Bolívar 210, Centro"),
        ("CUST-11", "Papelería El Estudiante", "55 8901 2345", "contacto@papeleria-estudiante.ejemplo.com", "Av. Montevideo 45, Col. Lindavista"),
        ("CUST-12", "Miguel Ángel Ríos", "55 9012 3456", "miguel.rios@ejemplo.com", "Calle Isabel la Católica 88, Centro"),
        ("CUST-13", "Despacho Contable Núñez", "55 0123 4567", "admin@contable-nunez.ejemplo.com", "Av. 20 de Noviembre 300, Centro"),
        ("CUST-14", "Paola Jiménez", "55 1357 2468", "paola.jimenez@ejemplo.com", "Calle Cedros 14, Col. Valle Norte")])

    c.executemany("INSERT OR IGNORE INTO vendors (id, name, contact) VALUES (?, ?, ?)", [
        ("VEND-01", "TechDistributor S.A. de C.V.", "ventas@techdist.ejemplo.com"),
        ("VEND-02", "Componentes Globales", "soporte@compuglob.ejemplo.com"),
        ("VEND-03", "Mayorista de Redes del Bajío", "pedidos@redesbajio.ejemplo.com"),
        ("VEND-04", "Refacciones Laptop Express", "compras@laptopexpress.ejemplo.com")])

    for item_id, name, brand, category, specs, stock, cost, branch_id in INVENTORY:
        c.execute(
            "INSERT OR IGNORE INTO inventory (id, name, brand, category, specs, stock, cost, price, branch_id, image_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, name, brand, category, json.dumps(specs, ensure_ascii=False), stock, cost,
             _precio_matricial(cost), branch_id, IMG.format(item_id.lower())))

    c.executemany("INSERT OR IGNORE INTO loaners (id, type, model, status, branch_id) VALUES (?, ?, ?, ?, ?)", [
        ("LOAN-01", "LAPTOP", "Dell Latitude 5490", "DISPONIBLE", "NORTE"),
        ("LOAN-02", "LAPTOP", "Lenovo ThinkPad T480", "PRESTADO", "CENTRO"),
        ("LOAN-03", "LAPTOP", "HP ProBook 440 G6", "PRESTADO", "NORTE"),
        ("LOAN-04", "TABLET", "Samsung Galaxy Tab A8", "DISPONIBLE", "CENTRO"),
        ("LOAN-05", "DESKTOP", "Dell OptiPlex 3070 Micro", "DISPONIBLE", "NORTE")])

    c.executemany("INSERT INTO appointments (customer_name, service, date, time, status, branch_id) VALUES (?, ?, ?, ?, ?, ?)", [
        ("Alejandro Medina", "Limpieza interna y cambio de pasta térmica (MacBook Pro)", _d(0), "10:00", "PENDIENTE", "NORTE"),
        ("Susana Robles", "Cambio de batería de laptop HP", _d(0), "09:00", "COMPLETADO", "NORTE"),
        ("Roberto Díaz", "Mantenimiento preventivo PC Gamer", _d(-1), "12:00", "PENDIENTE", "CENTRO"),
        ("Gabriela Luna", "Instalación de SSD y clonado de disco", _d(-1), "16:30", "PENDIENTE", "NORTE"),
        ("Despacho Contable Núñez", "Configuración de red y router WiFi 6", _d(-2), "11:00", "PENDIENTE", "CENTRO"),
        ("Héctor Salinas", "Diagnóstico de laptop que no carga", _d(-3), "13:00", "PENDIENTE", "NORTE"),
        ("Andrea Pineda", "Ensamble de PC a medida", _d(-4), "17:00", "PENDIENTE", "CENTRO")])

    # Equipos de clientes: (id, cliente, tipo, modelo, serie, condicion, sucursal)
    devices = [
        ("DEV-001", "CUST-01", "LAPTOP", "HP Pavilion 15-eg", "5CD1234567", "Rayones en la tapa, bisagra derecha floja.", "NORTE"),
        ("DEV-002", "CUST-02", "DESKTOP", "Dell OptiPlex 7070", "D123XYZ", "Mucho polvo interno.", "CENTRO"),
        ("DEV-003", "CUST-03", "GPU", "NVIDIA RTX 3070 Ti Founders", "GPU9876543", "Polvo excesivo, ventiladores ruidosos.", "NORTE"),
        ("DEV-004", "CUST-04", "MOTHERBOARD", "ASUS ROG Strix B550-F", "MB112233", "Pines doblados en el socket AM4.", "CENTRO"),
        ("DEV-005", "CUST-05", "LAPTOP", "Lenovo IdeaPad 3 14ALC6", "PF3ABCD1", "Sin daños visibles.", "NORTE"),
        ("DEV-006", "CUST-06", "LAPTOP", "Acer Aspire 5 A515", "NXHZ1234", "Teclado con teclas faltantes (E, R).", "NORTE"),
        ("DEV-007", "CUST-07", "DESKTOP", "PC Gamer (Ryzen 5 3600 / GTX 1660)", "CUSTOM-0071", "Cristal lateral estrellado.", "CENTRO"),
        ("DEV-008", "CUST-08", "LAPTOP", "MacBook Air 13 (2017)", "C02VX1ABCD", "Batería inflada, touchpad levantado.", "NORTE"),
        ("DEV-009", "CUST-09", "ALL-IN-ONE", "HP 24-df All-in-One", "8CC1234XYZ", "Sin daños visibles.", "CENTRO"),
        ("DEV-010", "CUST-10", "LAPTOP", "Dell Inspiron 15 3511", "9ZX8Y76", "Puerto de carga flojo.", "CENTRO"),
        ("DEV-011", "CUST-11", "IMPRESORA", "Epson EcoTank L3250", "X5E1234567", "Manchas de tinta en bandeja.", "NORTE"),
        ("DEV-012", "CUST-12", "LAPTOP", "ASUS TUF Gaming F15", "M3NRKD012345", "Rejillas obstruidas por polvo.", "CENTRO"),
        ("DEV-013", "CUST-13", "DESKTOP", "Lenovo ThinkCentre M70s", "MJ0ABC12", "Sin daños visibles.", "CENTRO"),
        ("DEV-014", "CUST-14", "LAPTOP", "HP 250 G7", "CND9876543", "Pantalla con línea vertical.", "NORTE"),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO customer_devices "
        "(id, customer_id, type, model, serial_number, condition, password, branch_id) "
        "VALUES (?, ?, ?, ?, ?, ?, '', ?)", devices)

    # Tickets: (id, estado, cliente, equipo, sintoma, dias_atras, mano_de_obra, sucursal)
    tickets = [
        ("REP-001021", "EN DIAGNÓSTICO", "CUST-01", "DEV-001", "No enciende y huele a quemado cerca del puerto de carga.", 2, 500.00, "NORTE"),
        ("REP-001022", "ENTREGADO Y PAGADO", "CUST-02", "DEV-002", "Pantalla azul intermitente (MEMORY_MANAGEMENT).", 12, 800.00, "CENTRO"),
        ("REP-001023", "RECIBIDO", "CUST-03", "DEV-003", "Artefactos y cuadros de colores en juegos.", 0, 0.00, "NORTE"),
        ("REP-001024", "EN REPARACIÓN", "CUST-04", "DEV-004", "Pines doblados en el socket, no da video.", 4, 1200.00, "CENTRO"),
        ("REP-001025", "ENTREGADO Y PAGADO", "CUST-05", "DEV-005", "Muy lenta al arrancar; cliente solicita SSD y más RAM.", 15, 450.00, "NORTE"),
        ("REP-001026", "ESPERANDO PIEZAS", "CUST-06", "DEV-006", "Teclado con teclas faltantes y otras que no responden.", 6, 350.00, "NORTE"),
        ("REP-001027", "LISTO PARA ENTREGA", "CUST-07", "DEV-007", "Se apaga al jugar; temperaturas de CPU arriba de 95 °C.", 5, 600.00, "CENTRO"),
        ("REP-001028", "EN REPARACIÓN", "CUST-08", "DEV-008", "Batería inflada; la laptop se apaga sin aviso.", 3, 700.00, "NORTE"),
        ("REP-001029", "ENTREGADO Y PAGADO", "CUST-09", "DEV-009", "No conecta a WiFi después de actualizar Windows.", 9, 300.00, "CENTRO"),
        ("REP-001030", "LISTO PARA ENTREGA", "CUST-10", "DEV-010", "No carga la batería; conector de corriente flojo.", 7, 650.00, "CENTRO"),
        ("REP-001031", "RECIBIDO", "CUST-11", "DEV-011", "Imprime con rayas y no reconoce el cartucho negro.", 1, 0.00, "NORTE"),
        ("REP-001032", "ENTREGADO Y PAGADO", "CUST-12", "DEV-012", "Sobrecalentamiento y ventilador muy ruidoso.", 18, 550.00, "CENTRO"),
        ("REP-001033", "EN DIAGNÓSTICO", "CUST-13", "DEV-013", "Arranca pero no da video después del logo.", 1, 0.00, "CENTRO"),
        ("REP-001034", "ENTREGADO Y PAGADO", "CUST-14", "DEV-014", "Línea vertical en pantalla; se cotiza cambio de panel.", 20, 400.00, "NORTE"),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO tickets (id, status, customer_id, device_id, symptom, date, labor_cost, branch_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(t[0], t[1], t[2], t[3], t[4], _d(t[5]), t[6], t[7]) for t in tickets])

    inv = {i[0]: i for i in INVENTORY}
    parts = [  # (ticket, refaccion, cantidad)
        ("REP-001022", "RAM-8G-D4", 1), ("REP-001024", "MB-B550M", 1),
        ("REP-001025", "SSD-500G-NVME", 1), ("REP-001025", "RAM-8G-D4", 1),
        ("REP-001027", "PST-TG1", 1), ("REP-001027", "AIR-COMP-400", 1),
        ("REP-001028", "PST-MX4", 1), ("REP-001029", "WIFI-USB", 1),
        ("REP-001030", "CHG-LAP-65W", 1), ("REP-001032", "PAD-TERM-1MM", 1), ("REP-001032", "PST-TG1", 1),
        ("REP-001034", "ALC-ISO-99", 1),
    ]
    totals = {}
    for ticket_id, part_id, qty in parts:
        _, name, _, _, _, _, cost, _ = inv[part_id]
        price = _precio_matricial(cost)
        c.execute("INSERT INTO ticket_parts (ticket_id, part_id, name, qty, cost, price) VALUES (?, ?, ?, ?, ?, ?)",
                  (ticket_id, part_id, name, qty, cost, price))
        totals[ticket_id] = totals.get(ticket_id, 0) + price * qty

    methods = ["Tarjeta", "Efectivo", "Transferencia"]
    for n, t in enumerate(t for t in tickets if t[1] == "ENTREGADO Y PAGADO"):
        ticket_id, days, labor = t[0], t[5], t[6]
        amount = round(labor + totals.get(ticket_id, 0), 2)
        paid_on = _d(max(days - 3, 0))
        c.execute("INSERT INTO payments (ticket_id, amount, method, date) VALUES (?, ?, ?, ?)",
                  (ticket_id, amount, methods[n % 3], paid_on))
        c.execute("INSERT INTO warranties (ticket_id, start_date, end_date, notes) VALUES (?, ?, ?, ?)",
                  (ticket_id, paid_on, _d(max(days - 3, 0) - 90), "Garantía de 90 días en mano de obra y refacciones."))
    # Anticipo parcial de un ticket en reparación
    c.execute("INSERT INTO payments (ticket_id, amount, method, date) VALUES (?, ?, ?, ?)",
              ("REP-001024", 1000.00, "Efectivo", _d(4)))

    flow = ["Equipo recibido en mostrador", "Diagnóstico iniciado", "Diagnóstico completado y cotización enviada",
            "Cliente autorizó la reparación", "Reparación terminada, pruebas de estrés OK", "Equipo entregado y pagado"]
    stage = {"RECIBIDO": 1, "EN DIAGNÓSTICO": 2, "ESPERANDO PIEZAS": 4, "EN REPARACIÓN": 4,
             "LISTO PARA ENTREGA": 5, "ENTREGADO Y PAGADO": 6}
    activity_rows = []
    for ticket_id, status, _, _, _, days, _, branch_id in tickets:
        for k in range(stage[status]):
            action = flow[k] if not (status == "ESPERANDO PIEZAS" and k == 3) else "En espera de refacción del proveedor"
            activity_rows.append((ticket_id, action, _dt(max(days - k, 0), 9 + k * 2, 15), branch_id))
    # Orden cronológico: el dashboard muestra los últimos movimientos por id.
    c.executemany("INSERT INTO activities (ticket_id, action, time, branch_id) VALUES (?, ?, ?, ?)",
                  sorted(activity_rows, key=lambda r: r[2]))

    # Ventas de mostrador (POS): (dias_atras, hora, sucursal, usuario, [(articulo, cantidad)])
    sales = [
        (0, 11, "NORTE", "admin", [("CAB-USB-C", 2), ("MOU-OPT-USB", 1)]),
        (1, 13, "NORTE", "tecnico_norte", [("USB-64G", 3)]),
        (2, 17, "NORTE", "admin", [("KBD-MEC-RGB", 1), ("MOU-OPT-USB", 1)]),
        (4, 10, "NORTE", "tecnico_norte", [("RAM-8G-D4", 2)]),
        (6, 12, "NORTE", "admin", [("FAN-120MM", 3), ("PST-MX4", 1)]),
        (9, 16, "NORTE", "admin", [("SSD-500G-NVME", 1), ("ALC-ISO-99", 1)]),
        (13, 18, "NORTE", "tecnico_norte", [("KIT-DESARM-24", 1)]),
        (0, 12, "CENTRO", "tecnico_centro", [("CAB-HDMI-2M", 1), ("CAB-RJ45-3M", 2)]),
        (1, 15, "CENTRO", "tecnico_centro", [("WIFI-USB", 1)]),
        (3, 11, "CENTRO", "tecnico_centro", [("SSD-1TB-SATA", 1)]),
        (5, 14, "CENTRO", "tecnico_centro", [("CAM-1080P", 1)]),
        (8, 17, "CENTRO", "tecnico_centro", [("RTR-AX1800", 1), ("CAB-RJ45-3M", 3)]),
        (11, 13, "CENTRO", "tecnico_centro", [("RAM-8G-SO4", 2)]),
        (16, 10, "CENTRO", "tecnico_centro", [("AIR-COMP-400", 2), ("PAD-TERM-1MM", 1)]),
    ]
    for days, hour, branch_id, username, lines in sales:
        lines = [(i, q) for i, q in lines if q > 0 and inv[i][7] == branch_id]
        total = sum(_precio_matricial(inv[i][6]) * q for i, q in lines)
        c.execute("INSERT INTO sales (total, date, branch_id, username, status) VALUES (?, ?, ?, ?, 'COMPLETADA')",
                  (round(total, 2), _dt(days, hour, 30), branch_id, username))
        sale_id = c.lastrowid
        for item_id, qty in lines:
            price = _precio_matricial(inv[item_id][6])
            c.execute("INSERT INTO sale_items (sale_id, item_id, qty, price, subtotal) VALUES (?, ?, ?, ?, ?)",
                      (sale_id, item_id, qty, price, round(price * qty, 2)))

    c.executemany("INSERT INTO purchase_orders (vendor_id, part_id, qty, status, date) VALUES (?, ?, ?, ?, ?)", [
        ("VEND-01", "GPU-RTX-4060", 3, "COMPLETADA", _d(25)),
        ("VEND-02", "PST-MX4", 10, "PENDIENTE", _d(2)),
        ("VEND-04", "BAT-LAP-HP", 5, "PENDIENTE", _d(1)),
        ("VEND-03", "RTR-AX1800", 6, "COMPLETADA", _d(14)),
        ("VEND-01", "SSD-500G-NVME", 8, "COMPLETADA", _d(10))])

    kb_data = [
        ("Pantalla Azul de la Muerte (BSOD)", "pantalla azul, bsod, reinicia, memory_management",
         "1. Anotar el código de detención (stop code). 2. Revisar el Visor de eventos. 3. Correr MemTest86 al menos 2 pasadas. "
         "4. Si falla la RAM, probar módulo por módulo. 5. Actualizar controladores de chipset y almacenamiento.", "Software"),
        ("Sobrecalentamiento y apagado repentino", "apaga, calienta, ventilador, temperatura, thermal throttling",
         "1. Medir temperaturas con HWMonitor en reposo y en carga. 2. Limpiar polvo con aire comprimido. "
         "3. Reemplazar pasta térmica (MX-4 / Kryonaut). 4. Revisar thermal pads de VRM y VRAM en GPUs.", "Hardware"),
        ("No enciende (sin energía)", "no enciende, muerta, quemado, sin luz",
         "1. Probar con otro cargador o fuente conocida. 2. Drenar energía residual (botón de encendido 30 s sin batería). "
         "3. Medir el voltaje del jack DC. 4. Revisar fusibles y MOSFETs de la etapa de carga.", "Hardware"),
        ("Laptop lenta: migración a SSD", "lenta, disco duro, ssd, clonar, arranque",
         "1. Verificar salud del disco con CrystalDiskInfo. 2. Clonar con Macrium Reflect o Clonezilla. "
         "3. Activar AHCI y TRIM. 4. Si tiene 4 GB de RAM, sugerir ampliar a 8 GB.", "Hardware"),
        ("Batería inflada en laptop", "bateria, inflada, hinchada, touchpad levantado",
         "1. NO perforar ni presionar la batería. 2. Desconectar y retirar con herramienta plástica. "
         "3. Almacenar en contenedor ignífugo y enviar a reciclaje. 4. Instalar batería compatible y calibrar.", "Seguridad"),
        ("Sin video con ventiladores girando", "no da video, pantalla negra, beep, post",
         "1. Escuchar códigos beep o revisar LEDs de diagnóstico (DRAM/VGA/CPU/BOOT). 2. Reasentar RAM y GPU. "
         "3. Limpiar contactos con alcohol isopropílico. 4. Probar con video integrado o con otra GPU.", "Hardware"),
        ("WiFi no conecta después de actualizar Windows", "wifi, red, internet, actualización, controlador",
         "1. Reinstalar el controlador de la tarjeta de red desde el sitio del fabricante. 2. netsh winsock reset. "
         "3. Revisar el modo avión y el administrador de energía. 4. Como alternativa, adaptador USB AC600.", "Redes"),
        ("Pines doblados en socket de CPU", "pines, socket, doblados, am4, lga",
         "1. Revisar con lupa o microscopio. 2. Enderezar con aguja fina o tarjeta plástica, pin por pin. "
         "3. En LGA, evaluar el reemplazo del socket o de la tarjeta madre si hay pines rotos.", "Hardware"),
    ]
    c.executemany("INSERT INTO knowledge_base (title, keywords, content, category) VALUES (?, ?, ?, ?)", kb_data)

    conn.commit()


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        print(f"[OK] {DB_PATH} ya existe, no se modifica. Bórralo primero si quieres regenerarlo.")
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(SCHEMA)
        seed(conn)
        conn.close()
        print(f"[OK] {DB_PATH} generado con el esquema y los datos de semilla originales.")
