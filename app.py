from os import makedirs
from datetime import datetime
from dotenv import load_dotenv
import shortuuid
from flask import Flask, request, jsonify, send_file, render_template, redirect, session
from supabase import create_client, Client
from flask_cors import CORS
import qrcode
from werkzeug.utils import secure_filename
import secrets
from functools import wraps
import validators
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import tempfile
import redis
import os

# Load environment variables
load_dotenv()
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# File Upload Configuration
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "pdf", "txt"}
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB limit
makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Session Security (enable in production)
if os.getenv("FLASK_ENV") == "production":
    app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

# Rate Limiting
def get_user_id():
    return session.get("user_id", get_remote_address())

redis_url = os.getenv("REDIS_URL")
if redis_url:
    limiter = Limiter(
        key_func=get_user_id,
        storage_uri=redis_url
    )
else:
    limiter = Limiter(key_func=get_user_id)

limiter.init_app(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/shorten", methods=["POST"])
@limiter.limit("10/minute")
def shorten_url():
    data = request.get_json(force=True, silent=True)
    if not data or ("url" not in data and "original_url" not in data):
        return jsonify({"error": "Missing URL in request."}), 400

    # Accept either 'url' or 'original_url' key from frontend
    original_url = (data.get("url") or data.get("original_url") or "").strip()
    custom_alias = (data.get("custom_alias") or "").strip()
    folder = (data.get("folder") or "").strip()
    tags = ",".join(data.get("tags", [])) if isinstance(data.get("tags"), list) else ""

    if not original_url:
        return jsonify({"error": "URL cannot be empty."}), 400

    # Add scheme if missing
    if not original_url.startswith(("http://", "https://")):
        original_url = "http://" + original_url

    # Validate again after adding scheme
    if not validators.url(original_url):
        return jsonify({"error": "Invalid URL. Please enter a valid domain like example.com or include http:// or https://."}), 400

    # Check for custom alias
    if custom_alias:
        short_code = custom_alias
        exists = supabase.table("urls").select("short_code").eq("short_code", short_code).execute()
        if exists.data:
            return jsonify({"error": "Custom alias already taken"}), 409
    else:
        # Generate unique short code
        while True:
            short_code = shortuuid.ShortUUID().random(length=6)
            exists = supabase.table("urls").select("short_code").eq("short_code", short_code).execute()
            if not exists.data:
                break

    now = datetime.utcnow().isoformat()

    # Insert into Supabase with all fields
    supabase.table("urls").insert({
        "original_url": original_url,
        "short_code": short_code,
        "custom_alias": custom_alias if custom_alias else None,
        "folder": folder if folder else None,
        "tags": tags if tags else None,
        "clicks": 0,
        "created_at": now,
        "updated_at": now
    }).execute()

    # Extract host without protocol for subdomain format
    host = request.host_url.rstrip('/').replace('http://', '').replace('https://', '')

    return jsonify({
        "short_url": f"{request.host_url}{short_code}",
        "subdomain_url": f"http://{short_code}.{host}",
        "folder": folder,
        "tags": tags.split(",") if tags else [],
        "created_at": now
    }), 201

@app.route("/<short_code>")
def redirect_short_url(short_code):
    try:
        # Get URL data and update click count atomically
        url_data = supabase.table("urls").select("*").eq("short_code", short_code).execute()
        if not url_data.data:
            return render_template("404.html"), 404

        url = url_data.data[0]
        
        # Update clicks and last access time
        supabase.table("urls").update({
            "clicks": url["clicks"] + 1,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", url["id"]).execute()

        return redirect(url["original_url"])
    except Exception as e:
        app.logger.error(f"Error redirecting URL {short_code}: {str(e)}")
        return render_template("404.html"), 404

@app.route("/api/urls/stats/<short_code>")
def get_url_stats(short_code):
    try:
        url_data = supabase.table("urls").select("*").eq("short_code", short_code).execute()
        if not url_data.data:
            return jsonify({"error": "URL not found"}), 404

        url = url_data.data[0]
        return jsonify({
            "short_code": url["short_code"],
            "original_url": url["original_url"],
            "clicks": url["clicks"],
            "folder": url["folder"],
            "tags": url["tags"].split(",") if url["tags"] else [],
            "created_at": url["created_at"],
            "last_accessed": url["updated_at"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/urls/list")
def list_urls():
    try:
        folder = request.args.get("folder")
        tag = request.args.get("tag")
        
        query = supabase.table("urls").select("*")
        if folder:
            query = query.eq("folder", folder)
        if tag:
            query = query.ilike("tags", f"%{tag}%")
            
        urls = query.order("created_at", desc=True).execute()
        
        return jsonify({
            "urls": [{
                "short_code": url["short_code"],
                "original_url": url["original_url"],
                "short_url": f"{request.host_url}{url['short_code']}",
                "clicks": url["clicks"],
                "folder": url["folder"],
                "tags": url["tags"].split(",") if url["tags"] else [],
                "created_at": url["created_at"],
                "last_accessed": url["updated_at"]
            } for url in urls.data]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/qr/<short_code>")
def generate_qr(short_code):
    url_data = supabase.table("urls").select("short_code").eq("short_code", short_code).execute()
    if not url_data.data:
        return jsonify({"error": "URL not found"}), 404
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"{request.host_url}{short_code}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img.save(tmp.name)
        tmp.seek(0)
        response = send_file(tmp.name, mimetype="image/png")
    os.unlink(tmp.name)
    return response

@app.route("/api/upload", methods=["POST"])
@limiter.limit("5/minute")
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{shortuuid.uuid()}_{filename}"
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(file_path)
        return jsonify({"public_url": f"/uploads/{unique_filename}"})
    return jsonify({"error": "File type not allowed"}), 400

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_file(os.path.join(app.config["UPLOAD_FOLDER"], filename))

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

# Rate Limiting (repeated configuration removed for brevity)
if redis_url:
    redis_client = redis.from_url(redis_url)
    limiter = Limiter(
        key_func=get_user_id,
        storage_uri=redis_url
    )
else:
    limiter = Limiter(key_func=get_user_id)

limiter.init_app(app)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
