#!/usr/bin/env python3
"""
BiechyFinder API Server - FastAPI Backend pour l'interface Web Svelte
Expose les fonctionnalités de recherche FTS5, de scan NAS et de RAG IA (Mistral)
sans modifier le code existant de BiechyFinder.
"""

import os
import sys
import json
import time
import re
import sqlite3
import threading
import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import httpx

app = FastAPI(title="BiechyFinder API", version="5.6")

# Enable CORS for local dev servers (Vite: 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration & Paths
DEFAULT_APP_DIR = os.path.join(os.path.expanduser("~"), "Documents", "BiechyFinder")
DEFAULT_DB = os.path.join(DEFAULT_APP_DIR, "biechyfinder.db")
CONFIG_FILE = os.path.join(DEFAULT_APP_DIR, "config.json")

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "db_path": DEFAULT_DB,
        "scan_paths": [],
        "mistral_api_key": "",
        "mistral_model": "mistral-small-latest",
        "nas_drive_letter": "",
        "ssh_config": {"enabled": False, "host": "", "user": "", "pwd": "", "port": 22}
    }

def save_config(cfg: Dict[str, Any]):
    os.makedirs(DEFAULT_APP_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

def get_db_path() -> str:
    cfg = load_config()
    db_path = cfg.get("db_path", DEFAULT_DB)
    if os.path.exists(db_path):
        return db_path
    # Fallback to local workspace db if exists
    local_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "biechyfinder.db")
    if os.path.exists(local_db):
        return local_db
    local_dist_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "biechyfinder.db")
    if os.path.exists(local_dist_db):
        return local_dist_db
    return db_path

# State tracking for UI ("idle" | "scanning" | "ai_thinking")
state_lock = threading.Lock()
current_app_state = "idle"
scan_progress = {
    "is_scanning": False,
    "current_path": "",
    "total_indexed": 0,
    "message": "En attente",
    "last_error": None
}

def set_app_state(new_state: str):
    global current_app_state
    with state_lock:
        current_app_state = new_state

def get_app_state() -> str:
    with state_lock:
        return current_app_state

def prepare_fts_query(query: str) -> str:
    clean = re.sub(r'["\'\*\+\(\)\:\^\{\}\[\]~]', ' ', query).strip()
    words = [re.sub(r'[^a-zA-Z0-9\u00C0-\u017F]', '', w) for w in clean.split()]
    tokens = [f"{w}*" for w in words if w]
    return " ".join(tokens)

CATEGORY_FILTERS = {
    "folders": "f.is_dir = 1",
    "files": "f.is_dir = 0",
    "docs": "f.is_dir = 0 AND (f.name LIKE '%.pdf' OR f.name LIKE '%.docx' OR f.name LIKE '%.doc' OR f.name LIKE '%.xlsx' OR f.name LIKE '%.xls' OR f.name LIKE '%.pptx' OR f.name LIKE '%.txt' OR f.name LIKE '%.csv' OR f.name LIKE '%.odt' OR f.name LIKE '%.rtf')",
    "videos": "f.is_dir = 0 AND (f.name LIKE '%.mp4' OR f.name LIKE '%.mkv' OR f.name LIKE '%.avi' OR f.name LIKE '%.mov' OR f.name LIKE '%.wmv' OR f.name LIKE '%.flv' OR f.name LIKE '%.webm' OR f.name LIKE '%.m4v')",
    "images": "f.is_dir = 0 AND (f.name LIKE '%.jpg' OR f.name LIKE '%.jpeg' OR f.name LIKE '%.png' OR f.name LIKE '%.gif' OR f.name LIKE '%.svg' OR f.name LIKE '%.webp' OR f.name LIKE '%.bmp' OR f.name LIKE '%.tiff' OR f.name LIKE '%.ico')",
    "code": "f.is_dir = 0 AND (f.name LIKE '%.py' OR f.name LIKE '%.js' OR f.name LIKE '%.ts' OR f.name LIKE '%.html' OR f.name LIKE '%.css' OR f.name LIKE '%.json' OR f.name LIKE '%.cpp' OR f.name LIKE '%.c' OR f.name LIKE '%.h' OR f.name LIKE '%.sh' OR f.name LIKE '%.bat' OR f.name LIKE '%.sql' OR f.name LIKE '%.yaml' OR f.name LIKE '%.yml' OR f.name LIKE '%.svelte' OR f.name LIKE '%.md')",
    "archives": "f.is_dir = 0 AND (f.name LIKE '%.zip' OR f.name LIKE '%.rar' OR f.name LIKE '%.7z' OR f.name LIKE '%.tar' OR f.name LIKE '%.gz' OR f.name LIKE '%.iso' OR f.name LIKE '%.bz2')"
}

