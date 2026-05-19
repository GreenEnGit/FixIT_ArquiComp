# 🛠️ FixIT - Hardware Repair Management System 

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

**FixIT** es un sistema integral de tipo SaaS y aplicación de escritorio diseñado específicamente para talleres de reparación de hardware, celulares y equipos de cómputo. Permite controlar desde la recepción del equipo hasta la entrega, manejando inventario, punto de venta (POS) y notificaciones automáticas por SMS a los clientes.

---

## ✨ Características Principales

- 📱 **Gestión de Tickets de Reparación:** Control del flujo de trabajo por estados (Recibido, En Diagnóstico, Esperando Piezas, En Reparación, Listo para Entrega, Entregado y Pagado).
- 🛒 **Punto de Venta (POS):** Ventas de mostrador integradas directamente con el inventario, control de carritos y generación de tickets.
- 📦 **Control de Inventario Avanzado:** Seguimiento de stock en tiempo real, control de costos y asignación dinámica de refacciones directamente a los tickets de reparación.
- 👥 **CRM de Clientes:** Registro detallado de clientes, dispositivos asociados y su historial histórico de reparaciones.
- 🔐 **Control de Accesos (RBAC):** Sistema de usuarios con roles diferenciados (Técnico, Administrador, etc.) y soporte multi-sucursal.
- 🔔 **Notificaciones Automáticas:** Integración lista para **Twilio** para enviar alertas por SMS a los clientes cuando su equipo está listo.
- 💻 **Modos de Ejecución Dual:** Puede ejecutarse como un servidor en la nube (`uvicorn`) o como una aplicación de escritorio nativa independiente (`pywebview`).
- 📊 **Auditoría Inmutable:** Registro riguroso de movimientos financieros y mermas de inventario.

## 🚀 Arquitectura Tecnológica

- **Backend:** Python 3.10+, FastAPI (Asíncrono, concurrente)
- **Base de Datos:** SQLite3 (Transaccional, con 20 tablas relacionales optimizadas, llaves foráneas y constraints)
- **Frontend:** Jinja2 Templates, HTML5 con diseño moderno (estilizado con clases utilitarias)
- **Empaquetado Escritorio:** PyWebView
- **Autenticación:** JWT Tokens y Passlib (Bcrypt) para hashing de contraseñas de alta seguridad.

---

## ⚙️ Instalación y Configuración (Entorno Local)

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/fixit-repair-system.git
cd fixit-repair-system
```

### 2. Crear entorno virtual e instalar dependencias
Es importante instalar todas las dependencias actualizadas desde el archivo `requirements.txt`:
```bash
python -m venv venv

# Activar entorno en Windows:
venv\Scripts\activate

# Activar entorno en Mac/Linux:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
Crea un archivo `.env` en la raíz del proyecto para alojar tus secretos, basándote en el archivo de ejemplo proporcionado:
```bash
cp .env.example .env
```
Edita el archivo `.env` para añadir tu clave secreta JWT, credenciales de base de datos (si migras de SQLite) y credenciales de API externas (Twilio/OpenAI).

### 4. Inicializar y Verificar la Base de Datos
El proyecto genera automáticamente la base de datos `taller_prototipo.db` si no existe. 
Para validar que la integridad de tu entorno y el esquema SQL sean correctos antes de arrancar, puedes usar:
```bash
python verify_project.py
```
> Si todo está correcto, el script devolverá `VERIFICACIÓN COMPLETADA: EL SISTEMA ESTÁ ESTABLE Y LIBRE DE ERRORES CRÍTICOS.`

---

## ▶️ Uso y Ejecución

Puedes levantar este proyecto de dos formas dependiendo de tu caso de uso:

### Opción A: Modo Servidor Web (Modo SaaS en la Nube)
Útil si quieres desplegarlo en un servidor o acceder desde navegadores en la misma red local.
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
> Accede a `http://localhost:8000` en tu navegador.

### Opción B: Modo Aplicación de Escritorio
Útil si el sistema será operado exclusivamente de forma local por un técnico sin requerir un navegador web de terceros.
```bash
python main_desktop.py
```
> Esto abrirá una ventana de interfaz gráfica nativa bloqueando el acceso a pestañas externas y optimizando el rendimiento.

---

## 🛠️ Scripts de Utilidad Incluidos

- `verify_project.py`: Ejecuta pruebas de diagnóstico. Revisa que todas las rutas Python no tengan errores de sintaxis y que las 20 tablas de la DB existan y estén conectadas.
- `check_bindings.py`: Valida que los nombres (`name=""`) en los formularios HTML de plantillas coincidan exactamente con las variables declaradas en los endpoints de FastAPI, previniendo errores HTTP 422 Unprocessable Entity.

---

## 🤝 Contribución
1. Haz un *Fork* del repositorio.
2. Crea una rama para tu feature (`git checkout -b feature/NuevaCaracteristica`).
3. Haz *Commit* a tus cambios (`git commit -m 'Añadir nueva característica'`).
4. Haz *Push* a la rama (`git push origin feature/NuevaCaracteristica`).
5. Abre un Pull Request.

---

**FixIT** - Construido para revolucionar la gestión técnica de reparaciones. 🚀
