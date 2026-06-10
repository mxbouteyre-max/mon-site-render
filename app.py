"""
app.py — Serveur Flask pour Render
"""

import os
import sys
import glob
import json
import subprocess
from flask import Flask, jsonify, request, send_from_directory, send_file
import io

app = Flask(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "code_extraction")

# ── route principale ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ── liste des scripts ─────────────────────────────────────────────
@app.route("/api/scripts")
def api_scripts():
    if not os.path.isdir(SCRIPTS_DIR):
        os.makedirs(SCRIPTS_DIR)
    files = sorted([
        os.path.basename(p)
        for p in glob.glob(os.path.join(SCRIPTS_DIR, "*.py"))
    ])
    return jsonify({"scripts": files})

# ── exécuter un script ────────────────────────────────────────────
@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True)
    name = data.get("script", "")

    if ".." in name or "/" in name or "\\" in name:
        return jsonify({"ok": False, "error": "Nom invalide"}), 400

    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.isfile(path):
        return jsonify({"ok": False, "error": f"Script introuvable : {name}"}), 404

    # Snapshot des fichiers présents AVANT l'exécution
    before = set(glob.glob(os.path.join(SCRIPTS_DIR, "*")))

    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            cwd=SCRIPTS_DIR,
            timeout=300
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "script": name, "error": "Timeout (>5 min)"})
    except Exception as e:
        return jsonify({"ok": False, "script": name, "error": str(e)})

    # Fichiers créés APRÈS l'exécution
    after  = set(glob.glob(os.path.join(SCRIPTS_DIR, "*")))
    new_files = [
        os.path.basename(f) for f in (after - before)
        if not f.endswith(".py")
    ]

    return jsonify({
        "ok":         result.returncode == 0,
        "script":     name,
        "returncode": result.returncode,
        "stdout":     result.stdout,
        "stderr":     result.stderr,
        "new_files":  new_files,   # ← fichiers produits par le script
    })

# ── liste des fichiers produits (csv/xlsx/json…) ──────────────────
@app.route("/api/outputs")
def api_outputs():
    extensions = (".csv", ".xlsx", ".json", ".tsv", ".parquet")
    files = sorted([
        os.path.basename(f)
        for f in glob.glob(os.path.join(SCRIPTS_DIR, "*"))
        if os.path.basename(f).endswith(extensions)
    ])
    return jsonify({"files": files})

# ── télécharger un fichier produit ────────────────────────────────
@app.route("/api/download/<filename>")
def api_download(filename):
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Nom invalide"}), 400
    path = os.path.join(SCRIPTS_DIR, filename)
    if not os.path.isfile(path):
        return jsonify({"error": "Fichier introuvable"}), 404
    return send_file(path, as_attachment=True, download_name=filename)

# ── télécharger TOUS les fichiers produits fusionnés en un xlsx ───
@app.route("/api/download_all")
def api_download_all():
    try:
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        return jsonify({"error": "pandas/openpyxl non installés"}), 500

    extensions = (".csv", ".xlsx", ".tsv")
    files = sorted([
        f for f in glob.glob(os.path.join(SCRIPTS_DIR, "*"))
        if os.path.basename(f).endswith(extensions)
    ])

    if not files:
        return jsonify({"error": "Aucun fichier de données trouvé"}), 404

    wb = Workbook()
    wb.remove(wb.active)  # supprime la feuille vide par défaut

    header_font  = Font(bold=True, color="FFFFFF", size=11)
    header_fill  = PatternFill("solid", start_color="1F4E79")
    center_align = Alignment(horizontal="center", vertical="center")

    for filepath in files:
        sheet_name = os.path.basename(filepath)
        # Nom de feuille : sans extension, max 31 chars (limite Excel)
        for ext in (".csv", ".xlsx", ".tsv"):
            sheet_name = sheet_name.replace(ext, "")
        sheet_name = sheet_name[:31]

        try:
            if filepath.endswith(".csv"):
                df = pd.read_csv(filepath, encoding="utf-8-sig")
            elif filepath.endswith(".tsv"):
                df = pd.read_csv(filepath, sep="\t", encoding="utf-8-sig")
            else:
                df = pd.read_excel(filepath)
        except Exception as e:
            # Crée une feuille d'erreur plutôt que de planter
            ws = wb.create_sheet(sheet_name)
            ws["A1"] = f"Erreur de lecture : {e}"
            continue

        ws = wb.create_sheet(sheet_name)

        # En-têtes
        for col_idx, col_name in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=str(col_name))
            cell.font  = header_font
            cell.fill  = header_fill
            cell.alignment = center_align

        # Données
        for row_idx, row in enumerate(df.itertuples(index=False), 2):
            for col_idx, value in enumerate(row, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)

        # Largeur auto des colonnes
        for col_idx, col_name in enumerate(df.columns, 1):
            max_len = max(
                len(str(col_name)),
                df.iloc[:, col_idx - 1].astype(str).str.len().max() if len(df) else 0
            )
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 60)

        # Freeze la ligne d'en-tête
        ws.freeze_panes = "A2"

    if not wb.sheetnames:
        return jsonify({"error": "Aucune donnée lisible"}), 404

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"collecte_{date_str}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    app.run(host="0.0.0.0", port=port, debug=False)
