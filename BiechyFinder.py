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
APP_VERSION = "5.6"
GITHUB_REPO = "fenekee/BiechyFinder"

# --- Palette Dark Mode Moderne (Tech, Épurée & Performante) ---
THEME_BG = "#0b0f19"              # Fond principal très sombre et moderne
THEME_SIDEBAR = "#10141f"         # Sidebar contrastée
THEME_CARD = "#151b2b"            # Fond des cartes / conteneurs
THEME_CARD_HOVER = "#1c2438"      # Hover fluide des cartes
THEME_CARD_BORDER = "#1f273d"     # Bordure très fine et discrète
THEME_ACCENT = "#2563eb"          # Bleu électrique moderne
THEME_ACCENT_HOVER = "#1d4ed8"    # Hover bouton accent
THEME_ACCENT_LIGHT = "#3b82f6"    # Bleu clair pour badges et accents vifs
THEME_TEXT_PRIMARY = "#f8fafc"    # Texte blanc lumineux
THEME_TEXT_MUTED = "#94a3b8"      # Texte secondaire gris clair
THEME_TEXT_DIM = "#64748b"        # Texte discret / raccourcis

# Configuration globale CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DEFAULT_APP_DIR = os.path.join(os.path.expanduser("~"), "Documents", "BiechyFinder")
DEFAULT_DB_DIR = DEFAULT_APP_DIR
DEFAULT_DB = os.path.join(DEFAULT_APP_DIR, "biechyfinder.db")
CONFIG_FILE = os.path.join(DEFAULT_APP_DIR, "config.json")

class BiechyFinder(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"BiechyFinder v{APP_VERSION} - NAS Fast Search")
        
        # --- Géométrie adaptative pour écrans de PC portable & moniteurs ---
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        default_w = min(1180, max(880, int(screen_w * 0.88)))
        default_h = min(780, max(560, int(screen_h * 0.84)))
        pos_x = max(10, (screen_w - default_w) // 2)
        pos_y = max(10, (screen_h - default_h) // 2 - 20)
        self.geometry(f"{default_w}x{default_h}+{pos_x}+{pos_y}")
        self.minsize(820, 520)

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

        # Structures pour navigation tactile & clavier (laptop)
        self._result_rows_widgets = []
        self._selected_row_index = -1
        self._active_frame_name = "search"

        # Layout principal
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Barre Latérale (Navigation Moderne Dark Tech) ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=THEME_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=0)

        # Logo épuré avec badge de version
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=16, pady=(24, 28), sticky="w")
        
        logo_title_row = ctk.CTkFrame(logo_frame, fg_color="transparent")
        logo_title_row.pack(anchor="w")
        ctk.CTkLabel(logo_title_row, text="⚡ BiechyFinder", font=ctk.CTkFont(size=20, weight="bold"), text_color=THEME_TEXT_PRIMARY).pack(side="left")
        
        # Badge de version compact
        version_badge = ctk.CTkFrame(logo_frame, fg_color="#1e293b", corner_radius=6)
        version_badge.pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(version_badge, text=f" v{APP_VERSION} • FTS5 Search ", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(padx=4, pady=1)

        # Boutons de navigation (style pill moderne avec indicateur actif)
        self.nav_buttons = {}

        self.btn_search = self._create_nav_button("🔍  Recherche", "search", 1)
        self.btn_indexer = self._create_nav_button("⚡  Indexeur", "indexer", 2)
        self.btn_chat = self._create_nav_button("🤖  Assistant IA", "chat", 3)
        self.btn_settings = self._create_nav_button("⚙️  Paramètres", "settings", 4)

        # Status DB en bas de la sidebar
        db_status_card = ctk.CTkFrame(self.sidebar, fg_color="#151b2b", corner_radius=8, border_width=1, border_color=THEME_CARD_BORDER)
        db_status_card.grid(row=7, column=0, padx=12, pady=(0, 8), sticky="ew")

        status_inner = ctk.CTkFrame(db_status_card, fg_color="transparent")
        status_inner.pack(padx=10, pady=8, fill="x")

        self.db_status_indicator = ctk.CTkFrame(status_inner, height=8, width=8, corner_radius=4)
        self.db_status_indicator.pack(side="left", padx=(0, 8))

        self.db_status_label = ctk.CTkLabel(status_inner, text="DB Connectée", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME_TEXT_MUTED)
        self.db_status_label.pack(side="left", anchor="w")

        self.db_status_sub = ctk.CTkLabel(db_status_card, text="", font=ctk.CTkFont(size=10), text_color=THEME_TEXT_DIM)
        self.db_status_sub.pack(padx=10, pady=(0, 6), anchor="w")
        self.update_db_indicator()

        # Bouton mise à jour moderne
        self.btn_update = ctk.CTkButton(
            self.sidebar,
            text=f"v{APP_VERSION}  ✓",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#171e2e",
            text_color="#94a3b8",
            hover_color="#1f293d",
            corner_radius=8,
            height=30,
            command=self.check_for_update
        )
        self.btn_update.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 16))

        # --- Frames créées à la demande (Lazy initialization) ---
        self.search_frame = None
        self.indexer_frame = None
        self.chat_frame = None
        self.settings_frame = None
        self.results_scroll = None
        self.settings_scroll = None

        # Gestionnaire universel de défilement Pavé Tactile (Touchpad / Trackpad) & Souris
        self.bind_all("<MouseWheel>", self._on_universal_mousewheel, add="+")
        # Support Linux touchpad / scroll
        self.bind_all("<Button-4>", lambda e: self._on_universal_mousewheel_step(e, -1), add="+")
        self.bind_all("<Button-5>", lambda e: self._on_universal_mousewheel_step(e, 1), add="+")

        # Raccourcis clavier laptop (navigation rapide sans souris)
        self.bind_all("<Down>", self._on_key_nav, add="+")
        self.bind_all("<Up>", self._on_key_nav, add="+")
        self.bind_all("<Next>", self._on_key_nav, add="+")
        self.bind_all("<Prior>", self._on_key_nav, add="+")
        self.bind_all("<Control-f>", lambda e: self._focus_search_entry(), add="+")
        self.bind_all("<Control-F>", lambda e: self._focus_search_entry(), add="+")

        # Stats en thread pour ne pas bloquer le démarrage
        threading.Thread(target=self._update_stats_async, daemon=True).start()

        # Vérification MAJ au démarrage (silencieuse)
        threading.Thread(target=self._do_check_update, args=(False,), daemon=True).start()

        # Initialisation de l'index de recherche FTS5 en tâche de fond
        threading.Thread(target=self._init_fts_index, daemon=True).start()

        # Démarrage différé : la fenêtre s'affiche d'abord, puis on charge le contenu
        self.after(1, self._deferred_startup)

    def _deferred_startup(self):
        """Charge la vue recherche après que la fenêtre est visible."""
        self.select_frame("search")
        self.after(50, lambda: self.search(initial=True))
        self.after(200, self._check_first_launch_setup)

    def _get_desktop_dir(self):
        """Retourne le chemin du Bureau (prend en charge OneDrive)."""
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            onedrive_desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
            if os.path.exists(onedrive_desktop):
                return onedrive_desktop
        return desktop

    def create_desktop_shortcut(self, target_exe=None, working_dir=None):
        """Crée un raccourci vers BiechyFinder sur le Bureau Windows."""
        try:
            if not target_exe:
                target_exe = os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)
            if not working_dir:
                working_dir = os.path.dirname(target_exe)

            desktop = self._get_desktop_dir()
            os.makedirs(desktop, exist_ok=True)
            shortcut_path = os.path.join(desktop, "BiechyFinder.lnk")

            ps_script = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{shortcut_path}')
