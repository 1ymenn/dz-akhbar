import os
import subprocess
import sys
from flask import Flask, send_from_directory, jsonify

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE, static_url_path='')

@app.route('/')
def index():
    return send_from_directory(BASE, 'index.html')

@app.route('/refresh')
def refresh():
    """Fetch fresh news and regenerate index.html"""
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(BASE, 'update_news.py')],
            cwd=BASE, capture_output=True, text=True, timeout=120
        )
        output = result.stdout + result.stderr
        lines = [l for l in output.split('\n') if l.strip()]
        return jsonify({"status": "ok", "log": lines[-5:]})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(BASE, filename)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"NewsHub server running at http://localhost:{port}")
    print("Open in your browser: http://localhost:" + str(port))
    app.run(host='0.0.0.0', port=port, debug=False)
