from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import yt_dlp
import json
import threading
import uuid
import hashlib
import secrets
from pathlib import Path
from functools import wraps

app = Flask(__name__)
CORS(app, supports_credentials=True)

DOWNLOAD_DIR = Path("downloads")
CONFIG_FILE  = Path("config/settings.json")
COOKIE_FILE  = Path("config/youtube_cookies.txt")
DOWNLOAD_DIR.mkdir(exist_ok=True)
Path("config").mkdir(exist_ok=True)

tasks = {}

SECRET_KEY_FILE = Path("config/secret.key")
if SECRET_KEY_FILE.exists():
    app.secret_key = SECRET_KEY_FILE.read_text().strip()
else:
    app.secret_key = secrets.token_hex(32)
    SECRET_KEY_FILE.write_text(app.secret_key)

DEFAULT_SETTINGS = {
    "site_title": "YTVD",
    "logo_type": "gradient_text",
    "logo_url": "",
    "logo_gradient": "linear-gradient(135deg, #f5a623 0%, #f7c26b 100%)",
    "logo_text": "YTVD",
    "links": [],
    "ads": {"header": "", "footer": "", "sidebar_left": "", "sidebar_right": ""},
    "use_cookies": False,
    "admin_password_hash": hashlib.sha256(b"admin123").hexdigest()
}

def load_settings():
    if CONFIG_FILE.exists():
        try:
            s = json.loads(CONFIG_FILE.read_text())
            for k, v in DEFAULT_SETTINGS.items():
                if k not in s:
                    s[k] = v
            return s
        except:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(data):
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/")
@app.route("/admin")
def index():
    return send_from_directory("templates", "index.html")

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.json or {}
    pw   = data.get("password", "")
    settings = load_settings()
    if hash_pw(pw) == settings.get("admin_password_hash", ""):
        session["admin_logged_in"] = True
        session.permanent = True
        return jsonify({"ok": True})
    return jsonify({"error": "Wrong password"}), 401

@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/auth/check")
def api_auth_check():
    return jsonify({"ok": bool(session.get("admin_logged_in"))})

@app.route("/api/auth/change_password", methods=["POST"])
@login_required
def api_change_password():
    data   = request.json or {}
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
    if not new_pw or len(new_pw) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    settings = load_settings()
    if hash_pw(old_pw) != settings.get("admin_password_hash", ""):
        return jsonify({"error": "Current password is wrong"}), 401
    settings["admin_password_hash"] = hash_pw(new_pw)
    save_settings(settings)
    return jsonify({"ok": True})

@app.route("/api/info", methods=["POST"])
def get_info():
    data = request.json or {}
    url  = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400
    settings = load_settings()
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    if settings.get("use_cookies") and COOKIE_FILE.exists():
        ydl_opts["cookiefile"] = str(COOKIE_FILE)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats, seen = [], set()
            for f in (info.get("formats") or []):
                ext    = f.get("ext", "")
                res    = f.get("resolution") or (f"{f.get('height')}p" if f.get("height") else "audio")
                vcodec = f.get("vcodec", "none")
                acodec = f.get("acodec", "none")
                fsize  = f.get("filesize") or f.get("filesize_approx") or 0
                key    = f"{res}-{ext}-{vcodec[:3]}-{acodec[:3]}"
                if key in seen: continue
                seen.add(key)
                formats.append({"id": f.get("format_id"), "ext": ext, "resolution": res,
                    "vcodec": vcodec, "acodec": acodec, "filesize": fsize, "note": f.get("format_note", "")})
            return jsonify({"title": info.get("title", "Unknown"), "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0), "uploader": info.get("uploader", ""), "formats": formats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _do_download(task_id, url, format_id, audio_only, settings):
    tasks[task_id]["status"] = "downloading"
    ydl_opts = {
        "outtmpl": str(DOWNLOAD_DIR / "%(title)s.%(ext)s"),
        "quiet": True, "no_warnings": True,
        "progress_hooks": [lambda d: _update_progress(task_id, d)]
    }
    if settings.get("use_cookies") and COOKIE_FILE.exists():
        ydl_opts["cookiefile"] = str(COOKIE_FILE)

    if audio_only:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
    elif format_id and format_id != "best":
        ydl_opts["format"] = f"{format_id}+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"
    else:
        ydl_opts["format"] = "bestvideo+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = Path(ydl.prepare_filename(info))
            if audio_only:
                filename = filename.with_suffix(".mp3")
            else:
                stem = filename.stem
                for ext in ["mp4", "mkv", "webm"]:
                    candidate = DOWNLOAD_DIR / f"{stem}.{ext}"
                    if candidate.exists():
                        filename = candidate
                        break
            tasks[task_id]["status"]   = "done"
            tasks[task_id]["filename"] = filename.name
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"]  = str(e)

def _update_progress(task_id, d):
    if d["status"] == "downloading":
        total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded = d.get("downloaded_bytes", 0)
        tasks[task_id].update({
            "progress": int(downloaded / total * 100) if total else 0,
            "speed":    d.get("speed") or 0,
            "eta":      d.get("eta") or 0
        })

@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.json or {}
    url  = data.get("url", "").strip()
    if not url: return jsonify({"error": "URL required"}), 400
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {"status": "pending", "progress": 0, "speed": 0, "eta": 0, "filename": "", "error": ""}
    threading.Thread(target=_do_download,
        args=(task_id, url, data.get("format_id", "best"), data.get("audio_only", False), load_settings()),
        daemon=True).start()
    return jsonify({"task_id": task_id})

@app.route("/api/progress/<task_id>")
def get_progress(task_id):
    task = tasks.get(task_id)
    if not task: return jsonify({"error": "Task not found"}), 404
    return jsonify(task)

@app.route("/api/files")
def list_files():
    files = []
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file():
            st = f.stat()
            files.append({"name": f.name, "size": st.st_size, "mtime": st.st_mtime})
    return jsonify(sorted(files, key=lambda x: x["mtime"], reverse=True))

@app.route("/api/files/<path:filename>", methods=["DELETE"])
@login_required
def delete_file(filename):
    path = (DOWNLOAD_DIR / filename).resolve()
    if path.parent.resolve() != DOWNLOAD_DIR.resolve():
        return jsonify({"error": "Invalid path"}), 400
    if path.exists(): path.unlink()
    return jsonify({"ok": True})

@app.route("/api/files/download/<path:filename>")
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/api/files/clear", methods=["DELETE"])
@login_required
def clear_files():
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file(): f.unlink()
    return jsonify({"ok": True})

@app.route("/api/settings", methods=["GET"])
def get_settings():
    s = load_settings()
    s.pop("admin_password_hash", None)
    return jsonify(s)

@app.route("/api/settings", methods=["POST"])
@login_required
def post_settings():
    data     = request.json or {}
    settings = load_settings()
    for k in ["site_title", "logo_type", "logo_url", "logo_gradient", "logo_text",
              "links", "ads", "use_cookies"]:
        if k in data: settings[k] = data[k]
    save_settings(settings)
    return jsonify({"ok": True})

@app.route("/api/cookies", methods=["GET"])
@login_required
def get_cookies():
    return jsonify({"cookies": COOKIE_FILE.read_text() if COOKIE_FILE.exists() else ""})

@app.route("/api/cookies", methods=["POST"])
@login_required
def save_cookies():
    COOKIE_FILE.write_text((request.json or {}).get("cookies", ""))
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
