"""
app.py — Serveur Flask pour Render
"""

import os
import sys
import glob
import json
import subprocess
import threading
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "code_extraction")

# ── sécurité basique : token optionnel ────────────────────────────
SECRET = os.environ.get("RUNNER_SECRET", "")   # vide = pas de protection

def check_auth():
    if not SECRET:
        return True
    token = request.headers.get("X-Token", "") or request.args.get("token", "")
    return token == SECRET

# ── routes statiques ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ── API ───────────────────────────────────────────────────────────
@app.route("/api/scripts")
def api_scripts():
    if not os.path.isdir(SCRIPTS_DIR):
        os.makedirs(SCRIPTS_DIR)
    files = sorted([
        os.path.basename(p)
        for p in glob.glob(os.path.join(SCRIPTS_DIR, "*.py"))
    ])
    return jsonify({"scripts": files})

@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True)
    name = data.get("script", "")

    # sécurité path traversal
    if ".." in name or "/" in name or "\\" in name:
        return jsonify({"ok": False, "error": "Nom invalide"}), 400

    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.isfile(path):
        return jsonify({"ok": False, "error": f"Script introuvable : {name}"}), 404

    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            cwd=SCRIPTS_DIR,
            timeout=300
        )
        return jsonify({
            "ok":         result.returncode == 0,
            "script":     name,
            "returncode": result.returncode,
            "stdout":     result.stdout,
            "stderr":     result.stderr,
        })
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "script": name, "error": "Timeout (>5 min)"})
    except Exception as e:
        return jsonify({"ok": False, "script": name, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    app.run(host="0.0.0.0", port=port, debug=False)