$s.TargetPath = '{target_exe}'
$s.WorkingDirectory = '{working_dir}'
$s.IconLocation = '{target_exe},0'
$s.Description = 'BiechyFinder - Recherche NAS ultra-rapide'
$s.Save()
"""
            flags = 0x08000000 if sys.platform == 'win32' else 0  # CREATE_NO_WINDOW
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], creationflags=flags, check=True)
            return True
        except Exception as e:
            print(f"Erreur création raccourci bureau: {e}")
            return False

    def _manual_create_shortcut(self):
        ok = self.create_desktop_shortcut()
        if ok:
            messagebox.showinfo("Raccourci Bureau", "Le raccourci BiechyFinder a été créé sur votre Bureau ! 📌")
        else:
            messagebox.showerror("Erreur", "Impossible de créer le raccourci sur le Bureau.")

    def _check_first_launch_setup(self):
        """Vérifie l'emplacement au premier lancement, propose d'installer dans Documents\\BiechyFinder
        et de créer le raccourci Bureau."""
        if getattr(sys, 'frozen', False):
            current_exe = os.path.abspath(sys.executable)
            target_dir = DEFAULT_APP_DIR
            target_exe = os.path.join(target_dir, "BiechyFinder.exe")
            current_dir = os.path.dirname(current_exe)

            # Si l'application tourne depuis un autre dossier que Documents\BiechyFinder
            if os.path.normcase(current_dir) != os.path.normcase(target_dir):
                prompt = (
                    "Bienvenue dans BiechyFinder ! ✨\n\n"
                    "Souhaitez-vous installer proprement l'application dans vos Documents :\n"
                    f"📁 {target_dir}\n\n"
                    "Et créer un raccourci 📌 sur votre Bureau ?"
                )
                if messagebox.askyesno("Installation BiechyFinder", prompt):
                    try:
                        os.makedirs(target_dir, exist_ok=True)
                        if os.path.normcase(current_exe) != os.path.normcase(target_exe):
                            shutil.copy2(current_exe, target_exe)

                        # Si une base existait à côté de l'exe d'origine, la transférer aussi
                        src_db = os.path.join(current_dir, "biechyfinder.db")
                        dest_db = os.path.join(target_dir, "biechyfinder.db")
                        if os.path.exists(src_db) and not os.path.exists(dest_db):
                            shutil.copy2(src_db, dest_db)

                        # Créer le raccourci Bureau
                        self.create_desktop_shortcut(target_exe, target_dir)

                        messagebox.showinfo(
                            "Installation réussie",
                            "BiechyFinder est maintenant bien rangé dans vos Documents !\n"
                            "Un raccourci a été ajouté sur votre Bureau 📌\n\n"
                            "L'application va s'ouvrir depuis son nouvel emplacement."
                        )
                        subprocess.Popen([target_exe], cwd=target_dir)
                        self.destroy()
                        sys.exit(0)
                        return
                    except Exception as e:
                        messagebox.showerror("Erreur d'installation", f"Impossible d'effectuer l'installation :\n{e}")

        # S'assurer que le raccourci Bureau existe
        desktop_shortcut = os.path.join(self._get_desktop_dir(), "BiechyFinder.lnk")
        if not os.path.exists(desktop_shortcut):
            self.create_desktop_shortcut()

        # Si aucune base de données n'existe, proposer de la télécharger
        if not os.path.exists(self.db_path):
            self.after(200, self._prompt_first_time_db_download)

    def _prompt_first_time_db_download(self):
        if not os.path.exists(self.db_path):
            if messagebox.askyesno(
                "Base de données manquante",
                "Aucune base de données n'a été trouvée sur cet ordinateur.\n\n"
                "Souhaitez-vous télécharger automatiquement la dernière base pré-indexée (~260 Mo) depuis GitHub ?"
            ):
                self.select_frame("settings")
                self.download_database_from_github()

    def load_config(self):
        # Migration si un config.json local existait dans le dossier d'exécution
        local_cfg = "config.json"
        if not os.path.exists(CONFIG_FILE) and os.path.exists(local_cfg):
            try:
                os.makedirs(DEFAULT_APP_DIR, exist_ok=True)
                shutil.copy2(local_cfg, CONFIG_FILE)
            except Exception:
                pass

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
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

    def _create_nav_button(self, text, name, row_idx):
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            text_color=THEME_TEXT_MUTED,
            hover_color=THEME_CARD_HOVER,
            anchor="w",
            corner_radius=8,
            height=42,
            command=lambda: self.select_frame(name)
        )
        btn.grid(row=row_idx, column=0, sticky="ew", padx=12, pady=3)
        self.nav_buttons[name] = btn
        return btn

    def select_frame(self, name):
        self._active_frame_name = name

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

        # Mise à jour moderne des styles de navigation
        for btn_name, btn in self.nav_buttons.items():
            if btn_name == name:
                btn.configure(fg_color=THEME_ACCENT, text_color="#ffffff", hover_color=THEME_ACCENT_HOVER)
            else:
                btn.configure(fg_color="transparent", text_color=THEME_TEXT_MUTED, hover_color=THEME_CARD_HOVER)

        # Masquer les autres vues
        if self.search_frame: self.search_frame.grid_forget()
        if self.indexer_frame: self.indexer_frame.grid_forget()
        if self.chat_frame: self.chat_frame.grid_forget()
        if self.settings_frame: self.settings_frame.grid_forget()

        # Afficher la vue sélectionnée avec padding fluide
        if name == "search":
            self.search_frame.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
            if hasattr(self, 'search_entry'):
                self.after(50, lambda: self.search_entry.focus_set())
        elif name == "indexer":
            self.indexer_frame.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
        elif name == "chat":
            self.chat_frame.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
        elif name == "settings":
            self.settings_frame.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)

    # --- Gestionnaire Universel Pavé Tactile (Touchpad / Trackpad) ---
    def _on_universal_mousewheel(self, event):
        """Gestionnaire de défilement fluide universel spécialement adapté aux
        pavés tactiles (Precision Touchpad Windows) et molettes de souris."""
        try:
            target = self.winfo_containing(event.x_root, event.y_root)
            canvas = None
            curr = target
            while curr is not None:
                if isinstance(curr, tk.Canvas):
                    canvas = curr
                    break
                if hasattr(curr, '_parent_canvas'):
                    canvas = curr._parent_canvas
                    break
                curr = getattr(curr, 'master', None)

            # Fallback vers le conteneur scrollable actif de la vue courante
            if canvas is None:
                if self._active_frame_name == "search" and self.results_scroll:
                    canvas = self.results_scroll._parent_canvas
                elif self._active_frame_name == "settings" and getattr(self, 'settings_scroll', None):
                    canvas = self.settings_scroll._parent_canvas
                elif self._active_frame_name == "chat" and getattr(self, 'chat_messages', None):
                    canvas = self.chat_messages._parent_canvas

            if canvas:
                delta = event.delta
                # Résolution du problème Windows Touchpad :
                # Les trackpads envoient de petits deltas (ex: 15-40). Un int(delta/120) renvoyait 0 !
                if abs(delta) < 120:
                    step = -1 if delta > 0 else 1
                else:
                    step = -int(delta / 35)

                canvas.yview_scroll(step, "units")
                return "break"
        except Exception:
            pass

    def _on_universal_mousewheel_step(self, event, step):
        try:
            target = self.winfo_containing(event.x_root, event.y_root)
            canvas = None
            curr = target
            while curr is not None:
                if isinstance(curr, tk.Canvas):
                    canvas = curr; break
                if hasattr(curr, '_parent_canvas'):
                    canvas = curr._parent_canvas; break
                curr = getattr(curr, 'master', None)
            if canvas is None and self._active_frame_name == "search" and self.results_scroll:
                canvas = self.results_scroll._parent_canvas
            if canvas:
                canvas.yview_scroll(step * 2, "units")
                return "break"
        except Exception:
            pass

    # --- Navigation au Clavier pour PC Portable (Sans Souris) ---
    def _focus_search_entry(self):
        if self._active_frame_name != "search":
            self.select_frame("search")
        if hasattr(self, 'search_entry'):
            self.search_entry.focus_set()
            self.search_entry.select_range(0, tk.END)

    def _on_key_nav(self, event):
        """Permet de faire défiler et sélectionner les résultats au clavier."""
        if self._active_frame_name != "search" or not self._result_rows_widgets:
            return

        key = event.keysym
        total = len(self._result_rows_widgets)

        if key == "Down":
            self._selected_row_index = min(total - 1, self._selected_row_index + 1)
            self._highlight_selected_row()
            return "break"
        elif key == "Up":
            self._selected_row_index = max(0, self._selected_row_index - 1)
            self._highlight_selected_row()
            return "break"
        elif key in ("Next", "Page_Down"):
            if self.results_scroll:
                self.results_scroll._parent_canvas.yview_scroll(6, "units")
                return "break"
        elif key in ("Prior", "Page_Up"):
            if self.results_scroll:
                self.results_scroll._parent_canvas.yview_scroll(-6, "units")
                return "break"

    def _highlight_selected_row(self):
        """Surligne le résultat actif et fait défiler la vue pour le garder sous les yeux."""
        if not self._result_rows_widgets:
            return
        for i, item in enumerate(self._result_rows_widgets):
            frame = item["frame"]
            if i == self._selected_row_index:
                frame.configure(fg_color="#1e3a8a", border_color="#3b82f6")  # Highlight bleu moderne
                # Auto-scroll vers cet élément
                try:
                    c = self.results_scroll._parent_canvas
                    c_h = c.winfo_height()
                    if c_h > 0:
                        y = frame.winfo_y()
                        total_h = self.results_scroll.winfo_height()
                        if total_h > 0:
                            c.yview_moveto(max(0.0, min(1.0, (y - 50) / total_h)))
                except Exception:
                    pass
            else:
                orig_bg = item["orig_bg"]
                frame.configure(fg_color=orig_bg, border_color=THEME_CARD_BORDER)

    def _show_toast(self, message):
        """Affiche une notification toast discrète et moderne en bas à droite (non bloquante)."""
        try:
            toast = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=8, border_width=1, border_color="#334155")
            lbl = ctk.CTkLabel(toast, text=f"✓  {message}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8")
            lbl.pack(padx=16, pady=8)
            toast.place(relx=0.97, rely=0.96, anchor="se")
            self.after(2000, lambda: toast.destroy() if toast.winfo_exists() else None)
        except Exception:
            pass

    def _copy_to_clipboard(self, text, label="Copié"):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self._show_toast(f"{label} copié dans le presse-papier !")
        except Exception:
            pass

    def _open_in_explorer(self, path):
        try:
            norm = os.path.normpath(path)
            if os.path.exists(norm):
                subprocess.run(['explorer', '/select,', norm])
            else:
                parent = os.path.dirname(norm)
                if os.path.exists(parent):
                    os.startfile(parent)
                else:
                    messagebox.showerror("Erreur", f"Chemin introuvable :\n{norm}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir l'explorateur : {e}")

    def _get_file_badge_info(self, name, is_dir):
        """Retourne (type_label, badge_color, icon) selon l'extension."""
        if is_dir:
            return "DIR", "#0369a1", "📁"
        ext = os.path.splitext(name)[1].lower().lstrip(".")
        if not ext:
            return "DOC", "#475569", "📄"
        if ext == "pdf":
            return "PDF", "#c2410c", "📕"
        elif ext in ("xlsx", "xls", "csv", "ods"):
            return ext.upper(), "#15803d", "📊"
        elif ext in ("docx", "doc", "odt", "txt", "rtf", "md"):
            return ext.upper()[:4], "#1d4ed8", "📝"
        elif ext in ("dwg", "dxf", "step", "stp", "cad"):
            return ext.upper()[:4], "#0e7490", "📐"
        elif ext in ("zip", "rar", "7z", "tar", "gz"):
            return ext.upper()[:4], "#b45309", "📦"
        elif ext in ("jpg", "jpeg", "png", "gif", "svg", "bmp", "webp"):
            return ext.upper()[:4], "#7e22ce", "🖼️"
        elif ext in ("mp4", "mkv", "avi", "mov", "mp3", "wav"):
            return ext.upper()[:4], "#a21caf", "🎬"
        elif ext in ("exe", "bat", "ps1", "sh", "msi"):
            return ext.upper()[:4], "#be123c", "⚙️"
        return ext.upper()[:4], "#334155", "📄"

    def _remap_drive_letter(self, path):
        """Remplace la lettre de lecteur dans un chemin si une lettre NAS est configurée."""
        if self.nas_drive_letter and path and len(path) >= 2 and path[1] == ':':
            return self.nas_drive_letter.upper() + path[1:]
        return path

    def update_db_indicator(self):
        exists = os.path.exists(self.db_path) if self.db_path else False
        color = "#10b981" if exists else "#ef4444"  # Vert émeraude ou rouge moderne
        self.db_status_indicator.configure(fg_color=color)
        if hasattr(self, 'db_status_label'):
            self.db_status_label.configure(
                text="DB Prête" if exists else "DB Manquante",
                text_color="#10b981" if exists else "#ef4444"
            )

    # --- SEARCH VIEW (REDESIGN MODERNE & OPTIMISÉ LAPTOP) ---
    def init_search_view(self):
        self.search_frame.grid_columnconfigure(0, weight=1)
        self.search_frame.grid_rowconfigure(2, weight=1)

        # Barre de recherche Spotlight moderne
        search_card = ctk.CTkFrame(self.search_frame, corner_radius=12, fg_color=THEME_CARD, border_width=1, border_color=THEME_CARD_BORDER)
        search_card.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 14))
        search_card.grid_columnconfigure(1, weight=1)

        # Icône loupe
        loupe_lbl = ctk.CTkLabel(search_card, text="🔍", font=ctk.CTkFont(size=18), text_color=THEME_TEXT_MUTED)
        loupe_lbl.grid(row=0, column=0, padx=(18, 8), pady=12)

        # Champ de saisie moderne
        self.search_entry = ctk.CTkEntry(
            search_card,
            placeholder_text="Rechercher par mots-clés, nom partiel, extension (ex: fact mars 2024, cisco 199)...",
            height=46,
            font=ctk.CTkFont(size=14),
            border_width=0,
            fg_color="transparent",
            text_color=THEME_TEXT_PRIMARY
        )
        self.search_entry.grid(row=0, column=1, padx=4, pady=10, sticky="ew")
        self.search_entry.bind("<Return>", lambda e: self.search())
        self.search_entry.bind("<KeyRelease>", self._on_search_keyrelease)

        # Bouton Effacer ✕
        self.btn_clear_search = ctk.CTkButton(
            search_card,
            text="✕",
            width=28,
            height=28,
            corner_radius=14,
            fg_color="transparent",
            hover_color="#1f293d",
            text_color=THEME_TEXT_DIM,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._clear_search_field
        )
        self.btn_clear_search.grid(row=0, column=2, padx=(2, 8), pady=10)

        # Bouton Rechercher tech
        self.search_btn = ctk.CTkButton(
            search_card,
            text="RECHERCHER  ↵",
            height=42,
            width=140,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME_ACCENT,
            hover_color=THEME_ACCENT_HOVER,
            corner_radius=8,
            command=self.search
        )
        self.search_btn.grid(row=0, column=3, padx=(4, 12), pady=10)

        # Barre d'actions & filtres rapides
        filter_bar = ctk.CTkFrame(self.search_frame, fg_color="transparent")
        filter_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        filter_bar.grid_columnconfigure(2, weight=1)

        self.var_dirs = tk.BooleanVar(value=True)
        self.check_dirs = ctk.CTkCheckBox(
            filter_bar,
            text="📁 Dossiers",
            variable=self.var_dirs,
            command=self.search,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME_TEXT_MUTED,
            fg_color=THEME_ACCENT,
            hover_color=THEME_ACCENT_HOVER,
            corner_radius=4
        )
        self.check_dirs.grid(row=0, column=0, padx=(2, 16), sticky="w")

        self.var_files = tk.BooleanVar(value=True)
        self.check_files = ctk.CTkCheckBox(
            filter_bar,
            text="📄 Fichiers",
            variable=self.var_files,
            command=self.search,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME_TEXT_MUTED,
            fg_color=THEME_ACCENT,
            hover_color=THEME_ACCENT_HOVER,
            corner_radius=4
        )
        self.check_files.grid(row=0, column=1, padx=(0, 16), sticky="w")

        # Indicateur de raccourci clavier laptop discret à droite
        laptop_hint = ctk.CTkLabel(
            filter_bar,
            text="Astuce portable : utilisez les flèches ↑ / ↓ pour naviguer dans les résultats sans souris • Entrée ↵ pour ouvrir",
            font=ctk.CTkFont(size=10),
            text_color=THEME_TEXT_DIM
        )
        laptop_hint.grid(row=0, column=2, sticky="e", padx=4)

        # Conteneur des résultats scrollable (moderne)
        self.results_scroll = ctk.CTkScrollableFrame(
            self.search_frame,
            corner_radius=10,
            fg_color=THEME_CARD,
            border_width=1,
            border_color=THEME_CARD_BORDER
        )
        self.results_scroll.grid(row=2, column=0, sticky="nsew")

    def _on_search_keyrelease(self, event):
        txt = self.search_entry.get()
        if txt:
            self.btn_clear_search.configure(text_color=THEME_TEXT_MUTED)
        else:
            self.btn_clear_search.configure(text_color="transparent")

    def _clear_search_field(self):
        self.search_entry.delete(0, tk.END)
        self.btn_clear_search.configure(text_color="transparent")
        self.search_entry.focus_set()
        self.search(initial=True)

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

        # Boutons de téléchargement de la base et raccourci bureau
        db_dl_row = ctk.CTkFrame(db_container, fg_color="transparent")
        db_dl_row.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 15), sticky="w")

        self.btn_download_db = ctk.CTkButton(
            db_dl_row,
            text="☁️ Télécharger la base depuis GitHub (~260 Mo)",
            fg_color="#1f538d",
            hover_color="#163e69",
            command=self.download_database_from_github
        )
        self.btn_download_db.pack(side="left", padx=(0, 10))

        self.btn_create_shortcut = ctk.CTkButton(
            db_dl_row,
            text="📌 Créer un raccourci Bureau",
            fg_color="#2e4053",
            hover_color="#1c2833",
            command=self._manual_create_shortcut
        )
        self.btn_create_shortcut.pack(side="left")

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

    def download_database_from_github(self):
        """Télécharge la dernière base de données biechyfinder.db depuis GitHub Releases."""
        dest_dir = os.path.dirname(self.db_path) if self.db_path else DEFAULT_DB_DIR
        if not dest_dir:
            dest_dir = DEFAULT_DB_DIR
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, "biechyfinder.db")

        if not messagebox.askyesno(
            "Téléchargement de la base",
            f"Voulez-vous télécharger la base de données pré-indexée (~260 Mo) depuis GitHub ?\n\n"
            f"Emplacement cible :\n{dest_path}\n\n"
            f"(Cela remplacera la base locale existante)."
        ):
            return

        prog_win = tk.Toplevel(self)
        prog_win.title("Téléchargement de la base...")
        prog_win.geometry("450x150")
        prog_win.resizable(False, False)
        prog_win.grab_set()
        prog_win.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(prog_win, text="Téléchargement de biechyfinder.db...", font=("Segoe UI", 11, "bold")).pack(pady=(15, 8))

        import tkinter.ttk as ttk
        pb = ttk.Progressbar(prog_win, mode="determinate", length=380, maximum=100)
        pb.pack(padx=25, pady=5)

        status_lbl = tk.Label(prog_win, text="Recherche de la dernière version sur GitHub...", font=("Segoe UI", 9), fg="gray")
        status_lbl.pack(pady=8)

        def worker():
            tmp_path = dest_path + ".downloading"
            try:
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

                self.after(0, lambda: status_lbl.config(text="Connexion au serveur..."))
                dl_req = urllib.request.Request(download_url, headers={"User-Agent": f"BiechyFinder/{APP_VERSION}"})
                with urllib.request.urlopen(dl_req, timeout=300) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    with open(tmp_path, "wb") as f_out:
                        while True:
                            chunk = resp.read(1024 * 512)
                            if not chunk:
                                break
                            f_out.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = (downloaded / total) * 100
                                mb_done = downloaded / (1024 * 1024)
                                mb_total = total / (1024 * 1024)
                                self.after(0, lambda p=pct, d=mb_done, t=mb_total: (
                                    pb.configure(value=p),
                                    status_lbl.config(text=f"{d:.1f} Mo / {t:.1f} Mo ({int(p)}%)")
                                ))

                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass
                os.replace(tmp_path, dest_path)

                self.db_path = dest_path
                self.save_config()

                def on_success():
                    prog_win.destroy()
                    if hasattr(self, 'db_path_entry'):
                        self.db_path_entry.delete(0, tk.END)
                        self.db_path_entry.insert(0, dest_path)
                    self.update_db_indicator()
                    self._update_stats_async()
                    threading.Thread(target=self._init_fts_index, daemon=True).start()
                    messagebox.showinfo("Succès", "La base de données a été téléchargée et configurée avec succès !\n\nVous pouvez maintenant effectuer vos recherches.")

                self.after(0, on_success)

            except Exception as e:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                def on_error(err_str=str(e)):
                    prog_win.destroy()
                    messagebox.showerror("Erreur de téléchargement", f"Impossible de télécharger la base de données :\n{err_str}")
                self.after(0, on_error)

        threading.Thread(target=worker, daemon=True).start()

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

    def _init_fts_index(self):
        """Initialise la table FTS5 pour la recherche plein texte instantanée et tolérante."""
        if not self.db_path or not os.path.exists(self.db_path):
            return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    name,
                    path,
                    content='files',
                    content_rowid='id',
                    tokenize="unicode61 remove_diacritics 2 separators '_-./\\\\'"
                )
            """)
            # Reconstruire si files contient des éléments mais files_fts est vide
            c.execute("SELECT rowid FROM files_fts LIMIT 1")
            has_fts = c.fetchone()
            c.execute("SELECT id FROM files LIMIT 1")
            has_files = c.fetchone()
            if has_files and not has_fts:
                c.execute("INSERT INTO files_fts(files_fts) VALUES('rebuild')")
                conn.commit()
            conn.close()
        except Exception:
            pass

    def _prepare_fts_query(self, query):
        """Transforme une saisie utilisateur en requête FTS5 robuste avec préfixes."""
        import re
        clean = re.sub(r'["\'\*\+\(\)\:\^\{\}\[\]~]', ' ', query).strip()
        words = [re.sub(r'[^a-zA-Z0-9\u00C0-\u017F]', '', w) for w in clean.split()]
        tokens = [f"{w}*" for w in words if w]
        return " ".join(tokens)

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
        t0 = time.perf_counter()
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if not query:
                sql = "SELECT name, path, is_dir, mod_time FROM files ORDER BY id DESC LIMIT 40"
                c.execute(sql)
                rows = c.fetchall()
            else:
                rows = []
                # 1. Recherche intelligente FTS5 (multi-mots, sans accents, fragments, ranking BM25)
                fts_q = self._prepare_fts_query(query)
                if fts_q:
                    try:
                        dir_filter = ""
                        if self.var_dirs.get() and not self.var_files.get():
                            dir_filter = " AND f.is_dir = 1"
                        elif self.var_files.get() and not self.var_dirs.get():
                            dir_filter = " AND f.is_dir = 0"

                        fts_sql = f"""
                            SELECT f.name, f.path, f.is_dir, f.mod_time
                            FROM files f
                            JOIN files_fts ON f.id = files_fts.rowid
                            WHERE files_fts MATCH ? {dir_filter}
                            ORDER BY bm25(files_fts, 10.0, 1.0), f.is_dir DESC, f.mod_time DESC
                            LIMIT 200
                        """
                        c.execute(fts_sql, (fts_q,))
                        rows = c.fetchall()
                    except Exception:
                        rows = []

                # 2. Fallback SQL flexible si FTS5 n'a rien retourné ou indisponible
                if not rows:
                    import re
                    words = [w for w in re.split(r'[\s_\-\.]+', query) if w]
                    if words:
                        conditions = []
                        params = []
                        for w in words:
                            conditions.append("(name LIKE ? OR path LIKE ?)")
                            params.extend([f"%{w}%", f"%{w}%"])
                        where_clause = " AND ".join(conditions)
                        if self.var_dirs.get() and not self.var_files.get():
                            where_clause += " AND is_dir = 1"
                        elif self.var_files.get() and not self.var_dirs.get():
                            where_clause += " AND is_dir = 0"
                        fallback_sql = f"""
                            SELECT name, path, is_dir, mod_time
                            FROM files
                            WHERE {where_clause}
                            ORDER BY is_dir DESC, name ASC
                            LIMIT 200
                        """
                        c.execute(fallback_sql, params)
                        rows = c.fetchall()

            conn.close()
            elapsed_ms = (time.perf_counter() - t0) * 1000

            # Retour au thread principal pour affichage moderne
            self.after(0, lambda: self._display_results(rows, initial, query, elapsed_ms))
        except Exception as e:
            self.after(0, lambda: self.loading_lbl.configure(text=f"Erreur: {str(e)}"))

    def _display_results(self, rows, initial, query="", elapsed_ms=0.0):
        if hasattr(self, 'loading_lbl') and self.loading_lbl.winfo_exists():
            self.loading_lbl.destroy()

        self._result_rows_widgets = []
        self._selected_row_index = -1

        if not rows:
            empty_card = ctk.CTkFrame(self.results_scroll, fg_color="transparent")
            empty_card.pack(fill="x", pady=40)
            ctk.CTkLabel(empty_card, text="🔍", font=ctk.CTkFont(size=32)).pack(pady=(0, 6))
            ctk.CTkLabel(empty_card, text="Aucun résultat trouvé", font=ctk.CTkFont(size=15, weight="bold"), text_color=THEME_TEXT_MUTED).pack()
            ctk.CTkLabel(empty_card, text="Vérifiez l'orthographe ou essayez d'autres mots-clés.", font=ctk.CTkFont(size=12), text_color=THEME_TEXT_DIM).pack(pady=(4, 0))
            return

        # Header moderne avec compteur et temps d'exécution
        header_frame = ctk.CTkFrame(self.results_scroll, fg_color="transparent")
        header_frame.pack(fill="x", padx=4, pady=(2, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        count_txt = f"{len(rows)} résultat{'s' if len(rows) > 1 else ''}"
        if len(rows) >= 200:
            count_txt += " (limité aux 200 premiers)"

        time_txt = f" • en {elapsed_ms:.1f} ms" if elapsed_ms > 0 else ""
        stat_badge = ctk.CTkLabel(
            header_frame,
            text=f"⚡ {count_txt}{time_txt}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        )
        stat_badge.pack(side="left", padx=4)

        if not initial and query:
            q_info = ctk.CTkLabel(
                header_frame,
                text=f"pour « {query} »",
                font=ctk.CTkFont(size=11),
                text_color=THEME_TEXT_DIM
            )
            q_info.pack(side="left", padx=4)

        for i, row in enumerate(rows):
            self.add_row(i, row)
            if i % 20 == 0: self.update_idletasks()

    def add_row(self, index, data):
        name, path, is_dir, mod_time = data
        display_path = self._remap_drive_letter(path)
        badge_text, badge_color, icon = self._get_file_badge_info(name, is_dir)

        # Alternance subtile de couleur de carte
        base_bg = "#131824" if index % 2 == 0 else "#161d2b"
        hover_bg = "#1e293b"

        row = ctk.CTkFrame(
            self.results_scroll,
            fg_color=base_bg,
            corner_radius=8,
            border_width=1,
            border_color=THEME_CARD_BORDER
        )
        row.pack(fill="x", pady=2, padx=4)
        row.grid_columnconfigure(1, weight=1)

        # 1. Badge type de fichier
        badge_frame = ctk.CTkFrame(row, fg_color=badge_color, corner_radius=6, width=44, height=28)
        badge_frame.grid(row=0, column=0, rowspan=2, padx=(10, 10), pady=8)
        badge_frame.pack_propagate(False)

        badge_lbl = ctk.CTkLabel(
            badge_frame,
            text=badge_text,
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#ffffff"
        )
        badge_lbl.pack(expand=True)

        # 2. Infos principales (Nom + Chemin)
        name_lbl = ctk.CTkLabel(
            row,
            text=name,
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME_TEXT_PRIMARY
        )
        name_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))

        path_lbl = ctk.CTkLabel(
            row,
            text=display_path,
            anchor="w",
            font=ctk.CTkFont(size=10),
            text_color=THEME_TEXT_DIM
        )
        path_lbl.grid(row=1, column=1, sticky="w", pady=(0, 6))

        # 3. Actions rapides au bout de la ligne
        actions_frame = ctk.CTkFrame(row, fg_color="transparent")
        actions_frame.grid(row=0, column=2, rowspan=2, padx=(10, 12), pady=6, sticky="e")

        btn_copy = ctk.CTkButton(
            actions_frame,
            text="📋 Copier",
            width=70,
            height=26,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color=THEME_TEXT_MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=lambda p=display_path: self._copy_to_clipboard(p, "Chemin")
        )
        btn_copy.pack(side="left", padx=(0, 6))

        btn_open_folder = ctk.CTkButton(
            actions_frame,
            text="📂 Dossier",
            width=75,
            height=26,
            corner_radius=6,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color=THEME_TEXT_MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
            command=lambda p=display_path: self._open_in_explorer(p)
        )
        btn_open_folder.pack(side="left")

        # Enregistrement pour navigation clavier
        row_record = {
            "index": index,
            "frame": row,
            "orig_bg": base_bg,
            "path": display_path,
            "name": name
        }
        self._result_rows_widgets.append(row_record)

        # Effet Hover dynamique
        def on_enter(e):
            if index != self._selected_row_index:
                row.configure(fg_color=hover_bg, border_color="#2c3854")

        def on_leave(e):
            if index != self._selected_row_index:
                row.configure(fg_color=base_bg, border_color=THEME_CARD_BORDER)

        # Événements et interaction (clic, double clic, menu contextuel)
        interactive_widgets = [row, badge_frame, badge_lbl, name_lbl, path_lbl]
        for w in interactive_widgets:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Double-Button-1>", lambda e, p=display_path: self.open_path(p))
            w.bind("<Button-1>", lambda e, idx=index: self._on_row_click(idx))
            w.bind("<Button-3>", lambda e, p=display_path, n=name: self._show_context_menu(e, p, n))
            # CRUCIAL POUR TOUCHPAD : transmission de la molette pour ne jamais bloquer le défilement
            w.bind("<MouseWheel>", self._on_universal_mousewheel, add="+")

    def _on_row_click(self, index):
        self._selected_row_index = index
        self._highlight_selected_row()

    def _show_context_menu(self, event, path, name):
        """Menu contextuel au clic droit sur un résultat."""
        try:
            menu = tk.Menu(
                self,
                tearoff=0,
                bg="#161c28",
                fg="#f1f5f9",
                activebackground=THEME_ACCENT,
                activeforeground="#ffffff",
                font=("Segoe UI", 10),
                bd=1
            )
            menu.add_command(label="⚡  Ouvrir", command=lambda: self.open_path(path))
            menu.add_command(label="📂  Afficher dans l'Explorateur Windows", command=lambda: self._open_in_explorer(path))
            menu.add_separator()
            menu.add_command(label="📋  Copier le chemin complet", command=lambda: self._copy_to_clipboard(path, "Chemin"))
            menu.add_command(label="🏷️  Copier le nom du fichier", command=lambda: self._copy_to_clipboard(name, "Nom"))
            menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass

    def open_path(self, path):
        try:
            path = os.path.normpath(path)
            if os.path.isdir(path):
                os.startfile(path)
            else:
                # Ouvrir directement le fichier avec l'application par défaut
                try:
                    os.startfile(path)
                except Exception:
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

            # Mise à jour de l'index de recherche plein texte FTS5
            try:
                self.index_status.configure(text="Optimisation de l'index de recherche...")
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
            except Exception:
                pass

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
                    target_dir = os.path.dirname(target_path)
                    target_name = os.path.basename(target_path)
                    old_pid = os.getpid()
                    bat_content = f"""@echo off
