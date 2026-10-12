#!/usr/bin/env python3
"""
Script de publication automatique de release pour BiechyFinder.
Usage:
    python publish_release.py [--build] [--no-db] [--notes "Notes de version"]

Fonctionnalités :
- Lit la version depuis BiechyFinder.py (ex: v5.4)
- (Optionnel) Compile le nouvel .exe avec PyInstaller via --build
- Récupère automatiquement la base de données 'biechyfinder.db' (locale ou depuis la dernière release)
- Crée la release GitHub correspondante
- Téléverse à la fois BiechyFinder.exe ET biechyfinder.db
"""

import os
import sys
import re
import json
import argparse
import subprocess
import urllib.request
import urllib.error

REPO = "fenekee/BiechyFinder"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_current_version():
    py_path = os.path.join(SCRIPT_DIR, "BiechyFinder.py")
    if not os.path.exists(py_path):
        raise FileNotFoundError(f"Impossible de trouver {py_path}")
    with open(py_path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not m:
        raise ValueError("Impossible d'extraire APP_VERSION de BiechyFinder.py")
    return m.group(1).strip()

def get_github_token():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        p = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            cwd=SCRIPT_DIR
        )
        for line in p.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None

def find_local_db():
    candidates = [
        os.path.join(os.path.expanduser("~"), "Documents", "BiechyFinder", "biechyfinder.db"),
        os.path.join(SCRIPT_DIR, "biechyfinder.db"),
        os.path.join(os.path.expanduser("~"), "Downloads", "biechyfinder.db")
    ]
    # Check config.json if exists
    cfg_path = os.path.join(os.path.expanduser("~"), "Documents", "BiechyFinder", "config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if cfg.get("db_path"):
                    candidates.insert(0, cfg["db_path"])
        except Exception:
            pass

    for path in candidates:
        if os.path.exists(path) and os.path.getsize(path) > 1024 * 1024:
            return path
    return None

def download_latest_db_from_github(headers, target_path):
    print("Recherche de la dernière base 'biechyfinder.db' sur les releases GitHub...")
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases", headers=headers)
    with urllib.request.urlopen(req) as resp:
        releases = json.loads(resp.read().decode())
    
    download_url = None
    for r in releases:
        for a in r.get("assets", []):
            if a.get("name") == "biechyfinder.db":
                download_url = a.get("browser_download_url")
                print(f"Trouvé dans la release {r.get('tag_name')} : {download_url}")
                break
        if download_url:
            break
            
    if not download_url:
        raise RuntimeError("Aucune base 'biechyfinder.db' trouvée dans les releases précédentes de GitHub.")

    print(f"Téléchargement de {download_url} vers {target_path}...")
    req = urllib.request.Request(download_url, headers={"User-Agent": "BiechyFinder-Release"})
    with urllib.request.urlopen(req) as resp, open(target_path, "wb") as out_file:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        last_pct = -1
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out_file.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                pct = int((downloaded / total) * 100)
                if pct != last_pct and pct % 20 == 0:
                    print(f"  Téléchargement DB : {pct}% ({downloaded // (1024*1024)} Mo / {total // (1024*1024)} Mo)")
                    last_pct = pct
    print("Téléchargement de la base terminé.")
    return target_path

class ProgressFileReader:
    def __init__(self, filepath, label="Upload"):
        self.f = open(filepath, "rb")
        self.total = os.path.getsize(filepath)
        self.read_so_far = 0
        self.last_pct = -1
        self.label = label

    def read(self, size=-1):
        chunk = self.f.read(size)
        self.read_so_far += len(chunk)
        if self.total > 0:
            pct = int((self.read_so_far / self.total) * 100)
            if pct != self.last_pct and pct % 10 == 0:
                print(f"  [{self.label}] {pct}% ({self.read_so_far / (1024*1024):.1f}/{self.total / (1024*1024):.1f} Mo)")
                self.last_pct = pct
        return chunk

    def len(self):
        return self.total

    def __len__(self):
        return self.total

import time

def upload_asset(upload_url, headers, file_path, asset_name, max_retries=3):
    file_size = os.path.getsize(file_path)
    for attempt in range(1, max_retries + 1):
        print(f"\nTéléversement de {asset_name} ({file_size / (1024*1024):.1f} Mo) [Essai {attempt}/{max_retries}]...")
        reader = ProgressFileReader(file_path, label=asset_name)
        target_url = f"{upload_url}?name={asset_name}"
        req = urllib.request.Request(
            target_url,
            data=reader,
            headers={
                **headers,
                "Content-Type": "application/octet-stream",
                "Content-Length": str(file_size)
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=900) as resp:
                data = json.loads(resp.read().decode())
                print(f"Succès : {asset_name} téléversé.")
                return data.get("browser_download_url")
        except Exception as e:
            print(f"Échec de l'essai {attempt}: {e}")
            if attempt < max_retries:
                try:
                    m = re.search(r'/releases/(\d+)/', upload_url)
                    if m:
                        rel_id = m.group(1)
                        chk_req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/{rel_id}", headers=headers)
                        with urllib.request.urlopen(chk_req) as cr:
                            rel_info = json.loads(cr.read().decode())
                            for a in rel_info.get("assets", []):
                                if a.get("name") == asset_name:
                                    del_req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/assets/{a['id']}", headers=headers, method="DELETE")
                                    urllib.request.urlopen(del_req)
                                    print("Nettoyage de l'asset partiel avant nouvel essai.")
                except Exception:
                    pass
                time.sleep(5)
            else:
                raise
        finally:
            reader.f.close()

def main():
    parser = argparse.ArgumentParser(description="Publier automatiquement une release BiechyFinder.")
    parser.add_argument("--build", action="store_true", help="Recompiler dist/BiechyFinder.exe avec PyInstaller avant publication")
    parser.add_argument("--no-db", action="store_true", help="Ne pas inclure biechyfinder.db dans les assets")
    parser.add_argument("--notes", type=str, default="", help="Notes de version pour la release")
    args = parser.parse_args()

    version = get_current_version()
    tag = f"v{version}"
    print(f"=== Publication de la release {tag} pour {REPO} ===")

    token = get_github_token()
    if not token:
        print("Erreur: Impossible de récupérer le token GitHub via git credential fill ou GITHUB_TOKEN.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "BiechyFinder-Release-Automation"
    }

    exe_path = os.path.join(SCRIPT_DIR, "dist", "BiechyFinder.exe")
    if args.build or not os.path.exists(exe_path):
        print("\nCompilation avec PyInstaller...")
        res = subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "BiechyFinder.spec"], cwd=SCRIPT_DIR)
        if res.returncode != 0:
            print("Erreur lors de la compilation.")
            sys.exit(1)

    if not os.path.exists(exe_path):
        print(f"Erreur: {exe_path} introuvable.")
        sys.exit(1)

    # Récupération / vérification de la base de données
    db_path = None
    if not args.no_db:
        db_path = find_local_db()
        if db_path:
            print(f"Base de données trouvée localement : {db_path} ({os.path.getsize(db_path) / (1024*1024):.1f} Mo)")
        else:
            cached_db = os.path.join(SCRIPT_DIR, "dist", "biechyfinder.db")
            if os.path.exists(cached_db) and os.path.getsize(cached_db) > 1024*1024:
                db_path = cached_db
            else:
                db_path = download_latest_db_from_github(headers, cached_db)

    # Vérification ou création de la release sur GitHub
    print(f"\nVérification de la release {tag} sur GitHub...")
    check_url = f"https://api.github.com/repos/{REPO}/releases/tags/{tag}"
    rel = None
    try:
        req = urllib.request.Request(check_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            rel = json.loads(resp.read().decode())
            print(f"Release {tag} existe déjà (ID {rel.get('id')}).")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Création de la nouvelle release {tag}...")
        else:
            print(f"Erreur HTTP: {e.code} - {e.read().decode()}")
            sys.exit(1)

    if not rel:
        create_url = f"https://api.github.com/repos/{REPO}/releases"
        body_text = args.notes or f"Mise à jour BiechyFinder {tag}"
        payload = json.dumps({
            "tag_name": tag,
            "target_commitish": "main",
            "name": f"BiechyFinder {tag}",
            "body": body_text,
            "draft": False,
            "prerelease": False
        }).encode("utf-8")
        req = urllib.request.Request(create_url, data=payload, headers={**headers, "Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            rel = json.loads(resp.read().decode())
            print(f"Release {tag} créée avec succès (ID {rel.get('id')}).")

    upload_url = rel["upload_url"].split("{")[0]
    existing_assets = {a["name"]: a["id"] for a in rel.get("assets", [])}

    # Upload BiechyFinder.exe
    if "BiechyFinder.exe" in existing_assets:
        aid = existing_assets["BiechyFinder.exe"]
        print(f"Suppression de l'ancien exécutable BiechyFinder.exe (ID {aid})...")
        del_req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/assets/{aid}", headers=headers, method="DELETE")
        urllib.request.urlopen(del_req)

    upload_asset(upload_url, headers, exe_path, "BiechyFinder.exe")

    # Upload biechyfinder.db
    if db_path:
        if "biechyfinder.db" in existing_assets:
            aid = existing_assets["biechyfinder.db"]
            print(f"La base biechyfinder.db existe déjà dans cette release (ID {aid}). Remplacement...")
            del_req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/assets/{aid}", headers=headers, method="DELETE")
            urllib.request.urlopen(del_req)
        upload_asset(upload_url, headers, db_path, "biechyfinder.db")

    print(f"\n==========================================")
    print(f" Release {tag} publiée avec succès !")
    print(f" URL: https://github.com/{REPO}/releases/tag/{tag}")
    print(f"==========================================")

if __name__ == "__main__":
    main()
