#!/usr/bin/env python3
"""
BiechyFinder Desktop App v6.0
Application Windows native moderne (Svelte + GSAP + FastAPI + pywebview Edge WebView2)
- Auto-installation des dépendances système manquantes (WebView2 Evergreen)
- Auto-téléchargement de la base de données au premier lancement si absente
- Auto-création du raccourci bureau
"""

import os
import sys
import io
import time
import socket
import json
import threading
import subprocess
import urllib.request
import urllib.error

# Correction PyInstaller Windows GUI (console=False) : sys.stdout et sys.stderr sont None
class SafeStream(io.StringIO):
    def write(self, s):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False

if sys.stdout is None or not hasattr(sys.stdout, 'isatty'):
    sys.stdout = SafeStream()
if sys.stderr is None or not hasattr(sys.stderr, 'isatty'):
    sys.stderr = SafeStream()

APP_VERSION = "6.0"
GITHUB_REPO = "fenekee/BiechyFinder"
DEFAULT_APP_DIR = os.path.join(os.path.expanduser("~"), "Documents", "BiechyFinder")
DEFAULT_DB = os.path.join(DEFAULT_APP_DIR, "biechyfinder.db")
CONFIG_FILE = os.path.join(DEFAULT_APP_DIR, "config.json")

# 1. Vérification et installation automatique de WebView2 si manquant sous Windows
def ensure_webview2_installed():
    if sys.platform != "win32":
        return
    try:
        import winreg
        # Vérification des clés de registre officielles de WebView2 Runtime
        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-2342-4285-A108-0A0003430441}"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-2342-4285-A108-0A0003430441}"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-2342-4285-A108-0A0003430441}")
        ]
        installed = False
        for hkey, subkey in keys:
            try:
                with winreg.OpenKey(hkey, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "pv")
                    if val and val != "0.0.0.0":
                        installed = True
                        break
            except OSError:
                pass

        if not installed:
            print("Microsoft Edge WebView2 non détecté. Installation automatique en cours...")
            bootstrapper_url = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
            tmp_installer = os.path.join(os.environ.get("TEMP", "."), "MicrosoftEdgeWebview2Setup.exe")
            urllib.request.urlretrieve(bootstrapper_url, tmp_installer)
            subprocess.run([tmp_installer, "/silent", "/install"], check=True)
            print("WebView2 installé avec succès !")
    except Exception as e:
        print(f"Note WebView2: {e}")

# 2. Création automatique du raccourci sur le Bureau au premier lancement
def ensure_desktop_shortcut():
    if sys.platform != "win32":
        return
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, "BiechyFinder.lnk")
        if not os.path.exists(shortcut_path):
            target_exe = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
            work_dir = os.path.dirname(target_exe)
            vbs_script = f'''Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_exe}"
oLink.WorkingDirectory = "{work_dir}"
oLink.Description = "BiechyFinder v{APP_VERSION} - Explorateur NAS & Assistant IA"
oLink.Save'''
            vbs_path = os.path.join(os.environ.get("TEMP", "."), "create_shortcut.vbs")
            with open(vbs_path, "w", encoding="utf-8") as f:
                f.write(vbs_script)
            subprocess.run(["cscript", "//nologo", vbs_path], check=False)
            try:
                os.remove(vbs_path)
            except Exception:
                pass
    except Exception:
        pass

# 3. Vérification de la base de données au premier lancement
def ensure_database():
    os.makedirs(DEFAULT_APP_DIR, exist_ok=True)
    if os.path.exists(DEFAULT_DB) and os.path.getsize(DEFAULT_DB) > 1024 * 1024:
        return
    
    # Vérifier si une base locale existe dans le dossier de l'app ou dist
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "biechyfinder.db"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "biechyfinder.db")
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 1024 * 1024:
            try:
                import shutil
                shutil.copy2(c, DEFAULT_DB)
                return
            except Exception:
                pass

    # Sinon téléchargement automatique depuis GitHub Releases en tâche de fond
    def _download_db():
        try:
            print("Téléchargement automatique de la base pré-indexée depuis GitHub...")
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
            req = urllib.request.Request(url, headers={"User-Agent": f"BiechyFinder/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                releases = json.loads(resp.read().decode())
            download_url = None
            for r in releases:
                for a in r.get("assets", []):
                    if a.get("name") == "biechyfinder.db":
                        download_url = a.get("browser_download_url")
                        break
                if download_url:
                    break
            if not download_url:
                download_url = f"https://github.com/{GITHUB_REPO}/releases/latest/download/biechyfinder.db"

            tmp_path = DEFAULT_DB + ".tmp"
            dl_req = urllib.request.Request(download_url, headers={"User-Agent": f"BiechyFinder/{APP_VERSION}"})
            with urllib.request.urlopen(dl_req, timeout=600) as resp, open(tmp_path, "wb") as f_out:
                while True:
                    chunk = resp.read(1024 * 512)
                    if not chunk:
                        break
                    f_out.write(chunk)
            if os.path.exists(tmp_path):
                os.replace(tmp_path, DEFAULT_DB)
                print("Base de données téléchargée avec succès !")
        except Exception as e:
            print(f"Note DB download: {e}")

    threading.Thread(target=_download_db, daemon=True).start()

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def start_api_server(port: int):
    try:
        import asyncio
        import uvicorn
        from server import app as fastapi_app
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        config = uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_config=None,
            log_level="error",
            access_log=False
        )
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    except Exception as e:
        import traceback
        err_log = os.path.join(DEFAULT_APP_DIR, "server_error.log")
        try:
            with open(err_log, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass

def wait_for_api(port: int, timeout: float = 12.0):
    url = f"http://127.0.0.1:{port}/api/status"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=0.8) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.15)
    return False

def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # 1. Dépendances système & initialisation premier lancement
    ensure_webview2_installed()
    ensure_desktop_shortcut()
    ensure_database()

    # 2. Port API
    port = 8000
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 8000))
    except OSError:
        port = find_free_port()

    # 3. Lancer FastAPI en arrière-plan
    api_thread = threading.Thread(target=start_api_server, args=(port,), daemon=True)
    api_thread.start()
    ready = wait_for_api(port)
    if not ready:
        err_log = os.path.join(DEFAULT_APP_DIR, "server_error.log")
        err_msg = "Le serveur API local n'a pas pu démarrer dans les délais."
        if os.path.exists(err_log):
            try:
                with open(err_log, "r", encoding="utf-8") as f:
                    err_msg += f"\n\nDétail de l'erreur:\n{f.read()[:500]}"
            except Exception:
                pass
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, err_msg, "BiechyFinder - Erreur de démarrage", 0x10)
        return

    # 4. Ouvrir la fenêtre desktop native
    import webview
    app_url = f"http://127.0.0.1:{port}"
    window = webview.create_window(
        title=f"BiechyFinder v{APP_VERSION} - Explorateur NAS & Assistant IA",
        url=app_url,
        width=1200,
        height=780,
        min_size=(840, 560),
        background_color="#090d16",
        text_select=True,
        zoomable=True
    )

    webview.start(debug=False)

if __name__ == "__main__":
    main()