# --- ENDPOINTS ---

@app.get("/api/status")
def get_status():
    db_path = get_db_path()
    db_exists = os.path.exists(db_path)
    total_items = 0
    total_dirs = 0
    total_files = 0
    db_size_mb = 0.0

    if db_exists:
        try:
            db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 1)
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT count(*) FROM files")
            total_items = c.fetchone()[0]
            c.execute("SELECT count(*) FROM files WHERE is_dir = 1")
            total_dirs = c.fetchone()[0]
            total_files = total_items - total_dirs
            conn.close()
        except Exception:
            pass

    cfg = load_config()
    return {
        "status": "connected" if db_exists else "no_db",
        "app_state": get_app_state(),
        "db_path": db_path,
        "db_size_mb": db_size_mb,
        "total_items": total_items,
        "total_dirs": total_dirs,
        "total_files": total_files,
        "scan_paths": cfg.get("scan_paths", []),
        "has_mistral_key": bool(cfg.get("mistral_api_key")),
        "scan_progress": scan_progress
    }

@app.get("/api/search")
def search_files(
    q: str = Query("", description="Terme de recherche"),
    category: str = Query("all", description="Filtre par type"),
    limit: int = Query(100, ge=1, le=500)
):
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return {"results": [], "total": 0, "elapsed_ms": 0.0, "error": "Base introuvable"}

    t0 = time.perf_counter()
    results = []

    cat_clause = CATEGORY_FILTERS.get(category.lower(), "")
    where_extra = f"AND {cat_clause}" if cat_clause else ""

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        if not q.strip():
            # Aperçu des éléments récents si pas de requête
            filter_sql = f"WHERE {cat_clause}" if cat_clause else ""
            sql = f"SELECT id, name, path, is_dir, mod_time FROM files {filter_sql} ORDER BY id DESC LIMIT ?"
            c.execute(sql, (limit,))
            rows = c.fetchall()
        else:
            # 1. Recherche FTS5
            fts_q = prepare_fts_query(q)
            rows = []
            if fts_q:
                try:
                    fts_sql = f"""
                        SELECT f.id, f.name, f.path, f.is_dir, f.mod_time
                        FROM files f
                        JOIN files_fts ON f.id = files_fts.rowid
                        WHERE files_fts MATCH ? {where_extra}
                        ORDER BY bm25(files_fts, 10.0, 1.0), f.is_dir DESC, f.mod_time DESC
                        LIMIT ?
                    """
                    c.execute(fts_sql, (fts_q, limit))
                    rows = c.fetchall()
                except Exception:
                    rows = []

            # 2. Fallback SQL si FTS5 ne trouve rien
            if not rows:
                words = [w for w in re.split(r'[\s_\-\.]+', q) if w]
                if words:
                    conditions = ["(name LIKE ? OR path LIKE ?)" for _ in words]
                    params = []
                    for w in words:
                        params.extend([f"%{w}%", f"%{w}%"])
                    where_q = " AND ".join(conditions)
                    fallback_cat = f"AND {cat_clause}" if cat_clause else ""
                    sql = f"""
                        SELECT id, name, path, is_dir, mod_time
                        FROM files
                        WHERE ({where_q}) {fallback_cat}
                        ORDER BY is_dir DESC, name ASC
                        LIMIT ?
                    """
                    params.append(limit)
                    c.execute(sql, params)
                    rows = c.fetchall()

        conn.close()

        # Formatage des données
        for r in rows:
            f_id, f_name, f_path, f_is_dir, f_mtime = r
            ext = ""
            if not f_is_dir and "." in f_name:
                ext = f_name.rsplit(".", 1)[-1].lower()
            results.append({
                "id": f_id,
                "name": f_name,
                "path": f_path,
                "is_dir": bool(f_is_dir),
                "mod_time": f_mtime,
                "ext": ext
            })

    except Exception as e:
        return {"results": [], "total": 0, "elapsed_ms": 0.0, "error": str(e)}

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "results": results,
        "total": len(results),
        "elapsed_ms": elapsed_ms
    }

class OpenRequest(BaseModel):
    path: str
    reveal: bool = False