setlocal
:: Supprimer toutes les variables d'environnement PyInstaller 6+ et legacy
set _PYI_APPLICATION_HOME_DIR=
set _PYI_ARCHIVE_FILE=
set _PYI_PARENT_PROCESS_LEVEL=
set _MEIPASS2=
set _MEIPASS=

:: Attendre la terminaison effective du processus pere (PID {old_pid})
:WAIT_LOOP
tasklist /fi "PID eq {old_pid}" 2>nul | find "{old_pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto WAIT_LOOP
)

:: Petite pause de securite pour liberer le verrou du fichier
timeout /t 2 /nobreak >nul

:: Remplacer l'exe (avec reessais jusqu'a reussite)
:MOVE_LOOP
move /y "{tmp_path}" "{target_path}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto MOVE_LOOP
)

:: Se deplacer dans le repertoire cible et demarrer l'application proprement
cd /d "{target_dir}"
start "" "{target_name}"

:: Supprimer ce script updater
del "%~f0" >nul 2>&1
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
            # Nettoyer l'environnement pour ne pas transmettre de variable PyInstaller au sous-processus
            clean_env = os.environ.copy()
            for k in list(clean_env.keys()):
                if k.startswith('_PYI_') or k.startswith('_MEI'):
                    clean_env.pop(k, None)

            # Lancer le bat en arrière-plan puis quitter
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                env=clean_env,
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
