import os
import sys
import socket
import webbrowser
import threading
import time
import uvicorn

from database import get_admin_credentials
from server import app, get_lan_ip
from replay_engine import MarketReplayEngine

def free_port_if_busy(port):
    """Libera automáticamente el puerto si quedó ocupado por un proceso huérfano previo."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                if sys.platform == "win32":
                    import subprocess
                    cmd = f'netstat -ano | findstr :{port}'
                    out = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
                    for line in out.strip().splitlines():
                        if "LISTENING" in line:
                            parts = line.strip().split()
                            pid = int(parts[-1])
                            if pid != os.getpid():
                                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(0.8)
    except Exception:
        pass

def open_browser(port):
    time.sleep(1.5)
    url = f"http://localhost:{port}/admin"
    print(f"\n[SISTEMA] Abriendo panel de administración en tu navegador: {url}...")
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    port = int(os.environ.get("PORT", 8000))
    free_port_if_busy(port)
    lan_ip = get_lan_ip()
    admin_user, admin_pass = get_admin_credentials()
    engine = MarketReplayEngine.get_instance()
    state = engine.get_state()

    print("=" * 74)
    print("      CRYPTO LAB — SIMULADOR FINANCIERO & AUDITORÍA FORENSE")
    print("=" * 74)
    print("\n [!] APLICACIÓN LISTA Y CONFIGURADA PARA TU PRESENTACIÓN\n")
    print(f" -> Enlace en esta computadora (Docente / Proyector):")
    print(f"    http://localhost:{port}/admin\n")
    print(f" -> Enlace para Celulares (Conectados a la misma red Wi-Fi):")
    print(f"    http://{lan_ip}:{port}\n")
    print(f" -> Credenciales Administrativas:")
    print(f"    Usuario:    {admin_user}")
    print(f"    Contraseña: [PROTEGIDA - Definida en tu archivo .env local]\n")
    print(f" -> Motor Market Replay (D-015):")
    print(f"    Dataset:    {state['dataset_name']}")
    print(f"    Período:    {state['periodo_efectivo_observado']}")
    print(f"    Velocidad:  {state['speed']}x (16.91 horas observadas en 30 minutos de sesión)")
    print("=" * 74)
    print(" [CONSEJO]: Proyecta la pantalla y abre 'Proyectar QR' para que tus")
    print("            estudiantes escaneen el código desde sus celulares.")
    print("=" * 74)
    print(" Presiona Ctrl + C en esta ventana cuando desees apagar el servidor.\n")

    # Open browser automatically in a background thread
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Run Uvicorn server on all network interfaces
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == "__main__":
    main()