@app.post("/api/open")
def open_item(req: OpenRequest):
    target = req.path
    cfg = load_config()
    drive_letter = cfg.get("nas_drive_letter", "").strip()

    # Remap drive letter if defined
    if drive_letter and target.startswith("//"):
        parts = target.strip("/").split("/", 1)
        if len(parts) > 1:
            dl = drive_letter.rstrip(":\\")
            target = f"{dl}:\\{parts[1].replace('/', chr(92))}"

    if not os.path.exists(target):
        # Essayer le dossier parent
        parent = os.path.dirname(target)
        if os.path.exists(parent):
            target = parent
        else:
            raise HTTPException(status_code=404, detail="Chemin introuvable sur le réseau local")

    try:
        if sys.platform == "win32":
            if req.reveal or os.path.isfile(target):
                subprocess.Popen(["explorer.exe", f"/select,{os.path.normpath(target)}"])
            else:
                os.startfile(os.path.normpath(target))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R" if req.reveal else "", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return {"status": "ok", "opened": target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SCANNING BACKGROUND ENGINE ---

def _fast_scan_dir(base_path: str):
    try:
        with os.scandir(base_path) as it:
            for entry in it:
                try:
                    stat = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=False)
                    yield (entry.name, entry.path, 1 if is_dir else 0, stat.st_mtime, stat.st_ctime)
                    if is_dir:
                        yield from _fast_scan_dir(entry.path)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass

def _scan_worker():
    global scan_progress
    set_app_state("scanning")
    scan_progress["is_scanning"] = True
    scan_progress["total_indexed"] = 0
    scan_progress["message"] = "Démarrage du scan..."
    scan_progress["last_error"] = None

    cfg = load_config()
    db_path = get_db_path()
    scan_paths = cfg.get("scan_paths", [])

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=-64000")

        c.execute("""CREATE TABLE IF NOT EXISTS files 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     name TEXT, path TEXT, is_dir INTEGER, 
                     mod_time REAL, creation_time REAL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_name ON files(name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_path ON files(path)")

        for sp in scan_paths:
            c.execute("DELETE FROM files WHERE path LIKE ?", (f"{sp}%",))
        conn.commit()

        total = 0
        for base_path in scan_paths:
            scan_progress["current_path"] = base_path
            scan_progress["message"] = f"Scan en cours: {base_path}"
            batch = []
            for item in _fast_scan_dir(base_path):
                if not scan_progress["is_scanning"]:
                    break
                batch.append(item)
                if len(batch) >= 5000:
                    c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                    total += len(batch)
                    scan_progress["total_indexed"] = total
                    batch = []

            if batch:
                c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                total += len(batch)
                scan_progress["total_indexed"] = total

        # FTS5 Rebuild
        scan_progress["message"] = "Indexation plein texte FTS5..."
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                name,
                path,
                content='files',
                content_rowid='id',
                tokenize="unicode61 remove_diacritics 2 separators '_-./\\\\'"
            )
        """)
        c.execute("INSERT INTO files_fts(files_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()

        scan_progress["message"] = f"Indexation terminée ({total:,} éléments)"
    except Exception as e:
        scan_progress["last_error"] = str(e)
        scan_progress["message"] = f"Erreur: {str(e)}"
    finally:
        scan_progress["is_scanning"] = False
        set_app_state("idle")

@app.post("/api/scan/start")
def start_scan():
    if scan_progress["is_scanning"]:
        return {"status": "already_running"}
    cfg = load_config()
    if not cfg.get("scan_paths"):
        raise HTTPException(status_code=400, detail="Aucun dossier configuré pour le scan.")
    threading.Thread(target=_scan_worker, daemon=True).start()
    return {"status": "started"}

@app.post("/api/scan/stop")
def stop_scan():
    scan_progress["is_scanning"] = False
    return {"status": "stopping"}

# --- RAG & AI CHAT STREAMING ---

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []

def get_nas_summary_text() -> str:
    summary_path = os.path.join(DEFAULT_APP_DIR, "nas_summary.txt")
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

def build_system_prompt() -> str:
    prompt = """Tu es un assistant IA spécialisé dans la recherche de fichiers sur un NAS réseau.
Tu aides l'utilisateur à retrouver rapidement ses documents, projets, dossiers et fichiers multimédia.

Voici le schéma de la table `files` :
- id : INTEGER PRIMARY KEY
- name : TEXT (nom du fichier ou dossier)
- path : TEXT (chemin complet réseau)
- is_dir : INTEGER (1 = dossier, 0 = fichier)
- mod_time : REAL (timestamp de modification Unix)
- creation_time : REAL (timestamp de création Unix)

RÈGLES IMPORTANTES :
1. Réponds TOUJOURS avec un bloc ```json ... ``` au début ou dans ta réponse contenant :
   {
     "sql": "SELECT name, path, is_dir, mod_time FROM files WHERE ... LIMIT 20",
     "explanation": "Explication claire et naturelle en français de ce que tu as cherché ou trouvé."
   }
2. Utilise LIKE pour la recherche de mots-clés (ex: name LIKE '%facture%' ou path LIKE '%Projets%').
3. Si la question n'a pas besoin de SQL, mets "sql": "" et donne une réponse utile dans "explanation".
4. Ne fais QUE des SELECT.
"""
    summary = get_nas_summary_text()
    if summary:
        prompt += f"\n\n== RÉSUMÉ DU STOCKAGE NAS ==\n{summary}\n"
    return prompt

@app.post("/api/ai/chat")
async def chat_with_ai(req: ChatRequest):
    cfg = load_config()
    api_key = cfg.get("mistral_api_key", "").strip()
    model = cfg.get("mistral_model", "mistral-small-latest")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Clé API Mistral non configurée. Ajoute ta clé dans les paramètres."
        )

    set_app_state("ai_thinking")

    # Messages array
    messages = [{"role": "system", "content": build_system_prompt()}]
    for h in req.history[-8:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    async def stream_generator():
        collected_text = ""
        db_path = get_db_path()
        sources_found = []

        try:
            # 1. Appel en streaming à l'API Mistral
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": True
                    }
                ) as resp:
                    if resp.status_code != 200:
                        err_content = await resp.aread()
                        yield f"data: {json.dumps({'type': 'error', 'message': f'Erreur API Mistral ({resp.status_code}): {err_content.decode()}'})}\n\n"
                        set_app_state("idle")
                        return

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                collected_text += delta
                                yield f"data: {json.dumps({'type': 'chunk', 'text': delta})}\n\n"
                        except Exception:
                            continue

            # 2. Extraire la requête SQL si présente pour fournir les sources du NAS
            json_match = re.search(r'```json\s*\n?(.*?)\n?```', collected_text, re.DOTALL)
            sql_query = ""
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1).strip())
                    sql_query = parsed.get("sql", "").strip()
                except Exception:
                    pass

            if sql_query and sql_query.upper().startswith("SELECT") and os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    c = conn.cursor()
                    c.execute(sql_query)
                    rows = c.fetchall()
                    conn.close()
                    for r in rows[:30]:
                        # Handle varied column select formats
                        name = r[0] if len(r) > 0 else ""
                        path = r[1] if len(r) > 1 else ""
                        is_dir = bool(r[2]) if len(r) > 2 else False
                        mod_time = r[3] if len(r) > 3 else 0.0
                        ext = ""
                        if not is_dir and "." in name:
                            ext = name.rsplit(".", 1)[-1].lower()
                        sources_found.append({
                            "name": name,
                            "path": path,
                            "is_dir": is_dir,
                            "mod_time": mod_time,
                            "ext": ext
                        })
                except Exception as sql_err:
                    print(f"Erreur SQL IA: {sql_err}")

            if sources_found:
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources_found})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            set_app_state("idle")

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

