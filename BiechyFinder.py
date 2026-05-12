import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
import sqlite3
import os
import datetime
import subprocess
import json
import threading
import time

# Configuration globale
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"
DEFAULT_DB = r"C:\Users\fenzseer\Downloads\biechyfinder.db"

class BiechyFinder(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BiechyFinder v4.0 - NAS Search & Indexer")
        self.geometry("1200x850")

        # Configuration
        config = self.load_config()
        self.db_path = config.get("db_path", DEFAULT_DB)
        self.scan_paths = config.get("scan_paths", [])
        self.ssh_config = config.get("ssh_config", {"enabled": False, "host": "", "user": "", "pwd": "", "port": 22})
        self.is_indexing = False

        # Layout principal
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Barre Latérale (Navigation) ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        self.logo = ctk.CTkLabel(self.sidebar, text="BiechyFinder", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo.grid(row=0, column=0, padx=20, pady=(30, 40))

        self.btn_search = ctk.CTkButton(self.sidebar, text="🔍 Recherche", font=ctk.CTkFont(size=14), 
                                       fg_color="transparent", text_color=("gray10", "gray90"), 
                                       hover_color=("gray70", "gray30"), anchor="w", height=40,
                                       command=lambda: self.select_frame("search"))
        self.btn_search.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.btn_indexer = ctk.CTkButton(self.sidebar, text="⚡ Indexeur", font=ctk.CTkFont(size=14),
                                        fg_color="transparent", text_color=("gray10", "gray90"),
                                        hover_color=("gray70", "gray30"), anchor="w", height=40,
                                        command=lambda: self.select_frame("indexer"))
        self.btn_indexer.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self.btn_settings = ctk.CTkButton(self.sidebar, text="⚙️ Paramètres", font=ctk.CTkFont(size=14),
                                         fg_color="transparent", text_color=("gray10", "gray90"),
                                         hover_color=("gray70", "gray30"), anchor="w", height=40,
                                         command=lambda: self.select_frame("settings"))
        self.btn_settings.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        # Status DB en bas de la sidebar
        self.db_status_indicator = ctk.CTkFrame(self.sidebar, height=10, width=10, corner_radius=5)
        self.db_status_indicator.grid(row=6, column=0, padx=(20, 0), pady=(0, 20), sticky="w")
        self.update_db_indicator()

        self.db_status_label = ctk.CTkLabel(self.sidebar, text="DB Connectée", font=ctk.CTkFont(size=11))
        self.db_status_label.grid(row=6, column=0, padx=(40, 20), pady=(0, 20), sticky="w")

        # --- Frames de Contenu ---
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.indexer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.init_search_view()
        self.init_indexer_view()
        self.init_settings_view()

        # Sélection par défaut
        self.select_frame("search")
        self.update_stats()
        
        # Aperçu initial (100 derniers éléments)
        self.after(500, lambda: self.search(initial=True))

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"db_path": DEFAULT_DB, "scan_paths": []}

    def save_config(self):
        config = {
            "db_path": self.db_path,
            "scan_paths": self.scan_paths,
            "ssh_config": {
                "enabled": self.var_ssh_enabled.get(),
                "host": self.ssh_host.get(),
                "user": self.ssh_user.get(),
                "pwd": self.ssh_pwd.get(),
                "port": int(self.ssh_port.get() or 22)
            }
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder la config: {e}")

    def select_frame(self, name):
        # Reset colors
        self.btn_search.configure(fg_color="transparent")
        self.btn_indexer.configure(fg_color="transparent")
        self.btn_settings.configure(fg_color="transparent")

        # Hide all
        self.search_frame.grid_forget()
        self.indexer_frame.grid_forget()
        self.settings_frame.grid_forget()

        # Show selected
        if name == "search":
            self.search_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.btn_search.configure(fg_color=("gray75", "gray25"))
        elif name == "indexer":
            self.indexer_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.btn_indexer.configure(fg_color=("gray75", "gray25"))
        elif name == "settings":
            self.settings_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.btn_settings.configure(fg_color=("gray75", "gray25"))

    def update_db_indicator(self):
        exists = os.path.exists(self.db_path) if self.db_path else False
        color = "green" if exists else "red"
        self.db_status_indicator.configure(fg_color=color)

    # --- SEARCH VIEW ---
    def init_search_view(self):
        self.search_frame.grid_columnconfigure(0, weight=1)
        self.search_frame.grid_rowconfigure(2, weight=1)

        # Barre de recherche premium
        search_container = ctk.CTkFrame(self.search_frame, corner_radius=15, height=100)
        search_container.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 20))
        search_container.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(search_container, placeholder_text="🔍 Nom du fichier, extension, dossier...", 
                                       height=50, font=ctk.CTkFont(size=15), border_width=0)
        self.search_entry.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.search_entry.bind("<Return>", lambda e: self.search())

        self.search_btn = ctk.CTkButton(search_container, text="RECHERCHER", height=50, width=140, 
                                       font=ctk.CTkFont(weight="bold"), command=self.search)
        self.search_btn.grid(row=0, column=1, padx=(0, 20), pady=20)

        # Filtres rapides
        filter_frame = ctk.CTkFrame(self.search_frame, fg_color="transparent")
        filter_frame.grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        self.var_dirs = tk.BooleanVar(value=True)
        self.check_dirs = ctk.CTkCheckBox(filter_frame, text="Dossiers", variable=self.var_dirs, command=self.search)
        self.check_dirs.pack(side="left", padx=(0, 20))

        self.var_files = tk.BooleanVar(value=True)
        self.check_files = ctk.CTkCheckBox(filter_frame, text="Fichiers", variable=self.var_files, command=self.search)
        self.check_files.pack(side="left")

        # Résultats
        self.results_scroll = ctk.CTkScrollableFrame(self.search_frame, corner_radius=10)
        self.results_scroll.grid(row=2, column=0, sticky="nsew")

    # --- INDEXER VIEW ---
    def init_indexer_view(self):
        self.indexer_frame.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(self.indexer_frame, text="Indexeur NAS", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Scan paths list
        list_container = ctk.CTkFrame(self.indexer_frame)
        list_container.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        list_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_container, text="Dossiers à indexer:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.paths_listbox = tk.Listbox(list_container, bg="#2b2b2b", fg="white", borderwidth=0, highlightthickness=0, font=("Segoe UI", 10))
        self.paths_listbox.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        for p in self.scan_paths: self.paths_listbox.insert(tk.END, p)

        btn_row = ctk.CTkFrame(list_container, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="w")

        ctk.CTkButton(btn_row, text="+ Ajouter Dossier", width=120, command=self.add_scan_path).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="- Supprimer", width=100, fg_color="#922b21", hover_color="#7b241c", 
                     command=self.remove_scan_path).pack(side="left")

        # Progress Section
        self.progress_frame = ctk.CTkFrame(self.indexer_frame)
        self.progress_frame.grid(row=2, column=0, sticky="ew", pady=10)
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.index_status = ctk.CTkLabel(self.progress_frame, text="Prêt à indexer")
        self.index_status.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.progress_bar.set(0)

        self.btn_start_index = ctk.CTkButton(self.indexer_frame, text="LANCER L'INDEXATION", 
                                            font=ctk.CTkFont(size=16, weight="bold"), height=50, 
                                            fg_color="#1e8449", hover_color="#145a32",
                                            command=self.start_indexing_thread)
        self.btn_start_index.grid(row=3, column=0, sticky="ew", pady=20)

        # SSH Config (Collapsible-like)
        self.ssh_frame = ctk.CTkFrame(self.indexer_frame)
        self.ssh_frame.grid(row=4, column=0, sticky="ew", pady=10)
        
        self.var_ssh_enabled = tk.BooleanVar(value=self.ssh_config["enabled"])
        ctk.CTkCheckBox(self.ssh_frame, text="Utiliser SSH (Plus rapide pour NAS Linux)", 
                        variable=self.var_ssh_enabled).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        ssh_inputs = ctk.CTkFrame(self.ssh_frame, fg_color="transparent")
        ssh_inputs.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        
        self.ssh_host = ctk.CTkEntry(ssh_inputs, placeholder_text="IP NAS", width=150)
        self.ssh_host.pack(side="left", padx=5)
        self.ssh_host.insert(0, self.ssh_config["host"])
        
        self.ssh_user = ctk.CTkEntry(ssh_inputs, placeholder_text="User", width=100)
        self.ssh_user.pack(side="left", padx=5)
        self.ssh_user.insert(0, self.ssh_config["user"])
        
        self.ssh_pwd = ctk.CTkEntry(ssh_inputs, placeholder_text="Password", show="*", width=120)
        self.ssh_pwd.pack(side="left", padx=5)
        self.ssh_pwd.insert(0, self.ssh_config["pwd"])
        
        self.ssh_port = ctk.CTkEntry(ssh_inputs, placeholder_text="Port", width=60)
        self.ssh_port.pack(side="left", padx=5)
        self.ssh_port.insert(0, str(self.ssh_config["port"]))

    # --- SETTINGS VIEW ---
    def init_settings_view(self):
        self.settings_frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self.settings_frame, text="Paramètres", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 20))

        db_container = ctk.CTkFrame(self.settings_frame)
        db_container.grid(row=1, column=0, sticky="ew", pady=10)
        db_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(db_container, text="Base de données (SQLite):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.db_path_entry = ctk.CTkEntry(db_container)
        self.db_path_entry.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.db_path_entry.insert(0, self.db_path)

        ctk.CTkButton(db_container, text="Parcourir...", command=self.browse_db).grid(row=1, column=1, padx=(0, 20), pady=10)

        self.stats_info = ctk.CTkLabel(self.settings_frame, text="Stats: ...", justify="left")
        self.stats_info.grid(row=2, column=0, padx=5, pady=20, sticky="w")

        btn_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        btn_row.grid(row=3, column=0, sticky="w")

        ctk.CTkButton(btn_row, text="Sauvegarder les paramètres", command=self.apply_settings).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="Vider la Base de Données", fg_color="#922b21", hover_color="#7b241c",
                     command=self.clear_database).pack(side="left")

    def clear_database(self):
        if messagebox.askyesno("Confirmation", "Voulez-vous vraiment vider TOUTE la base de données ?"):
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute("DELETE FROM files")
                conn.commit()
                conn.close()
                self.update_stats()
                messagebox.showinfo("Succès", "Base de données vidée.")
            except Exception as e:
                messagebox.showerror("Erreur", str(e))

    # --- ACTIONS ---
    def browse_db(self):
        path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db"), ("All Files", "*.*")])
        if path:
            self.db_path_entry.delete(0, tk.END)
            self.db_path_entry.insert(0, path)

    def apply_settings(self):
        self.db_path = self.db_path_entry.get()
        self.save_config()
        self.update_db_indicator()
        self.update_stats()
        messagebox.showinfo("Succès", "Paramètres sauvegardés.")

    def add_scan_path(self):
        path = filedialog.askdirectory(title="Sélectionner un dossier (Local ou Réseau)")
        if path:
            path = os.path.normpath(path)
            if path not in self.scan_paths:
                self.scan_paths.append(path)
                self.paths_listbox.insert(tk.END, path)
                self.save_config()

    def remove_scan_path(self):
        selection = self.paths_listbox.curselection()
        if selection:
            path = self.paths_listbox.get(selection[0])
            self.scan_paths.remove(path)
            self.paths_listbox.delete(selection[0])
            self.save_config()

    def update_stats(self):
        if not os.path.exists(self.db_path):
            self.stats_info.configure(text="Base de données non trouvée.")
            return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM files")
            count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM files WHERE is_dir=1")
            dirs = c.fetchone()[0]
            size = os.path.getsize(self.db_path) / (1024 * 1024)
            self.stats_info.configure(text=f"Items: {count:,}\nDossiers: {dirs:,}\nFichiers: {count-dirs:,}\nTaille DB: {size:.1f} MB")
            conn.close()
        except:
            self.stats_info.configure(text="Erreur lecture DB")

    def search(self, initial=False):
        query = self.search_entry.get().strip()
        if not os.path.exists(self.db_path):
            if not initial: messagebox.showerror("Erreur", "DB introuvable.")
            return

        # Effacer les résultats précédents
        for w in self.results_scroll.winfo_children():
            w.destroy()
        
        self.loading_lbl = ctk.CTkLabel(self.results_scroll, text="Chargement de l'aperçu..." if initial else "Recherche...", text_color="gray")
        self.loading_lbl.pack(pady=20)
        
        # Lancer la recherche dans un thread pour ne pas figer l'UI
        threading.Thread(target=self._search_thread, args=(query, initial), daemon=True).start()

    def _search_thread(self, query, initial):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if not query:
                sql = "SELECT name, path, is_dir, mod_time FROM files ORDER BY id DESC LIMIT 100"
                params = []
            else:
                sql = "SELECT name, path, is_dir, mod_time FROM files WHERE name LIKE ?"
                params = [f"%{query}%"]
                if self.var_dirs.get() and not self.var_files.get(): sql += " AND is_dir = 1"
                elif self.var_files.get() and not self.var_dirs.get(): sql += " AND is_dir = 0"
                sql += " ORDER BY is_dir DESC, name ASC LIMIT 200"
            
            c.execute(sql, params)
            rows = c.fetchall()
            conn.close()

            # Retour au thread principal pour mettre à jour l'UI
            self.after(0, lambda: self._display_results(rows, initial))
        except Exception as e:
            self.after(0, lambda: self.loading_lbl.configure(text=f"Erreur: {str(e)}"))

    def _display_results(self, rows, initial):
        if hasattr(self, 'loading_lbl') and self.loading_lbl.winfo_exists():
            self.loading_lbl.destroy()

        if not rows:
            ctk.CTkLabel(self.results_scroll, text="Aucun résultat", text_color="gray").pack(pady=20)
            return

        for i, row in enumerate(rows):
            self.add_row(i, row)
            if i % 15 == 0: self.update_idletasks()

    def add_row(self, index, data):
        name, path, is_dir, mod_time = data
        bg = ("gray90", "gray15") if index % 2 == 0 else ("gray95", "gray18")
        
        row = ctk.CTkFrame(self.results_scroll, fg_color=bg, corner_radius=5)
        row.pack(fill="x", pady=1, padx=5)
        
        icon = "📁" if is_dir else "📄"
        lbl = ctk.CTkLabel(row, text=f"{icon} {name}", anchor="w", font=ctk.CTkFont(size=13))
        lbl.pack(side="left", padx=10, pady=5)

        path_lbl = ctk.CTkLabel(row, text=path, anchor="w", font=ctk.CTkFont(size=10), text_color="gray")
        path_lbl.pack(side="left", padx=20, fill="x", expand=True)

        row.bind("<Double-Button-1>", lambda e, p=path: self.open_path(p))
        lbl.bind("<Double-Button-1>", lambda e, p=path: self.open_path(p))

    def open_path(self, path):
        try:
            path = os.path.normpath(path)
            if os.path.isdir(path):
                os.startfile(path)
            else:
                subprocess.run(['explorer', '/select,', path])
        except Exception as e:
            messagebox.showerror("Erreur", f"Lien mort ou inaccessible: {e}")

    # --- INDEXING ENGINE ---
    def start_indexing_thread(self):
        if self.is_indexing: return
        if not self.scan_paths:
            messagebox.showwarning("Indexation", "Ajoutez au moins un dossier à scanner.")
            return
        
        self.is_indexing = True
        self.btn_start_index.configure(state="disabled", text="INDEXATION EN COURS...", fg_color="gray")
        threading.Thread(target=self.run_indexer, daemon=True).start()

    def run_indexer(self):
        try:
            import paramiko
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("""CREATE TABLE IF NOT EXISTS files 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         name TEXT, path TEXT, is_dir INTEGER, 
                         mod_time REAL, creation_time REAL)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_name ON files(name)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_path ON files(path)")
            
            for sp in self.scan_paths:
                c.execute("DELETE FROM files WHERE path LIKE ?", (f"{sp}%",))
            conn.commit()

            total_added = 0
            
            if self.var_ssh_enabled.get():
                # --- SSH SCAN (High Speed) ---
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(self.ssh_host.get(), port=int(self.ssh_port.get()), 
                            username=self.ssh_user.get(), password=self.ssh_pwd.get(), timeout=10)
                
                for base_path in self.scan_paths:
                    self.index_status.configure(text=f"SSH Scan: {base_path}")
                    # %f: filename, %p: path, %y: type (d/f), %T@: mtime, %C@: ctime
                    cmd = f'find "{base_path}" -printf "%f|%p|%y|%T@|%C@\\n"'
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    
                    batch = []
                    for line in stdout:
                        if not self.is_indexing: break
                        parts = line.strip().split('|')
                        if len(parts) == 5:
                            name, path, ptype, mtime, ctime = parts
                            try:
                                batch.append((name, path, 1 if ptype=='d' else 0, float(mtime), float(ctime)))
                            except: continue
                            
                            if len(batch) >= 1000:
                                c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                                total_added += len(batch)
                                batch = []
                                self.index_status.configure(text=f"SSH Indexé: {total_added:,}...")
                    
                    if batch:
                        c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                        total_added += len(batch)
                
                ssh.close()
            else:
                # --- LOCAL/SMB SCAN ---
                for base_path in self.scan_paths:
                    self.index_status.configure(text=f"Scan: {base_path}")
                    self.progress_bar.set(0)
                    
                    batch = []
                    for root, dirs, files in os.walk(base_path):
                        if not self.is_indexing: break
                        
                        # Add current directory
                        try:
                            batch.append((os.path.basename(root), root, 1, os.path.getmtime(root), os.path.getctime(root)))
                        except: pass
                        
                        for f in files:
                            fpath = os.path.join(root, f)
                            try:
                                batch.append((f, fpath, 0, os.path.getmtime(fpath), os.path.getctime(fpath)))
                            except: continue
                        
                        if len(batch) > 1000:
                            c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                            total_added += len(batch)
                            batch = []
                            self.index_status.configure(text=f"Indexé: {total_added:,}...")
                    
                    if batch:
                        c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                        total_added += len(batch)

            conn.commit()
            conn.close()
            self.index_status.configure(text=f"Terminé ! {total_added:,} éléments indexés.")
        except Exception as e:
            self.index_status.configure(text=f"Erreur: {str(e)}")
        finally:
            self.is_indexing = False
            self.btn_start_index.configure(state="normal", text="LANCER L'INDEXATION", fg_color="#1e8449")
            self.update_stats()

if __name__ == "__main__":
    app = BiechyFinder()
    app.mainloop()
