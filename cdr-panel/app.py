#!/usr/bin/env python3
"""
Panel de Registro de Llamadas (CDR) - Callcenter Demo
Lee el Master.csv generado por el módulo cdr_csv de Asterisk
y expone una API + interfaz web para listar y reproducir grabaciones.
Formato estándar de Master.csv (Asterisk, cdr_csv por defecto):
accountcode, src, dst, dcontext, clid, channel, dstchannel,
lastapp, lastdata, start, answer, end, duration, billsec,
disposition, amaflags, uniqueid, userfield
"""
import csv
import os
import re
import subprocess
from datetime import datetime
from flask import Flask, jsonify, render_template, send_from_directory, abort, request

app = Flask(__name__)
CDR_DIR = os.environ.get("CDR_DIR", "/data/cdr")
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/data/grabaciones")
MASTER_CSV = os.path.join(CDR_DIR, "Master.csv")
CDR_FIELDS = [
    "accountcode", "src", "dst", "dcontext", "clid", "channel",
    "dstchannel", "lastapp", "lastdata", "start", "answer", "end",
    "duration", "billsec", "disposition", "amaflags", "uniqueid", "userfield",
]

def parse_master_csv():
    rows = []
    if not os.path.exists(MASTER_CSV):
        return rows
    with open(MASTER_CSV, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for raw in reader:
            if not raw or len(raw) < len(CDR_FIELDS):
                continue
            record = dict(zip(CDR_FIELDS, raw))
            record["recording_file"] = find_recording_for(record)
            rows.append(record)
    rows.reverse()
    return rows

def find_recording_for(record):
    if not os.path.isdir(RECORDINGS_DIR):
        return None
    start_raw = record.get("start", "")
    try:
        dt = datetime.strptime(start_raw, "%Y-%m-%d %H:%M:%S")
        stamp = dt.strftime("%Y%m%d-%H%M")
    except ValueError:
        return None
    try:
        candidates = os.listdir(RECORDINGS_DIR)
    except OSError:
        return None
    for ext_field in ("dst", "src"):
        ext = record.get(ext_field, "")
        if not ext:
            continue
        for fname in candidates:
            if fname.startswith(f"{ext}-{stamp}"):
                return fname
    return None

def compute_stats(rows):
    total = len(rows)
    answered = sum(1 for r in rows if r.get("disposition") == "ANSWERED")
    no_answer = sum(1 for r in rows if r.get("disposition") == "NO ANSWER")
    failed = sum(1 for r in rows if r.get("disposition") in ("FAILED", "BUSY"))
    total_billsec = sum(int(r.get("billsec") or 0) for r in rows)
    answered_rows = [r for r in rows if r.get("disposition") == "ANSWERED"]
    answered_billsec = sum(int(r.get("billsec") or 0) for r in answered_rows)
    avg_billsec = round(answered_billsec / len(answered_rows)) if answered_rows else 0
    return {
        "total": total,
        "answered": answered,
        "no_answer": no_answer,
        "failed": failed,
        "total_billsec": total_billsec,
        "avg_billsec": avg_billsec,
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/cdr")
def api_cdr():
    rows = parse_master_csv()
    src_filter = request.args.get("src", "").strip()
    date_filter = request.args.get("date", "").strip()
    disposition_filter = request.args.get("disposition", "").strip()
    if src_filter:
        rows = [r for r in rows if src_filter in r.get("src", "") or src_filter in r.get("dst", "")]
    if date_filter:
        rows = [r for r in rows if r.get("start", "").startswith(date_filter)]
    if disposition_filter:
        rows = [r for r in rows if r.get("disposition") == disposition_filter]
    return jsonify({
        "stats": compute_stats(rows),
        "calls": rows,
    })

@app.route("/api/endpoints")
def api_endpoints():
    """Devuelve las extensiones registradas en Asterisk en tiempo real."""
    try:
        result = subprocess.run(
            ["docker", "exec", "callcenter-asterisk", "asterisk", "-rx", "pjsip show endpoints"],
            capture_output=True, text=True, timeout=10
        )
        endpoints = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Endpoint:") and "Endpoint/CID" not in line:
                parts = line.split()
                if len(parts) >= 3:
                    ext = parts[1].strip()
                    status = parts[2].strip()
                    endpoints.append({"extension": ext, "status": status})
        return jsonify({"endpoints": endpoints, "total": len(endpoints)})
    except Exception as e:
        return jsonify({"endpoints": [], "total": 0, "error": str(e)}), 500

@app.route("/recordings/<path:filename>")
def serve_recording(filename):
    safe_path = os.path.normpath(os.path.join(RECORDINGS_DIR, filename))
    if not safe_path.startswith(os.path.normpath(RECORDINGS_DIR)):
        abort(403)
    if not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(RECORDINGS_DIR, filename, as_attachment=False)

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "master_csv_found": os.path.exists(MASTER_CSV),
        "recordings_dir_found": os.path.isdir(RECORDINGS_DIR),
    })

@app.route("/api/provision", methods=["POST"])
def provision_extension():
    data = request.get_json(force=True, silent=True) or {}
    extension = str(data.get("extension", "")).strip()
    password = str(data.get("password", "")).strip()
    if not extension or not password:
        return jsonify({"status": "error", "message": "extension y password son requeridos"}), 400
    if not re.match(r'^\d{3,6}$', extension):
        return jsonify({"status": "error", "message": "extension invalida"}), 400
    if not re.match(r'^[a-zA-Z0-9_\-\.]{4,32}$', password):
        return jsonify({"status": "error", "message": "password invalida"}), 400

    pjsip_path = "/workspace/asterisk/config/pjsip.conf"
    extensions_path = "/workspace/asterisk/config/extensions.conf"

    try:
        with open(pjsip_path, "r") as f:
            if f"[{extension}]" in f.read():
                return jsonify({"status": "error", "message": f"Extension {extension} ya existe"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error leyendo pjsip.conf: {e}"}), 500

    pjsip_block = f"""
; ===== Extensión {extension} =====
[{extension}]
type=endpoint
context=internal
disallow=all
allow=ulaw
allow=alaw
auth={extension}-auth
aors={extension}
[{extension}-auth]
type=auth
auth_type=userpass
username={extension}
password={password}
[{extension}]
type=aor
max_contacts=1
"""
    exten_block = f"""exten => {extension},1,MixMonitor({extension}-${{STRFTIME(${{EPOCH}},,%Y%m%d-%H%M%S)}}.wav)
 same => n,Dial(PJSIP/{extension},20)
 same => n,Hangup()
"""
    try:
        with open(pjsip_path, "a") as f:
            f.write(pjsip_block)
        with open(extensions_path, "a") as f:
            f.write(exten_block)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error escribiendo config: {e}"}), 500

    try:
        subprocess.run(
            ["docker", "exec", "callcenter-asterisk", "asterisk", "-rx", "module reload res_pjsip.so"],
            capture_output=True, text=True, timeout=15
        )
        subprocess.run(
            ["docker", "exec", "callcenter-asterisk", "asterisk", "-rx", "dialplan reload"],
            capture_output=True, text=True, timeout=15
        )
    except Exception as e:
        return jsonify({"status": "warning", "extension": extension,
                        "message": f"Extension escrita pero no se pudo recargar Asterisk: {e}"}), 207

    return jsonify({
        "status": "ok",
        "extension": extension,
        "message": f"Extension {extension} aprovisionada y Asterisk recargado correctamente"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
