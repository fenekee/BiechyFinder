# 🔍 BiechyFinder v4.0 - NAS Search & Indexer

Application de recherche et d'indexation de fichiers NAS avec assistant IA intégré (Mistral AI).

## ✨ Fonctionnalités

- **Recherche rapide** — Recherche instantanée par nom, extension ou dossier dans ta base indexée
- **Indexeur NAS** — Scanne et indexe tes dossiers réseau (local ou via SSH)
- **Chat IA** — Décris ce que tu cherches en langage naturel, l'IA génère la requête SQL pour toi
- **Résumé IA du NAS** — Génère un résumé intelligent du contenu de ton stockage

## 📥 Installation

### Option 1 : Télécharger le .exe (Windows)
Télécharge la dernière version depuis l'onglet [**Releases**](../../releases) — aucune installation requise.

### Option 2 : Depuis le code source

```bash
# Cloner le dépôt
git clone https://github.com/ton-user/BiechyFinder.git
cd BiechyFinder

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python BiechyFinder.py
```

## ⚙️ Configuration

Au premier lancement, va dans **⚙️ Paramètres** pour configurer :

1. **Base de données** — Choisis l'emplacement du fichier SQLite (créé automatiquement à l'indexation)
2. **Clé API Mistral** — Nécessaire pour le Chat IA et le résumé. Obtiens ta clé gratuite sur [console.mistral.ai](https://console.mistral.ai/)
3. **Modèle Mistral** — `mistral-small-latest` (rapide) ou `mistral-large-latest` (plus précis)

> ⚠️ La configuration est sauvegardée localement dans `config.json` (non inclus dans le dépôt pour protéger ta clé API).

## 🔧 Compiler le .exe soi-même

```bash
pip install pyinstaller
python -m PyInstaller BiechyFinder.spec --noconfirm
```

Le .exe sera généré dans le dossier `dist/`.

## 📦 Dépendances

- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — Interface graphique moderne
- [httpx](https://www.python-httpx.org/) — Appels API Mistral
- [paramiko](https://www.paramiko.org/) — Connexion SSH au NAS