# --- CONFIG ENDPOINTS ---

@app.get("/api/config")
def get_configuration():
    cfg = load_config()
    # Mask API key for security
    api_key = cfg.get("mistral_api_key", "")
    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else ("Configurée" if api_key else "")
    return {
        "db_path": cfg.get("db_path", DEFAULT_DB),
        "scan_paths": cfg.get("scan_paths", []),
        "mistral_model": cfg.get("mistral_model", "mistral-small-latest"),
        "has_mistral_key": bool(api_key),
        "masked_api_key": masked_key,
        "nas_drive_letter": cfg.get("nas_drive_letter", "")
    }

class ConfigUpdate(BaseModel):
    mistral_api_key: Optional[str] = None
    mistral_model: Optional[str] = None
    scan_paths: Optional[List[str]] = None
    nas_drive_letter: Optional[str] = None

@app.post("/api/config")
def update_configuration(update: ConfigUpdate):
    cfg = load_config()
    if update.mistral_api_key is not None and update.mistral_api_key.strip():
        cfg["mistral_api_key"] = update.mistral_api_key.strip()
    if update.mistral_model:
        cfg["mistral_model"] = update.mistral_model.strip()
    if update.scan_paths is not None:
        cfg["scan_paths"] = update.scan_paths
    if update.nas_drive_letter is not None:
        cfg["nas_drive_letter"] = update.nas_drive_letter.strip()

    save_config(cfg)
    return {"status": "saved"}

# --- STATIC SPA SERVING (Frontend Vite Build) ---
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(frontend_dist, full_path)
        if full_path and os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))

if __name__ == "__main__":
    import uvicorn
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("=" * 60)
    print("  [OK] BiechyFinder Web App en cours sur : http://127.0.0.1:8000")
    print("=" * 60)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

