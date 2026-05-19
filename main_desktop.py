import threading
import uvicorn
import webview
import time
from database import init_db
from main import app

def start_server():
    # Deshabilitamos el log level para no inundar la terminal al correr en hilo secundario
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == '__main__':
    # 1. Asegurar Inicialización de Base de Datos Local
    print("Inicializando Base de Datos Local SQLite...")
    init_db()

    # 2. Iniciar servidor FastAPI en hilo secundario (Daemon)
    print("Iniciando servidor lógico local en puerto 8000...")
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()
    
    # Pequeño delay para asegurar que Uvicorn está listo antes de abrir el frontend
    time.sleep(1)
    
    # 3. Crear ventana nativa con pywebview
    print("Iniciando Interfaz Gráfica de Escritorio...")
    webview.create_window(
        title="FixIT", 
        url="http://127.0.0.1:8000", 
        width=1280, 
        height=720,
        min_size=(1024, 600)
    )
    
    # Arrancar el main loop de la ventana (Bloqueante hasta que el usuario cierre la app)
    webview.start()
