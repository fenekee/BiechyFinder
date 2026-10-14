#!/usr/bin/env python3
"""
BiechyFinder Desktop App
Lance l'application dans une fenêtre Windows native ultra moderne via pywebview (Edge WebView2),
avec le backend Python FTS5 & IA local, sans nécessiter de navigateur web.
"""

import os
import sys
import time
import socket
import threading
import urllib.request
import webview
import uvicorn
from server import app as fastapi_app

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def start_api_server(port: int):
    # Démarrage silencieux d'uvicorn dans un thread daemon
    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()

def wait_for_api(port: int, timeout: float = 6.0):
    url = f"http://127.0.0.1:{port}/api/status"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.1)
    return False

def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    port = 8000
    # Vérifier si le port 8000 est déjà occupé, sinon trouver un port libre
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 8000))
    except OSError:
        port = find_free_port()

    # Démarrer le serveur API en tâche de fond
    api_thread = threading.Thread(target=start_api_server, args=(port,), daemon=True)
    api_thread.start()

    # Attendre que l'API soit prête
    wait_for_api(port)

    # Chemin de l'icône de l'application si présente
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if not os.path.exists(icon_path):
        icon_path = None

    # Création de la fenêtre Desktop native
    app_url = f"http://127.0.0.1:{port}"
    window = webview.create_window(
        title="BiechyFinder - Explorateur NAS & Assistant IA",
        url=app_url,
        width=1200,
        height=780,
        min_size=(840, 560),
        background_color="#090d16",
        text_select=True,
        zoomable=True
    )

    # Lancement du moteur WebView2 natif Windows
    webview.start(debug=False)

if __name__ == "__main__":
    main()
