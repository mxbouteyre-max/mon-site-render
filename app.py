"""
app.py — Serveur Flask pour Render

Logique :
  - Lister les scripts disponibles (code_extraction/*.py)
  - Lancer un ou plusieurs scripts sélectionnés (en arrière-plan)
  - Suivre l'état des jobs (running / finished / failed)
  - Une fois terminés, fusionner tous les résultats (csv/xlsx/tsv)
    produits dans code_extraction/ en un seul fichier .xlsx téléchargeable
"""

import os, sys, glob, io, subprocess, threading
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory, send_file

app = Flask(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "code_extraction")
JOBS = {}
JOBS_LOCK = threading.Lock()
MAX_RUNNING = 2

DATA_EXTENSIONS = (".csv", ".xlsx", ".tsv")


# ── lecture CSV robuste ───────────────────────────────────────────
def _read_csv_robust(filepath):
    """Essaie plusieurs séparateurs et encodages jusqu'à trouver le bon."""
    import pandas as pd

    encodings  = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    separators = [None, ";", ",", "\t", "|"]  # None = sniff automatique

    last_error = None
    for enc in encodings:
        for sep in separators:
            try:
                kwargs = dict(encoding=enc, on_bad_lines="skip")
                if sep is None:
                    kwargs["sep"] = None
                    kwargs["engine"] = "python"
                else:
                    kwargs["sep"] = sep
                df = pd.read_csv(filepath, **kwargs)
                if len(df.columns) > 1 or sep is None:
                    return df
            except Exception as e:
                last_error = e
                continue

    raise ValueError(f"Impossible de lire le CSV ({last_error})")


# ── exécution d'un script ─────────────────────────────────────────
def execute_script(script_name, script_path):
    with JOBS_LOCK:
        JOBS[script_name] = {
            "status": "running",
            "start_time": datetime.now().isoformat()
        }

    try:
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=SCRIPTS_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        with JOBS_LOCK:
            JOBS[script_name]["pid"] = process.pid

        stdout, stderr = process.communicate()

        with JOBS_LOCK:
            JOBS[script_name].update({
                "status": "finished" if process.returncode == 0 else "failed",
                "returncode": process.returncode,
                "stdout": stdout[-10000:] if stdout else "",
                "stderr": stderr[-10000:] if stderr else "",
                "end_time": datetime.now().isoformat()
            })

    except Exception as e:
        with JOBS_LOCK:
            JOBS[script_name] = {
                "status": "failed",
                "error": str(e),
                "end_time": datetime.now().isoformat()
            }


# ── pages statiques ───────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/information.html")
def information():
    return send_from_directory(".", "information.html")

@app.route("/excel-merger.html")
def excel_merger():
    return send_from_directory(".", "excel-merger.html")

@app.route("/fusion")
def fusion():
    return send_from_directory(".", "fusion-colonnes.html")


# ── liste des scripts disponibles ─────────────────────────────────
@app.route("/api/scripts")
def api_scripts():
    if not os.path.isdir(SCRIPTS_DIR):
        os.makedirs(SCRIPTS_DIR)
    files = sorted([
        os.path.basename(p)
        for p in glob.glob(os.path.join(SCRIPTS_DIR, "*.py"))
    ])
    return jsonify({"scripts": files})


# ── lancer un ou plusieurs scripts ────────────────────────────────
@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(force=True)

    # accepte soit "script": "x.py" soit "scripts": ["x.py", "y.py"]
    names = data.get("scripts")
    if names is None:
        single = data.get("script", "")
        names = [single] if single else []

    if not names:
        return jsonify({"ok": False, "error": "Aucun script sélectionné"}), 400

    results = []

    for name in names:
        if ".." in name or "/" in name or "\\" in name:
            results.append({"script": name, "ok": False, "error": "Nom invalide"})
            continue

        path = os.path.join(SCRIPTS_DIR, name)

        if not os.path.isfile(path):
            results.append({"script": name, "ok": False, "error": f"Script introuvable : {name}"})
            continue

        with JOBS_LOCK:
            already_running = JOBS.get(name, {}).get("status") == "running"
            running_count = sum(1 for job in JOBS.values() if job.get("status") == "running")

        if already_running:
            results.append({"script": name, "ok": False, "error": "Script déjà en cours"})
            continue

        if running_count >= MAX_RUNNING:
            results.append({"script": name, "ok": False, "error": f"Maximum {MAX_RUNNING} scripts simultanés"})
            continue

        thread = threading.Thread(
            target=execute_script,
            args=(name, path),
            daemon=True
        )
        thread.start()

        results.append({"script": name, "ok": True, "message": f"{name} lancé en arrière-plan"})

    return jsonify({"ok": True, "results": results})


# ── état des jobs ──────────────────────────────────────────────────
@app.route("/api/jobs")
def api_jobs():
    with JOBS_LOCK:
        return jsonify(JOBS)


# ── liste des fichiers de résultats produits ───────────────────────
@app.route("/api/outputs")
def api_outputs():
    files = sorted([
        os.path.basename(f)
        for f in glob.glob(os.path.join(SCRIPTS_DIR, "*"))
        if os.path.basename(f).endswith(DATA_EXTENSIONS)
    ])
    return jsonify({"files": files})


# ── télécharger un fichier individuel ──────────────────────────────
@app.route("/api/download/<filename>")
def api_download(filename):
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Nom invalide"}), 400
    path = os.path.join(SCRIPTS_DIR, filename)
    if not os.path.isfile(path):
        return jsonify({"error": "Fichier introuvable"}), 404
    return send_file(path, as_attachment=True, download_name=filename)


# ── télécharger tous les résultats fusionnés en un xlsx ─────────────
@app.route("/api/download_all")
def api_download_all():
    try:
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        return jsonify({"error": "pandas/openpyxl non installés"}), 500

    files = sorted([
        f for f in glob.glob(os.path.join(SCRIPTS_DIR, "*"))
        if os.path.basename(f).endswith(DATA_EXTENSIONS)
    ])

    if not files:
        return jsonify({"error": "Aucun fichier de données trouvé"}), 404

    wb = Workbook()
    wb.remove(wb.active)
    header_font  = Font(bold=True, color="FFFFFF", size=11)
    header_fill  = PatternFill("solid", start_color="1F4E79")
    center_align = Alignment(horizontal="center", vertical="center")

    for filepath in files:
        sheet_name = os.path.basename(filepath)
        for ext in DATA_EXTENSIONS:
            sheet_name = sheet_name.replace(ext, "")
        sheet_name = sheet_name[:31]

        try:
            if filepath.endswith(".xlsx"):
                df = pd.read_excel(filepath)
            elif filepath.endswith(".tsv"):
                df = pd.read_csv(filepath, sep="\t", encoding="utf-8-sig", on_bad_lines="skip")
            else:
                df = _read_csv_robust(filepath)
        except Exception as e:
            ws = wb.create_sheet(sheet_name)
            ws["A1"] = f"Erreur de lecture : {e}"
            continue

        ws = wb.create_sheet(sheet_name)

        for col_idx, col_name in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=str(col_name))
            cell.font      = header_font
            cell.fill      = header_fill
            cell.alignment = center_align

        for row_idx, row in enumerate(df.itertuples(index=False), 2):
            for col_idx, value in enumerate(row, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)

        for col_idx, col_name in enumerate(df.columns, 1):
            max_len = max(
                len(str(col_name)),
                df.iloc[:, col_idx - 1].astype(str).str.len().max() if len(df) else 0
            )
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 60)

        ws.freeze_panes = "A2"

    if not wb.sheetnames:
        return jsonify({"error": "Aucune donnée lisible"}), 404

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

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