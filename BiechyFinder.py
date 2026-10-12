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
import re
import sys
import shutil
import urllib.request
import urllib.error

# --- Version & Mise à jour ---
APP_VERSION = "5.0"
GITHUB_REPO = "fenekee/BiechyFinder"

# Configuration globale
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"
DEFAULT_DB = r"C:\Users\fenzseer\Downloads\biechyfinder.db"

class BiechyFinder(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"BiechyFinder v{APP_VERSION} - NAS Search & Indexer")
        self.geometry("1200x850")

        # Icône de la fenêtre et de la barre des tâches
        if getattr(sys, 'frozen', False):
            _icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
        else:
            _icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if os.path.exists(_icon_path):
            try:
                self.iconbitmap(_icon_path)
            except Exception:
                pass

        # Configuration
        config = self.load_config()
        self.db_path = config.get("db_path", DEFAULT_DB)
        self.scan_paths = config.get("scan_paths", [])
        self.ssh_config = config.get("ssh_config", {"enabled": False, "host": "", "user": "", "pwd": "", "port": 22})
        self.mistral_api_key = config.get("mistral_api_key", "")
        self.mistral_model = config.get("mistral_model", "mistral-small-latest")
        self.nas_drive_letter = config.get("nas_drive_letter", "")
        self.is_indexing = False
        self.chat_history = []  # Historique des messages pour le contexte Mistral
        self._views_initialized = {"search": False, "indexer": False, "chat": False, "settings": False}

        # Layout principal
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Barre Latérale (Navigation) ---
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=0)

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

        self.btn_chat = ctk.CTkButton(self.sidebar, text="🤖 Chat IA", font=ctk.CTkFont(size=14),
                                       fg_color="transparent", text_color=("gray10", "gray90"),
                                       hover_color=("gray70", "gray30"), anchor="w", height=40,
                                       command=lambda: self.select_frame("chat"))
        self.btn_chat.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

        self.btn_settings = ctk.CTkButton(self.sidebar, text="⚙️ Paramètres", font=ctk.CTkFont(size=14),
                                         fg_color="transparent", text_color=("gray10", "gray90"),
                                         hover_color=("gray70", "gray30"), anchor="w", height=40,
                                         command=lambda: self.select_frame("settings"))
        self.btn_settings.grid(row=4, column=0, sticky="ew", padx=10, pady=5)

        # Status DB en bas de la sidebar
        self.db_status_indicator = ctk.CTkFrame(self.sidebar, height=10, width=10, corner_radius=5)
        self.db_status_indicator.grid(row=7, column=0, padx=(20, 0), pady=(0, 5), sticky="w")
        self.update_db_indicator()

        self.db_status_label = ctk.CTkLabel(self.sidebar, text="DB Connectée", font=ctk.CTkFont(size=11))
        self.db_status_label.grid(row=7, column=0, padx=(40, 20), pady=(0, 5), sticky="w")

        # Bouton mise à jour
        self.btn_update = ctk.CTkButton(
            self.sidebar,
            text=f"v{APP_VERSION} ✓",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color="gray",
            hover_color=("gray70", "gray30"),
            height=28,
            command=self.check_for_update
        )
        self.btn_update.grid(row=8, column=0, sticky="ew", padx=10, pady=(0, 15))

        # --- Frames créées à la demande (pas au démarrage) ---
        self.search_frame = None
        self.indexer_frame = None
        self.chat_frame = None
        self.settings_frame = None

        # Stats en thread pour ne pas bloquer le démarrage
        threading.Thread(target=self._update_stats_async, daemon=True).start()

        # Vérification MAJ au démarrage (silencieuse)
        threading.Thread(target=self._do_check_update, args=(False,), daemon=True).start()

        # Démarrage différé : la fenêtre s'affiche d'abord, puis on charge le contenu
        self.after(1, self._deferred_startup)

    def _deferred_startup(self):
        """Charge la vue recherche après que la fenêtre est visible."""
        self.select_frame("search")
        self.after(50, lambda: self.search(initial=True))

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"db_path": DEFAULT_DB, "scan_paths": []}

    def save_config(self):
        # SSH config : utiliser les widgets si initialisés, sinon les valeurs en mémoire
        if self._views_initialized.get("indexer"):
            ssh_cfg = {
                "enabled": self.var_ssh_enabled.get(),
                "host": self.ssh_host.get(),
                "user": self.ssh_user.get(),
                "pwd": self.ssh_pwd.get(),
                "port": int(self.ssh_port.get() or 22)
            }
        else:
            ssh_cfg = self.ssh_config

        config = {
            "db_path": self.db_path,
            "scan_paths": self.scan_paths,
            "ssh_config": ssh_cfg,
            "mistral_api_key": self.mistral_api_key,
            "mistral_model": self.mistral_model,
            "nas_drive_letter": self.nas_drive_letter
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder la config: {e}")

    def select_frame(self, name):
        # Lazy init : créer le frame + son contenu au premier accès
        if not self._views_initialized.get(name, True):
            if name == "search":
                self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
                self.init_search_view()
            elif name == "indexer":
                self.indexer_frame = ctk.CTkFrame(self, fg_color="transparent")
                self.init_indexer_view()
            elif name == "chat":
                self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
                self.init_chat_view()
            elif name == "settings":
                self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
                self.init_settings_view()
            self._views_initialized[name] = True

        # Reset colors
        self.btn_search.configure(fg_color="transparent")
        self.btn_indexer.configure(fg_color="transparent")
        self.btn_chat.configure(fg_color="transparent")
        self.btn_settings.configure(fg_color="transparent")

        # Hide all (seulement les frames qui existent)
        if self.search_frame: self.search_frame.grid_forget()
        if self.indexer_frame: self.indexer_frame.grid_forget()
        if self.chat_frame: self.chat_frame.grid_forget()
        if self.settings_frame: self.settings_frame.grid_forget()

        # Show selected
        if name == "search":
            self.search_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.btn_search.configure(fg_color=("gray75", "gray25"))
        elif name == "indexer":
            self.indexer_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.btn_indexer.configure(fg_color=("gray75", "gray25"))
        elif name == "chat":
            self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.btn_chat.configure(fg_color=("gray75", "gray25"))
        elif name == "settings":
            self.settings_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.btn_settings.configure(fg_color=("gray75", "gray25"))

    def _remap_drive_letter(self, path):
        """Remplace la lettre de lecteur dans un chemin si une lettre NAS est configurée."""
        if self.nas_drive_letter and path and len(path) >= 2 and path[1] == ':':
            return self.nas_drive_letter.upper() + path[1:]
        return path

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

        # Bouton Résumé IA
        self.summary_frame = ctk.CTkFrame(self.indexer_frame)
        self.summary_frame.grid(row=5, column=0, sticky="ew", pady=10)
        self.summary_frame.grid_columnconfigure(0, weight=1)

        self.btn_generate_summary = ctk.CTkButton(self.summary_frame, text="\U0001f9e0 Générer le résumé IA du NAS",
                                                   font=ctk.CTkFont(size=14, weight="bold"), height=45,
                                                   fg_color="#6c3483", hover_color="#4a235a",
                                                   command=self.start_summary_thread)
        self.btn_generate_summary.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")

        self.summary_status = ctk.CTkLabel(self.summary_frame, text=self._get_summary_status_text(),
                                           font=ctk.CTkFont(size=11), text_color="gray")
        self.summary_status.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # SSH Config (Collapsible-like)
        self.ssh_frame = ctk.CTkFrame(self.indexer_frame)
        self.ssh_frame.grid(row=6, column=0, sticky="ew", pady=10)
        
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

    # --- CHAT IA VIEW ---
    def init_chat_view(self):
        self.chat_frame.grid_columnconfigure(0, weight=1)
        self.chat_frame.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self.chat_frame, corner_radius=15, height=60)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="🤖 Assistant IA - Recherche de fichiers",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=15, sticky="w")

        self.btn_clear_chat = ctk.CTkButton(header, text="🗑️ Effacer", width=100,
                                            fg_color="#922b21", hover_color="#7b241c",
                                            command=self.clear_chat)
        self.btn_clear_chat.grid(row=0, column=1, padx=20, pady=15)

        # Zone de messages (scrollable)
        self.chat_messages = ctk.CTkScrollableFrame(self.chat_frame, corner_radius=10)
        self.chat_messages.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.chat_messages.grid_columnconfigure(0, weight=1)

        # Message d'accueil
        self._add_bot_message("Salut ! 👋 Je suis ton assistant IA.\n\nDécris-moi ce que tu cherches en langage naturel, par exemple :\n• \"Trouve les fichiers PDF\"\n• \"Montre-moi les vidéos modifiées en 2024\"\n• \"Quels dossiers contiennent 'projet' ?\"\n\nJe vais interroger ta base de données pour toi !")

        # Barre d'input en bas
        input_frame = ctk.CTkFrame(self.chat_frame, corner_radius=15)
        input_frame.grid(row=2, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Décris ce que tu cherches...",
                                       height=50, font=ctk.CTkFont(size=14), border_width=0)
        self.chat_entry.grid(row=0, column=0, padx=20, pady=15, sticky="ew")
        self.chat_entry.bind("<Return>", lambda e: self.send_chat_message())

        self.btn_send_chat = ctk.CTkButton(input_frame, text="Envoyer ▶", height=50, width=120,
                                           font=ctk.CTkFont(weight="bold"),
                                           command=self.send_chat_message)
        self.btn_send_chat.grid(row=0, column=1, padx=(0, 20), pady=15)

    def _add_user_message(self, text):
        """Ajoute une bulle de message utilisateur (alignée à droite)."""
        container = ctk.CTkFrame(self.chat_messages, fg_color="transparent")
        container.pack(fill="x", pady=5, padx=10)

        bubble = ctk.CTkFrame(container, fg_color=("#2980b9", "#1a5276"), corner_radius=15)
        bubble.pack(side="right", padx=(80, 0))

        lbl = ctk.CTkLabel(bubble, text=text, wraplength=500, justify="left",
                           font=ctk.CTkFont(size=13), text_color="white")
        lbl.pack(padx=15, pady=10)

    def _add_bot_message(self, text):
        """Ajoute une bulle de message IA (alignée à gauche)."""
        container = ctk.CTkFrame(self.chat_messages, fg_color="transparent")
        container.pack(fill="x", pady=5, padx=10)

        bubble = ctk.CTkFrame(container, fg_color=("gray80", "gray20"), corner_radius=15)
        bubble.pack(side="left", padx=(0, 80))

        lbl = ctk.CTkLabel(bubble, text=text, wraplength=500, justify="left",
                           font=ctk.CTkFont(size=13))
        lbl.pack(padx=15, pady=10)

    def _add_file_results(self, rows):
        """Ajoute les résultats de fichiers cliquables dans le chat."""
        if not rows:
            return

        container = ctk.CTkFrame(self.chat_messages, fg_color="transparent")
        container.pack(fill="x", pady=(0, 5), padx=10)

        results_frame = ctk.CTkFrame(container, fg_color=("gray85", "gray17"), corner_radius=10)
        results_frame.pack(side="left", padx=(0, 80), fill="x", expand=True)

        max_display = min(len(rows), 20)
        for i in range(max_display):
            row_data = rows[i]
            name = row_data[0]
            path = row_data[1]
            display_path = self._remap_drive_letter(path)
            is_dir = row_data[2] if len(row_data) > 2 else 0

            icon = "📁" if is_dir else "📄"
            bg = ("gray90", "gray15") if i % 2 == 0 else ("gray95", "gray18")

            file_row = ctk.CTkFrame(results_frame, fg_color=bg, corner_radius=5)
            file_row.pack(fill="x", pady=1, padx=5)

            lbl = ctk.CTkLabel(file_row, text=f"{icon} {name}", anchor="w", font=ctk.CTkFont(size=12))
            lbl.pack(side="left", padx=10, pady=4)

            path_lbl = ctk.CTkLabel(file_row, text=display_path, anchor="w", font=ctk.CTkFont(size=9), text_color="gray")
            path_lbl.pack(side="left", padx=10, fill="x", expand=True)

            file_row.bind("<Double-Button-1>", lambda e, p=display_path: self.open_path(p))
            lbl.bind("<Double-Button-1>", lambda e, p=display_path: self.open_path(p))
            path_lbl.bind("<Double-Button-1>", lambda e, p=display_path: self.open_path(p))

        if len(rows) > max_display:
            ctk.CTkLabel(results_frame, text=f"... et {len(rows) - max_display} autres résultats",
                         text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=5)

    def clear_chat(self):
        """Efface la conversation et reset l'historique."""
        for w in self.chat_messages.winfo_children():
            w.destroy()
        self.chat_history = []
        self._add_bot_message("Conversation effacée ! 🧹\nPose-moi une nouvelle question.")

    def send_chat_message(self):
        """Envoie le message de l'utilisateur au chatbot IA."""
        msg = self.chat_entry.get().strip()
        if not msg:
            return

        self.chat_entry.delete(0, tk.END)
        self._add_user_message(msg)

        # Vérifications
        if not self.mistral_api_key:
            self._add_bot_message("⚠️ Clé API Mistral non configurée !\n\nVa dans ⚙️ Paramètres pour ajouter ta clé API.")
            self.btn_send_chat.configure(state="normal")
            self.chat_entry.configure(state="normal")
            self.chat_entry.focus()
            return

        if not os.path.exists(self.db_path):
            self._add_bot_message("⚠️ Base de données introuvable !\nVérifie le chemin dans les paramètres.")
            self.btn_send_chat.configure(state="normal")
            self.chat_entry.configure(state="normal")
            self.chat_entry.focus()
            return

        # Afficher un indicateur de chargement
        loading_container = ctk.CTkFrame(self.chat_messages, fg_color="transparent")
        loading_container.pack(fill="x", pady=5, padx=10)
        loading_bubble = ctk.CTkFrame(loading_container, fg_color=("gray80", "gray20"), corner_radius=15)
        loading_bubble.pack(side="left")
        loading_lbl = ctk.CTkLabel(loading_bubble, text="⏳ Réflexion en cours...",
                                   font=ctk.CTkFont(size=13), text_color="gray")
        loading_lbl.pack(padx=15, pady=10)

        # Scroll en bas
        self.chat_messages._parent_canvas.yview_moveto(1.0)

        # Désactiver le bouton pendant le traitement
        self.btn_send_chat.configure(state="disabled")
        self.chat_entry.configure(state="disabled")

        # Lancer dans un thread
        threading.Thread(target=self._process_ai_query, args=(msg, loading_container), daemon=True).start()

    def _get_summary_status_text(self):
        """Retourne le texte de statut du résumé IA."""
        summary_path = self._get_summary_path()
        if summary_path and os.path.exists(summary_path):
            mod_time = os.path.getmtime(summary_path)
            date_str = datetime.datetime.fromtimestamp(mod_time).strftime("%d/%m/%Y à %H:%M")
            return f"✅ Résumé existant (généré le {date_str})"
        return "Aucun résumé généré pour l'instant."

    def _get_summary_path(self):
        """Retourne le chemin du fichier résumé (à côté de la DB)."""
        if self.db_path:
            return os.path.join(os.path.dirname(self.db_path), "nas_summary.txt")
        return None

    def _load_nas_summary(self):
        """Charge le résumé du NAS depuis le fichier."""
        summary_path = self._get_summary_path()
        if summary_path and os.path.exists(summary_path):
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except:
                pass
        return None

    def start_summary_thread(self):
        """Lance la génération du résumé dans un thread."""
        if not self.mistral_api_key:
            messagebox.showwarning("Résumé IA", "Configure ta clé API Mistral dans ⚙️ Paramètres d'abord.")
            return
        if not os.path.exists(self.db_path):
            messagebox.showwarning("Résumé IA", "Base de données introuvable.")
            return
        self.btn_generate_summary.configure(state="disabled", text="🧠 Génération en cours...", fg_color="gray")
        self.summary_status.configure(text="⏳ Analyse de la DB et appel à Mistral...")
        threading.Thread(target=self._generate_nas_summary, daemon=True).start()

    def _collect_nas_stats(self):
        """Collecte les statistiques structurelles de la DB pour le résumé."""
        stats = {}
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            # Stats globales
            c.execute("SELECT COUNT(*) FROM files")
            stats["total"] = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM files WHERE is_dir=1")
            stats["total_dirs"] = c.fetchone()[0]
            stats["total_files"] = stats["total"] - stats["total_dirs"]

            # Top 20 extensions
            c.execute("""
                SELECT 
                    LOWER(CASE WHEN INSTR(name, '.') > 0 
                          THEN '.' || SUBSTR(name, LENGTH(name) - LENGTH(REPLACE(name, '.', '')) + 1 + 1)
                          ELSE '(sans extension)' END) as ext,
                    COUNT(*) as cnt
                FROM files WHERE is_dir=0
                GROUP BY ext ORDER BY cnt DESC LIMIT 20
            """)
            stats["extensions"] = c.fetchall()

            # Top 30 dossiers racines (niveau 1 sous les scan_paths)
            root_dirs = []
            for sp in self.scan_paths:
                sp_norm = sp.replace('\\', '/')
                c.execute("""
                    SELECT name, path FROM files 
                    WHERE is_dir=1 AND path LIKE ? 
                    AND path NOT LIKE ?
                    ORDER BY name ASC LIMIT 30
                """, (f"{sp_norm}/%", f"{sp_norm}/%/%"))
                root_dirs.extend(c.fetchall())
                # Aussi essayer avec backslash
                sp_back = sp.replace('/', '\\')
                c.execute("""
                    SELECT name, path FROM files 
                    WHERE is_dir=1 AND path LIKE ? 
                    AND path NOT LIKE ?
                    ORDER BY name ASC LIMIT 30
                """, (f"{sp_back}\\%", f"{sp_back}\\%\\%"))
                root_dirs.extend(c.fetchall())
            stats["root_dirs"] = root_dirs[:30]

            # Top 15 dossiers avec le plus de fichiers directs
            c.execute("""
                SELECT 
                    CASE 
                        WHEN INSTR(REPLACE(path, '\\', '/'), '/') > 0 
                        THEN SUBSTR(REPLACE(path, '\\', '/'), 1, LENGTH(REPLACE(path, '\\', '/')) - LENGTH(name) - 1)
                        ELSE path 
                    END as parent_dir,
                    COUNT(*) as cnt
                FROM files WHERE is_dir=0
                GROUP BY parent_dir ORDER BY cnt DESC LIMIT 15
            """)
            stats["top_folders_by_count"] = c.fetchall()

            conn.close()
        except Exception as e:
            stats["error"] = str(e)
        return stats

    def _call_mistral_api(self, messages):
        """Appelle l'API Mistral directement via HTTP (sans SDK)."""
        import httpx
        response = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.mistral_model,
                "messages": messages,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _generate_nas_summary(self):
        """Génère un résumé IA du NAS via Mistral (1 seul appel API)."""
        try:
            # Collecter les stats
            stats = self._collect_nas_stats()
            if "error" in stats:
                self.after(0, lambda: self._on_summary_done(False, f"Erreur DB : {stats['error']}"))
                return

            # Construire le prompt avec les données
            data_prompt = f"""Voici les statistiques d'un NAS/stockage réseau. Génère un résumé structuré et concis (10-15 lignes max) décrivant le contenu de ce stockage. Le résumé doit aider un assistant IA à retrouver des fichiers plus tard.

== STATISTIQUES ==
Total éléments : {stats.get('total', 0):,}
Dossiers : {stats.get('total_dirs', 0):,}
Fichiers : {stats.get('total_files', 0):,}

== TOP EXTENSIONS ==
{chr(10).join(f"  {ext}: {cnt} fichiers" for ext, cnt in stats.get('extensions', []))}

== DOSSIERS RACINES ==
{chr(10).join(f"  📁 {name} ({path})" for name, path in stats.get('root_dirs', []))}

== DOSSIERS LES PLUS REMPLIS ==
{chr(10).join(f"  {folder}: {cnt} fichiers" for folder, cnt in stats.get('top_folders_by_count', []))}

Génère un résumé en français, naturel et utile. Mentionne les types de contenu qu'on peut trouver, les dossiers importants, et les types de fichiers dominants."""

            summary = self._call_mistral_api([
                {"role": "system", "content": "Tu es un assistant qui génère des résumés concis de stockage réseau."},
                {"role": "user", "content": data_prompt}
            ]).strip()

            # Sauvegarder le résumé
            summary_path = self._get_summary_path()
            if summary_path:
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary)

            self.after(0, lambda: self._on_summary_done(True, summary))

        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                error_msg = "Clé API invalide"
            self.after(0, lambda: self._on_summary_done(False, error_msg))

    def _on_summary_done(self, success, message):
        """Callback après la génération du résumé (thread principal)."""
        self.btn_generate_summary.configure(state="normal", text="\U0001f9e0 Générer le résumé IA du NAS", fg_color="#6c3483")
        if success:
            self.summary_status.configure(text=self._get_summary_status_text())
            messagebox.showinfo("Résumé IA", "Résumé du NAS généré avec succès ! ✅\nIl sera utilisé par le chatbot.")
        else:
            self.summary_status.configure(text=f"❌ Erreur : {message}")

    def _get_system_prompt(self):
        """Construit le system prompt pour Mistral avec le schéma de la DB."""
        base_prompt = """Tu es un assistant spécialisé dans la recherche de fichiers. Tu aides l'utilisateur à retrouver des fichiers et dossiers dans sa base de données SQLite.

Voici le schéma de la table `files` :
- id : INTEGER PRIMARY KEY
- name : TEXT (nom du fichier ou dossier)
- path : TEXT (chemin complet)
- is_dir : INTEGER (1 = dossier, 0 = fichier)
- mod_time : REAL (timestamp de modification Unix)
- creation_time : REAL (timestamp de création Unix)

Règles STRICTES :
1. Réponds TOUJOURS avec un bloc JSON valide entre ```json et ``` contenant :
   - "sql" : la requête SELECT SQLite à exécuter (LIMIT 50 max). N'utilise QUE des SELECT.
   - "explanation" : une courte explication de ce que tu cherches (en français).
2. Utilise LIKE pour les recherches de nom (ex: name LIKE '%pdf' pour les PDF).
3. Pour les dates, utilise les timestamps Unix avec strftime ou des comparaisons numériques.
4. Pour les extensions, cherche avec name LIKE '%.ext'
5. Ne fais JAMAIS de DELETE, UPDATE, INSERT, DROP, ou ALTER.
6. Si la question n'est pas liée aux fichiers, réponds quand même en JSON avec un sql vide et ton explanation.

Exemples :
Utilisateur: "Trouve les PDF"
```json
{"sql": "SELECT name, path, is_dir, mod_time FROM files WHERE name LIKE '%.pdf' AND is_dir = 0 LIMIT 50", "explanation": "Je recherche tous les fichiers PDF."}
```

Utilisateur: "Montre les gros dossiers qui contiennent projet"
```json
{"sql": "SELECT name, path, is_dir, mod_time FROM files WHERE name LIKE '%projet%' AND is_dir = 1 LIMIT 50", "explanation": "Je cherche les dossiers dont le nom contient 'projet'."}
```"""

        # Injecter le résumé du NAS s'il existe
        nas_summary = self._load_nas_summary()
        if nas_summary:
            base_prompt += f"\n\n== RÉSUMÉ DU CONTENU DU NAS ==\nVoici un résumé du stockage de l'utilisateur. Utilise ces informations pour mieux orienter tes recherches SQL :\n\n{nas_summary}"

        return base_prompt

    def _process_ai_query(self, user_message, loading_widget):
        """Traite la requête IA dans un thread séparé."""
        try:
            # Construire les messages avec historique
            messages = [{"role": "system", "content": self._get_system_prompt()}]
            # Ajouter l'historique récent (max 10 échanges pour le contexte)
            for h in self.chat_history[-10:]:
                messages.append(h)
            messages.append({"role": "user", "content": user_message})

            # Appel API Mistral
            ai_content = self._call_mistral_api(messages)

            # Sauvegarder dans l'historique
            self.chat_history.append({"role": "user", "content": user_message})
            self.chat_history.append({"role": "assistant", "content": ai_content})

            # Parser la réponse JSON
            sql_query = None
            explanation = ai_content
            rows = []

            # Extraire le JSON du markdown
            json_match = re.search(r'```json\s*\n?(.*?)\n?```', ai_content, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1).strip())
                    sql_query = parsed.get("sql", "").strip()
                    explanation = parsed.get("explanation", "")
                except json.JSONDecodeError:
                    explanation = ai_content
            else:
                # Tenter de parser directement comme JSON
                try:
                    parsed = json.loads(ai_content.strip())
                    sql_query = parsed.get("sql", "").strip()
                    explanation = parsed.get("explanation", ai_content)
                except json.JSONDecodeError:
                    explanation = ai_content

            # Exécuter la requête SQL si valide
            if sql_query and sql_query.upper().startswith("SELECT"):
                try:
                    conn = sqlite3.connect(self.db_path)
                    c = conn.cursor()
                    c.execute(sql_query)
                    rows = c.fetchall()
                    conn.close()

                    if rows:
                        explanation += f"\n\n📊 {len(rows)} résultat(s) trouvé(s) :"
                    else:
                        explanation += "\n\n😕 Aucun résultat trouvé."
                except Exception as db_err:
                    explanation += f"\n\n❌ Erreur SQL : {str(db_err)}"

            # Mettre à jour l'UI dans le thread principal
            self.after(0, lambda: self._display_ai_response(explanation, rows, loading_widget))

        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                error_msg = "⚠️ Clé API invalide. Vérifie ta clé dans les paramètres."
            elif "429" in error_msg:
                error_msg = "⚠️ Trop de requêtes. Attends un moment et réessaie."
            else:
                error_msg = f"❌ Erreur : {error_msg}"
            self.after(0, lambda: self._display_ai_response(error_msg, [], loading_widget))

    def _display_ai_response(self, text, rows, loading_widget):
        """Affiche la réponse de l'IA dans le chat (thread principal)."""
        try:
            # Supprimer l'indicateur de chargement
            if loading_widget and loading_widget.winfo_exists():
                loading_widget.destroy()

            # Afficher la réponse
            self._add_bot_message(text)

            # Afficher les résultats cliquables
            if rows:
                self._add_file_results(rows)

            # Scroll en bas
            self.after(100, lambda: self.chat_messages._parent_canvas.yview_moveto(1.0))
        finally:
            # Toujours réactiver l'input, même en cas d'erreur
            self.btn_send_chat.configure(state="normal")
            self.chat_entry.configure(state="normal")
            self.chat_entry.focus()

    # --- SETTINGS VIEW ---
    def init_settings_view(self):
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_rowconfigure(0, weight=1)

        # Scrollable container pour que tous les réglages soient accessibles
        scroll = ctk.CTkScrollableFrame(self.settings_frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(scroll, text="Paramètres", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 20))

        db_container = ctk.CTkFrame(scroll)
        db_container.grid(row=1, column=0, sticky="ew", pady=10)
        db_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(db_container, text="Base de données (SQLite):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.db_path_entry = ctk.CTkEntry(db_container)
        self.db_path_entry.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.db_path_entry.insert(0, self.db_path)

        ctk.CTkButton(db_container, text="Parcourir...", command=self.browse_db).grid(row=1, column=1, padx=(0, 20), pady=10)

        self.stats_info = ctk.CTkLabel(scroll, text="Stats: ...", justify="left")
        self.stats_info.grid(row=2, column=0, padx=5, pady=20, sticky="w")
        # Charger les stats pré-calculées si disponibles
        if hasattr(self, '_cached_stats'):
            self.stats_info.configure(text=self._cached_stats)

        # --- Section Lettre de Lecteur NAS ---
        drive_container = ctk.CTkFrame(scroll)
        drive_container.grid(row=3, column=0, sticky="ew", pady=10)
        drive_container.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(drive_container, text="💾 Lettre de lecteur NAS", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(15, 5), sticky="w")

        ctk.CTkLabel(drive_container, text="Les chemins en base seront remappés vers cette lettre :",
                     font=ctk.CTkFont(size=11), text_color="gray").grid(
            row=1, column=0, columnspan=2, padx=20, pady=(0, 5), sticky="w")

        self.drive_letter_entry = ctk.CTkEntry(drive_container, placeholder_text="Ex: B, Z, D...", width=80)
        self.drive_letter_entry.grid(row=2, column=0, padx=20, pady=(5, 15), sticky="w")
        if self.nas_drive_letter:
            self.drive_letter_entry.insert(0, self.nas_drive_letter)

        # Afficher les lecteurs détectés
        try:
            detected = [chr(d) for d in range(65, 91) if os.path.exists(f"{chr(d)}:\\")]
            drives_text = "Lecteurs détectés : " + ", ".join(f"{d}:" for d in detected)
        except:
            drives_text = ""
        ctk.CTkLabel(drive_container, text=drives_text, font=ctk.CTkFont(size=10), text_color="gray").grid(
            row=2, column=1, padx=10, pady=(5, 15), sticky="w")

        # --- Section Mistral AI ---
        ai_container = ctk.CTkFrame(scroll)
        ai_container.grid(row=4, column=0, sticky="ew", pady=(20, 10))
        ai_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(ai_container, text="🤖 Configuration Mistral AI", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(15, 5), sticky="w")

        ctk.CTkLabel(ai_container, text="Clé API :", font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.mistral_key_entry = ctk.CTkEntry(ai_container, show="*", placeholder_text="Colle ta clé API Mistral ici...")
        self.mistral_key_entry.grid(row=2, column=0, columnspan=2, padx=20, pady=(5, 10), sticky="ew")
        if self.mistral_api_key:
            self.mistral_key_entry.insert(0, self.mistral_api_key)

        ctk.CTkLabel(ai_container, text="Modèle :", font=ctk.CTkFont(size=12)).grid(
            row=3, column=0, padx=20, pady=(5, 0), sticky="w")
        self.mistral_model_menu = ctk.CTkOptionMenu(ai_container,
                                                     values=["mistral-small-latest", "mistral-large-latest"],
                                                     width=250)
        self.mistral_model_menu.grid(row=4, column=0, padx=20, pady=(5, 15), sticky="w")
        self.mistral_model_menu.set(self.mistral_model)

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.grid(row=5, column=0, sticky="w", pady=(10, 20))

        ctk.CTkButton(btn_row, text="💾 Sauvegarder les paramètres", command=self.apply_settings).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="🗑️ Vider la Base de Données", fg_color="#922b21", hover_color="#7b241c",
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
        self.mistral_api_key = self.mistral_key_entry.get().strip()
        self.mistral_model = self.mistral_model_menu.get()
        # Lettre de lecteur NAS : garder uniquement la première lettre
        raw_letter = self.drive_letter_entry.get().strip().upper()
        if raw_letter and raw_letter[0].isalpha():
            self.nas_drive_letter = raw_letter[0]
        else:
            self.nas_drive_letter = ""
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
        if not self._views_initialized.get("settings"):
            return
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

    def _update_stats_async(self):
        """Version thread-safe de update_stats pour le démarrage."""
        if not os.path.exists(self.db_path):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM files")
            count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM files WHERE is_dir=1")
            dirs = c.fetchone()[0]
            conn.close()
            size = os.path.getsize(self.db_path) / (1024 * 1024)
            # On stocke les résultats pour quand settings sera ouvert
            self._cached_stats = f"Items: {count:,}\nDossiers: {dirs:,}\nFichiers: {count-dirs:,}\nTaille DB: {size:.1f} MB"
        except:
            self._cached_stats = "Erreur lecture DB"

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
                sql = "SELECT name, path, is_dir, mod_time FROM files ORDER BY id DESC LIMIT 30"
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
        display_path = self._remap_drive_letter(path)
        bg = ("gray90", "gray15") if index % 2 == 0 else ("gray95", "gray18")
        
        row = ctk.CTkFrame(self.results_scroll, fg_color=bg, corner_radius=5)
        row.pack(fill="x", pady=1, padx=5)
        
        icon = "📁" if is_dir else "📄"
        lbl = ctk.CTkLabel(row, text=f"{icon} {name}", anchor="w", font=ctk.CTkFont(size=13))
        lbl.pack(side="left", padx=10, pady=5)

        path_lbl = ctk.CTkLabel(row, text=display_path, anchor="w", font=ctk.CTkFont(size=10), text_color="gray")
        path_lbl.pack(side="left", padx=20, fill="x", expand=True)

        row.bind("<Double-Button-1>", lambda e, p=display_path: self.open_path(p))
        lbl.bind("<Double-Button-1>", lambda e, p=display_path: self.open_path(p))

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

    def _fast_scan(self, base_path):
        """Scan récursif avec os.scandir() — 2-5× plus rapide que os.walk() sur réseau.
        Yields des tuples (name, path, is_dir, mod_time, creation_time)."""
        try:
            with os.scandir(base_path) as it:
                for entry in it:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        is_dir = entry.is_dir(follow_symlinks=False)
                        yield (entry.name, entry.path, 1 if is_dir else 0, stat.st_mtime, stat.st_ctime)
                        if is_dir:
                            yield from self._fast_scan(entry.path)
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass

    def run_indexer(self):
        try:
            import paramiko
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Optimisations SQLite pour écriture en masse
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA cache_size=-64000")
            
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
                            
                            if len(batch) >= 5000:
                                c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                                total_added += len(batch)
                                batch = []
                                self.index_status.configure(text=f"SSH Indexé: {total_added:,}...")
                    
                    if batch:
                        c.executemany("INSERT INTO files (name, path, is_dir, mod_time, creation_time) VALUES (?,?,?,?,?)", batch)
                        total_added += len(batch)
                
                ssh.close()
            else:
                # --- LOCAL/SMB SCAN (optimisé avec scandir) ---
                for base_path in self.scan_paths:
                    self.index_status.configure(text=f"Scan: {base_path}")
                    self.progress_bar.set(0)
                    
                    batch = []
                    for entry_tuple in self._fast_scan(base_path):
                        if not self.is_indexing: break
                        batch.append(entry_tuple)
                        
                        if len(batch) >= 5000:
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

            # Générer le résumé IA automatiquement si clé API configurée
            if self.mistral_api_key:
                self.index_status.configure(text=f"Terminé ! {total_added:,} indexés. 🧠 Génération du résumé IA...")
                self.after(0, lambda: self.summary_status.configure(text="⏳ Génération auto du résumé..."))
                self._generate_nas_summary()

        except Exception as e:
            self.index_status.configure(text=f"Erreur: {str(e)}")
        finally:
            self.is_indexing = False
            self.btn_start_index.configure(state="normal", text="LANCER L'INDEXATION", fg_color="#1e8449")
            self.update_stats()

    # --- MISE À JOUR ---
    def check_for_update(self):
        """Lancé manuellement via le bouton — affiche toujours un retour."""
        self.btn_update.configure(text="⏳ Vérification...", text_color="gray", state="disabled")
        threading.Thread(target=self._do_check_update, args=(True,), daemon=True).start()

    def _do_check_update(self, show_feedback):
        """Interroge l'API GitHub Releases pour comparer les versions."""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": f"BiechyFinder/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())

            latest_tag = data.get("tag_name", "").lstrip("v")
            release_name = data.get("name", latest_tag)
            assets = data.get("assets", [])

            # Chercher un asset .py ou .exe dans la release
            py_asset = next((a for a in assets if a["name"].endswith(".py")), None)
            exe_asset = next((a for a in assets if a["name"].endswith(".exe")), None)
            download_asset = (exe_asset or py_asset) if getattr(sys, 'frozen', False) else (py_asset or exe_asset)

            # Comparer les versions (simple comparaison numérique)
            try:
                is_newer = tuple(int(x) for x in latest_tag.split(".")) > tuple(int(x) for x in APP_VERSION.split("."))
            except ValueError:
                is_newer = latest_tag != APP_VERSION

            if is_newer:
                self.after(0, lambda: self._show_update_available(latest_tag, release_name, download_asset))
            else:
                self.after(0, lambda: self._show_up_to_date(show_feedback))

        except urllib.error.HTTPError as e:
            # HTTPError DOIT être catchée AVANT URLError (c'en est une sous-classe)
            if e.code == 404:
                # Aucune release publiée sur GitHub — on traite comme "à jour"
                self.after(0, lambda: self._show_up_to_date(show_feedback))
            elif e.code == 403:
                self.after(0, lambda: self._show_update_error("Limite GitHub atteinte, réessaie dans 1 min.", show_feedback))
            else:
                self.after(0, lambda: self._show_update_error(f"Erreur GitHub : HTTP {e.code}", show_feedback))
        except urllib.error.URLError:
            self.after(0, lambda: self._show_update_error("Pas de connexion internet", show_feedback))
        except Exception as e:
            self.after(0, lambda: self._show_update_error(str(e), show_feedback))

    def _show_update_available(self, latest_tag, release_name, asset):
        """Affiche le bouton MAJ en vert et propose le téléchargement."""
        self.btn_update.configure(
            text=f"⬆ v{latest_tag} dispo !",
            text_color="#2ecc71",
            fg_color=("#1a4a2e", "#1a4a2e"),
            state="normal"
        )
        # Popup de notification
        if messagebox.askyesno(
            "Mise à jour disponible",
            f"Une nouvelle version est disponible !\n\n"
            f"Version actuelle : v{APP_VERSION}\n"
            f"Nouvelle version : {release_name} (v{latest_tag})\n\n"
            f"Voulez-vous mettre à jour maintenant ?"
        ):
            self.perform_update(latest_tag, asset)

    def _show_up_to_date(self, show_feedback):
        """Remet le bouton en état neutre (version à jour)."""
        self.btn_update.configure(
            text=f"v{APP_VERSION} ✓",
            text_color="gray",
            fg_color="transparent",
            state="normal"
        )
        if show_feedback:
            messagebox.showinfo("Mise à jour", f"BiechyFinder v{APP_VERSION} est déjà à jour ! 🎉")

    def _show_update_error(self, error_msg, show_feedback):
        """En cas d'erreur réseau, remet le bouton en état normal."""
        self.btn_update.configure(
            text=f"v{APP_VERSION} ?",
            text_color="gray",
            fg_color="transparent",
            state="normal"
        )
        if show_feedback:
            messagebox.showwarning("Mise à jour", f"Impossible de vérifier les mises à jour.\n{error_msg}")

    def perform_update(self, latest_tag, asset):
        """Télécharge et installe la mise à jour depuis GitHub, puis redémarre."""
        if asset is None:
            import webbrowser
            webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")
            return

        download_url = asset["browser_download_url"]
        asset_name = asset["name"]

        # Détecter si on tourne en exe compilé (PyInstaller) ou en .py
        is_frozen = getattr(sys, 'frozen', False)
        if is_frozen:
            current_exe = sys.executable  # ex: C:\...\BiechyFinder.exe
            target_path = current_exe
        else:
            current_exe = os.path.abspath(__file__)
            target_path = current_exe

        tmp_path = target_path + ".tmp"
        backup_path = target_path + ".backup"

        # Popup de progression
        prog_win = tk.Toplevel(self)
        prog_win.title("Mise à jour en cours...")
        prog_win.geometry("420x140")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        prog_win.protocol("WM_DELETE_WINDOW", lambda: None)  # Bloquer fermeture

        tk.Label(prog_win, text=f"Téléchargement de BiechyFinder v{latest_tag}...",
                 font=("Segoe UI", 11)).pack(pady=(20, 10))

        import tkinter.ttk as ttk
        pb = ttk.Progressbar(prog_win, mode="indeterminate", length=360)
        pb.pack(padx=30)
        pb.start(10)

        status_lbl = tk.Label(prog_win, text="Connexion à GitHub...", font=("Segoe UI", 9), fg="gray")
        status_lbl.pack(pady=8)

        def do_download():
            try:
                # --- Téléchargement ---
                self.after(0, lambda: status_lbl.config(text=f"Téléchargement de {asset_name}..."))
                req = urllib.request.Request(download_url, headers={"User-Agent": f"BiechyFinder/{APP_VERSION}"})

                with urllib.request.urlopen(req, timeout=120) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    with open(tmp_path, "wb") as out:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            out.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = int(downloaded / total * 100)
                                self.after(0, lambda p=pct: status_lbl.config(
                                    text=f"Téléchargement... {p}% ({downloaded//1024//1024:.1f} MB)"))

                # --- Backup ---
                self.after(0, lambda: status_lbl.config(text="Sauvegarde de l'ancienne version..."))
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                shutil.copy2(target_path, backup_path)

                if is_frozen:
                    # Pour un .exe : on ne peut pas remplacer un exe en cours d'exécution sur Windows.
                    # On crée un .bat qui attend la fermeture de l'app, remplace le fichier, relance et se supprime.
                    self.after(0, lambda: status_lbl.config(text="Préparation du redémarrage..."))
                    bat_path = target_path + "_updater.bat"
                    bat_content = f"""@echo off
:: Attendre que BiechyFinder se ferme (3 secondes)
timeout /t 3 /nobreak >nul

:: Remplacer l'exe
move /y "{tmp_path}" "{target_path}"

:: Relancer l'application
start "" "{target_path}"

:: Supprimer ce script
del "%~f0"
"""
                    with open(bat_path, "w", encoding="utf-8") as f:
                        f.write(bat_content)

                    self.after(0, lambda: _finalize_exe(bat_path))
                else:
                    # Pour un .py : remplacement direct
                    self.after(0, lambda: status_lbl.config(text="Installation..."))
                    shutil.move(tmp_path, target_path)
                    self.after(0, lambda: _finalize_py())

            except Exception as e:
                # Nettoyage en cas d'erreur
                for p in [tmp_path]:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
                err = str(e)
                self.after(0, lambda: _on_error(err))

        def _finalize_exe(bat_path):
            prog_win.destroy()
            messagebox.showinfo(
                "Mise à jour prête",
                f"BiechyFinder v{latest_tag} est téléchargé !\n\n"
                f"L'application va se fermer et redémarrer automatiquement.\n"
                f"(Backup conservé : {os.path.basename(backup_path)})"
            )
            # Lancer le bat en arrière-plan puis quitter
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True
            )
            self.destroy()
            sys.exit(0)

        def _finalize_py():
            prog_win.destroy()
            messagebox.showinfo(
                "Mise à jour réussie",
                f"BiechyFinder a été mis à jour vers v{latest_tag} !\n\n"
                f"L'application va redémarrer.\n"
                f"(Backup : {os.path.basename(backup_path)})"
            )
            python = sys.executable
            self.destroy()
            subprocess.Popen([python, target_path])
            sys.exit(0)

        def _on_error(err_msg):
            try:
                prog_win.destroy()
            except Exception:
                pass
            messagebox.showerror(
                "Erreur de mise à jour",
                f"La mise à jour a échoué :\n{err_msg}\n\nL'ancienne version est conservée."
            )
            self.btn_update.configure(text=f"⬆ v{latest_tag} dispo !", state="normal")

        # Lancer le téléchargement dans un thread
        threading.Thread(target=do_download, daemon=True).start()

if __name__ == "__main__":
    app = BiechyFinder()
    app.mainloop()
