import os
import uuid
import subprocess
import json
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Cambia in produzione

# Cartelle
UPLOAD_FOLDER = 'uploads'
COMPRESSED_FOLDER = 'compressed'
TEMP_FOLDER = 'temp'
PROGRESS_FILE = os.path.join(TEMP_FOLDER, 'progress.json')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['COMPRESSED_FOLDER'] = COMPRESSED_FOLDER

for folder in [UPLOAD_FOLDER, COMPRESSED_FOLDER, TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Processo ffmpeg corrente
current_process = None


def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in {'mp4', 'mov', 'avi', 'mkv', 'webm'}


@app.route('/')
def index():
    """Pagina principale"""
    return render_template('index.html')


@app.route('/compress', methods=['POST'])
def compress():
    """Avvia la compressione video"""
    global current_process

    if 'file' not in request.files:
        return jsonify({"error": "Nessun file selezionato"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nessun file selezionato"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Formato non supportato"}), 400

    # Parametri
    crf = request.form.get('crf', '28')
    width = request.form.get('width', '1280')
    height = request.form.get('height', '-1')
    start_time = request.form.get('start_time', '0')
    duration = request.form.get('duration', '')
    custom_width = request.form.get('custom_width', '')
    custom_height = request.form.get('custom_height', '')

    if custom_width:
        width = custom_width
        height = custom_height if custom_height else '-1'

    # Salvataggio file
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(input_path)

    name, ext = os.path.splitext(file.filename)
    output_filename = f"{name}_compressed{ext}"
    output_path = os.path.join(app.config['COMPRESSED_FOLDER'], output_filename)

    # Filtro scale
    if width != 'original':
        scale_filter = f"scale={width}:{height}:flags=lanczos"
    else:
        scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

    # Comando ffmpeg
    cmd = ['ffmpeg', '-i', input_path]

    if start_time != '0':
        cmd += ['-ss', start_time]
    if duration:
        cmd += ['-t', duration]

    cmd += [
        '-vf', scale_filter,
        '-c:v', 'libx264',
        '-crf', crf,
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        '-y',
        output_path
    ]

    # Stato iniziale
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({"progress": 0, "status": "in corso"}, f)

    try:
        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        duration_sec = 0
        while True:
            line = current_process.stdout.readline()
            if not line and current_process.poll() is not None:
                break

            if "Duration: " in line and duration_sec == 0:
                try:
                    time_str = line.split("Duration: ")[1].split(",")[0]
                    h, m, s = time_str.split(":")
                    duration_sec = int(h) * 3600 + int(m) * 60 + float(s)
                except:
                    pass

            if "time=" in line and duration_sec > 0:
                try:
                    current_time = line.split("time=")[1].split(" ")[0]
                    h, m, s = current_time.split(":")
                    elapsed = int(h) * 3600 + int(m) * 60 + float(s)
                    progress = min(int((elapsed / duration_sec) * 100), 100)
                    with open(PROGRESS_FILE, 'w') as f:
                        json.dump({"progress": progress, "status": "in corso"}, f)
                except:
                    pass

        current_process.wait()
        if current_process.returncode == 0:
            with open(PROGRESS_FILE, 'w') as f:
                json.dump({"progress": 100, "status": "completato", "file": output_filename}, f)
        else:
            with open(PROGRESS_FILE, 'w') as f:
                json.dump({"progress": 0, "status": "fallito", "error": "FFmpeg errore"}, f)

    except Exception as e:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({"progress": 0, "status": "fallito", "error": str(e)}, f)
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

    return jsonify({"status": "started"})


@app.route('/progress')
def progress():
    """Restituisce lo stato attuale della compressione"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        except:
            pass
    return jsonify({"progress": 0, "status": "idle"})


@app.route('/cancel', methods=['POST'])
def cancel():
    """Interrompe il processo ffmpeg"""
    global current_process
    if current_process and current_process.poll() is None:
        current_process.terminate()
        try:
            current_process.wait(timeout=3)
        except:
            current_process.kill()
        current_process = None
    return jsonify({"status": "canceled"})


@app.route('/download/<filename>')
def download(filename):
    """Scarica il file compresso"""
    path = os.path.join(app.config['COMPRESSED_FOLDER'], filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File non trovato", 404


@app.errorhandler(405)
def method_not_allowed(e):
    """Reindirizza se qualcuno prova ad accedere a /compress con GET"""
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

