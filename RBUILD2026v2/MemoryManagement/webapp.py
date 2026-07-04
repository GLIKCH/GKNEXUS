import json
import os
import subprocess
import zipfile
import base64
import mimetypes
import shutil
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from functools import wraps
from urllib import error, request as urlrequest
from flask import Flask, Response, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from .storage import (
    BASE_DIR as STORAGE_BASE_DIR,
    CONV_DIR,
    list_conversations,
    load_conversation,
    save_conversation,
    delete_conversation,
    search_conversations,
    prune_expired_conversations,
    capture_conversation,
)
from .models import Conversation

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
LOG_DIR = os.path.join(BASE_DIR, "logs")
EXPORT_DIR = os.path.join(BASE_DIR, "docs", "exports")
IMPORT_DIR = os.path.join(BASE_DIR, "docs", "imports")
IMAGE_DIR = os.path.join(BASE_DIR, "docs", "images")
BUNDLE_DIR = os.path.join(BASE_DIR, "docs", "bundles")
AGENT_TEMPLATES_FILE = os.path.join(BASE_DIR, "docs", "agent_templates.json")
EMOTION_PRESETS_FILE = os.path.join(BASE_DIR, "docs", "emotion_presets.json")
UI_SETTINGS_FILE = os.path.join(BASE_DIR, "docs", "ui_settings.json")
EXTENSIONS_FILE = os.path.join(BASE_DIR, "docs", "extensions.json")
USER_ASSET_DIR = os.path.join(BASE_DIR, "static", "user")
TEXT_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".json", ".html", ".css", ".scss", ".md", ".txt",
    ".py", ".toml", ".yaml", ".yml", ".env", ".example", ".gitignore", ".dockerfile",
    ".sql", ".sh", ".ps1", ".bat", ".xml", ".svg", ".cjs", ".mjs", ".vue", ".svelte",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xlsm", ".xls", ".csv", ".ipynb"}
SKIP_DIR_PARTS = {"node_modules", ".git", "dist", "build", ".next", ".venv", "venv", "__pycache__"}

SECURE_BUNDLE_MARKER = "glikch_secure_manifest.json"
TOKEN_WINDOW_DEFAULT = int(os.environ.get("LM_STUDIO_CONTEXT_TOKENS", "131072"))

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = os.environ.get("MEMORY_CONSOLE_SECRET", "change-this-secret")

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234").rstrip("/")
DEFAULT_MODEL = os.environ.get("LM_STUDIO_MODEL", "")
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("LM_STUDIO_TIMEOUT_SECONDS", "1800"))
MAX_RESPONSE_TOKENS = int(os.environ.get("LM_STUDIO_MAX_RESPONSE_TOKENS", "8192"))
ADMIN_USERNAME = os.environ.get("MEMORY_CONSOLE_USERNAME", "glikch")
ADMIN_PASSWORD_HASH = os.environ.get(
    "MEMORY_CONSOLE_PASSWORD_HASH",
    "scrypt:32768:8:1$OXZ2o8d6w3YOd30W$25c6628836bb324a8c8a29b3804c48c278d395b97159aa9eb9d802ac635965062353cde08a27e5a5800b2dad4f4e0f7ba15eb78d0de2c47856c15a8832a00e04",
)

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(IMPORT_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(BUNDLE_DIR, exist_ok=True)
os.makedirs(USER_ASSET_DIR, exist_ok=True)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


DEFAULT_UI_SETTINGS = {
    "login_wallpaper": "",
    "app_wallpaper": "",
    "app_logo": "",
    "logo_scale": 1.0,
    "logo_offset_x": 0,
    "logo_offset_y": 0,
    "mascot_scale": 1.0,
    "login_position": "center",
    "theme_preset": "crimson-violet",
    "border_strength": 1.0,
    "glow_strength": 0.75,
    "accent_colors": ["#ff2a3d", "#ff6a00", "#ffd000", "#ff2fd6", "#7b2cff", "#13e8ff"],
    "exterior_border_color": "#13e8ff",
    "neon_enabled": True,
    "chrome_alpha": 0.72,
    "mascot_enabled": True,
    "voice_enabled": False,
    "voice_name": "",
    "default_model": DEFAULT_MODEL,
    "token_window": TOKEN_WINDOW_DEFAULT,
    "matrix_enabled": True,
    "matrix_charset": "01GLIKCHNEXUZ$#<>/{}[]()rootAI",
    "matrix_color_top": "#ff7a7a",
    "matrix_color_mid": "#ff1f33",
    "matrix_color_tail": "#3b0008",
    "matrix_text_color": "#ff3038",
    "matrix_glow_color": "#ff1f33",
    "matrix_glow_strength": 1.0,
    "matrix_text_size": 0.78,
    "matrix_distance": 230,
    "matrix_emoji_enabled": False,
    "matrix_density": 42,
    "matrix_speed": 18,
}


def _clean_hex_color(value: str, fallback: str) -> str:
    value = str(value or "").strip()
    if len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
            return value.lower()
        except ValueError:
            pass
    return fallback


def _default_ui_settings() -> dict:
    defaults = dict(DEFAULT_UI_SETTINGS)
    defaults["accent_colors"] = list(DEFAULT_UI_SETTINGS["accent_colors"])
    defaults["login_wallpaper"] = url_for("static", filename="brand/login-wallpaper.png")
    defaults["app_wallpaper"] = url_for("static", filename="brand/dashboard-wallpaper.png")
    defaults["app_logo"] = url_for("static", filename="user/gknxzlogo01.png")
    return defaults


def _load_ui_settings() -> dict:
    settings = _default_ui_settings()
    if os.path.exists(UI_SETTINGS_FILE):
        try:
            with open(UI_SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
                data = json.load(settings_file)
            if isinstance(data, dict):
                settings.update({key: value for key, value in data.items() if key in settings})
        except Exception as exc:
            _log_event("error", "UI settings load failed", error=str(exc))
    settings["login_position"] = settings.get("login_position") if settings.get("login_position") in {"center", "left", "right", "top", "bottom"} else "center"
    settings["border_strength"] = max(0.0, min(2.0, float(settings.get("border_strength") or 1.0)))
    settings["glow_strength"] = max(0.0, min(2.0, float(settings.get("glow_strength") or 0.75)))
    settings["token_window"] = max(1024, min(1048576, int(float(settings.get("token_window") or TOKEN_WINDOW_DEFAULT))))
    settings["matrix_density"] = max(8, min(120, int(float(settings.get("matrix_density") or 42))))
    settings["matrix_speed"] = max(6, min(60, int(float(settings.get("matrix_speed") or 18))))
    settings["matrix_glow_strength"] = max(0.0, min(3.0, float(settings.get("matrix_glow_strength") or 1.0)))
    settings["matrix_text_size"] = max(0.45, min(1.4, float(settings.get("matrix_text_size") or 0.78)))
    settings["matrix_distance"] = max(120, min(420, int(float(settings.get("matrix_distance") or 230))))
    for key, fallback in (("matrix_color_top", "#ff7a7a"), ("matrix_color_mid", "#ff1f33"), ("matrix_color_tail", "#3b0008"), ("matrix_text_color", "#ff3038"), ("matrix_glow_color", "#ff1f33")):
        settings[key] = _clean_hex_color(settings.get(key), fallback)
    colors = settings.get("accent_colors") if isinstance(settings.get("accent_colors"), list) else []
    fallback = DEFAULT_UI_SETTINGS["accent_colors"]
    settings["accent_colors"] = [_clean_hex_color(colors[index] if index < len(colors) else "", fallback[index]) for index in range(6)]
    return settings


def _save_ui_settings(data: dict) -> dict:
    current = _load_ui_settings()
    for key in ["login_wallpaper", "app_wallpaper", "app_logo", "theme_preset", "voice_name", "default_model"]:
        if key in data:
            current[key] = str(data.get(key) or "").strip()[:500]
    if "matrix_charset" in data:
        current["matrix_charset"] = str(data.get("matrix_charset") or DEFAULT_UI_SETTINGS["matrix_charset"]).strip()[:120] or DEFAULT_UI_SETTINGS["matrix_charset"]
    if data.get("login_position") in {"center", "left", "right", "top", "bottom"}:
        current["login_position"] = data["login_position"]
    if "border_strength" in data:
        current["border_strength"] = max(0.0, min(2.0, float(data.get("border_strength") or 1.0)))
    if "glow_strength" in data:
        current["glow_strength"] = max(0.0, min(2.0, float(data.get("glow_strength") or 0.75)))
    if "logo_scale" in data:
        current["logo_scale"] = max(0.6, min(2.2, float(data.get("logo_scale") or 1.0)))
    if "logo_offset_x" in data:
        current["logo_offset_x"] = max(-120, min(120, int(float(data.get("logo_offset_x") or 0))))
    if "logo_offset_y" in data:
        current["logo_offset_y"] = max(-40, min(40, int(float(data.get("logo_offset_y") or 0))))
    if "mascot_scale" in data:
        current["mascot_scale"] = max(0.7, min(1.8, float(data.get("mascot_scale") or 1.0)))
    if "exterior_border_color" in data:
        current["exterior_border_color"] = _clean_hex_color(data.get("exterior_border_color"), DEFAULT_UI_SETTINGS["exterior_border_color"])
    if "chrome_alpha" in data:
        current["chrome_alpha"] = max(0.0, min(1.0, float(data.get("chrome_alpha") or DEFAULT_UI_SETTINGS["chrome_alpha"])))
    if "token_window" in data:
        current["token_window"] = max(1024, min(1048576, int(float(data.get("token_window") or TOKEN_WINDOW_DEFAULT))))
    if "matrix_density" in data:
        current["matrix_density"] = max(8, min(120, int(float(data.get("matrix_density") or 42))))
    if "matrix_speed" in data:
        current["matrix_speed"] = max(6, min(60, int(float(data.get("matrix_speed") or 18))))
    if "matrix_glow_strength" in data:
        current["matrix_glow_strength"] = max(0.0, min(3.0, float(data.get("matrix_glow_strength") or 1.0)))
    if "matrix_text_size" in data:
        current["matrix_text_size"] = max(0.45, min(1.4, float(data.get("matrix_text_size") or 0.78)))
    if "matrix_distance" in data:
        current["matrix_distance"] = max(120, min(420, int(float(data.get("matrix_distance") or 230))))
    for key, fallback in (("matrix_color_top", "#ff7a7a"), ("matrix_color_mid", "#ff1f33"), ("matrix_color_tail", "#3b0008"), ("matrix_text_color", "#ff3038"), ("matrix_glow_color", "#ff1f33")):
        if key in data:
            current[key] = _clean_hex_color(data.get(key), fallback)
    for key in ["neon_enabled", "mascot_enabled", "voice_enabled", "matrix_enabled", "matrix_emoji_enabled"]:
        if key in data:
            current[key] = bool(data.get(key))
    if isinstance(data.get("accent_colors"), list):
        fallback = DEFAULT_UI_SETTINGS["accent_colors"]
        current["accent_colors"] = [_clean_hex_color(data["accent_colors"][index] if index < len(data["accent_colors"]) else "", fallback[index]) for index in range(6)]
    os.makedirs(os.path.dirname(UI_SETTINGS_FILE), exist_ok=True)
    with open(UI_SETTINGS_FILE, "w", encoding="utf-8") as settings_file:
        json.dump({"schema": "glikch.nexuz.ui-settings.v1", **current}, settings_file, ensure_ascii=False, indent=2)
    _log_event("info", "UI settings saved")
    return current


@app.route("/login", methods=["GET", "POST"])
def login():
    error_message = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["authenticated"] = True
            session["username"] = username
            _log_event("info", "Admin login succeeded", username=username)
            return redirect(request.args.get("next") or url_for("chat"))
        error_message = "Invalid login."
        _log_event("error", "Admin login failed", username=username)
    return render_template("login.html", error_message=error_message, ui_settings=_load_ui_settings())


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.errorhandler(413)
def payload_too_large(exc):
    _log_event("error", "Request payload too large", error=str(exc))
    return jsonify({"error": "Request payload is too large. Try a smaller or compressed image."}), 413


@app.errorhandler(500)
def internal_server_error(exc):
    _log_event("error", "Unhandled server error", error=str(exc))
    return jsonify({"error": "Internal server error. Check the dated log for details."}), 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today_log_path() -> str:
    return os.path.join(LOG_DIR, f"{datetime.now(timezone.utc).date().isoformat()}.log")


def _log_event(level: str, message: str, **context) -> None:
    entry = {
        "timestamp": _now_iso(),
        "level": level.upper(),
        "message": message,
        "context": context,
    }
    with open(_today_log_path(), "a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _conversation_to_dict(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "metadata": conv.metadata,
        "messages": conv.messages,
        "message_count": len(conv.messages),
    }


def _safe_filename(value: str) -> str:
    allowed = [char if char.isalnum() or char in ("-", "_", ".") else "-" for char in value]
    return "".join(allowed).strip("-") or "conversation"


def _safe_join(base_dir: str, *parts: str) -> str:
    candidate = os.path.abspath(os.path.join(base_dir, *parts))
    base = os.path.abspath(base_dir)
    if candidate != base and not candidate.startswith(base + os.sep):
        raise ValueError("Invalid file path.")
    return candidate


def _save_data_url_image(data_url: str, conversation_id: str, name: str) -> dict:
    if not data_url.startswith("data:image/") or "," not in data_url:
        raise ValueError("Invalid image data URL.")
    header, encoded = data_url.split(",", 1)
    mime = header[5:].split(";")[0].lower()
    extension = mimetypes.guess_extension(mime) or ".png"
    if extension == ".jpe":
        extension = ".jpg"
    image_bytes = base64.b64decode(encoded, validate=True)
    if len(image_bytes) > 8 * 1024 * 1024:
        raise ValueError("Image is too large after compression. Keep images under 8 MB.")
    conv_dir = _safe_join(IMAGE_DIR, _safe_filename(conversation_id))
    os.makedirs(conv_dir, exist_ok=True)
    stem = _safe_filename(os.path.splitext(name or "image")[0])
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}-{stem}{extension}"
    path = _safe_join(conv_dir, filename)
    with open(path, "wb") as image_file:
        image_file.write(image_bytes)
    return {
        "name": name or filename,
        "mime": mime,
        "file": os.path.relpath(path, BASE_DIR).replace("\\", "/"),
        "size": len(image_bytes),
    }



def _estimate_tokens_text(value) -> int:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value or "")
    return max(1 if text else 0, (len(text) + 3) // 4)


def _estimate_tokens_messages(messages: list) -> int:
    return sum(_estimate_tokens_text(item.get("content", "")) + 4 for item in messages if isinstance(item, dict))


def _token_window() -> int:
    try:
        return int(_load_ui_settings().get("token_window") or TOKEN_WINDOW_DEFAULT)
    except Exception:
        return TOKEN_WINDOW_DEFAULT


def _estimate_conversation_tokens(conv: Conversation) -> dict:
    prompt_tokens = _estimate_tokens_messages(conv.messages)
    compact_tokens = _estimate_tokens_text(_compact_conversation(conv))
    return {
        "window": _token_window(),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": 0,
        "total_tokens": prompt_tokens,
        "context_tokens": prompt_tokens,
        "remaining_tokens": max(0, _token_window() - prompt_tokens),
        "percent_used": round(min(100, (prompt_tokens / _token_window()) * 100), 1) if _token_window() else 0,
        "compact_tokens": compact_tokens,
        "compact_percent": round(min(100, (compact_tokens / _token_window()) * 100), 1) if _token_window() else 0,
    }


def _derive_bundle_keys(password: str, salt: bytes) -> tuple[bytes, bytes]:
    material = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240000, dklen=64)
    return material[:32], material[32:]


def _xor_stream(data: bytes, key: bytes, salt: bytes) -> bytes:
    output = bytearray()
    counter = 0
    for index in range(0, len(data), 32):
        block = hmac.new(key, salt + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        chunk = data[index:index + 32]
        output.extend(byte ^ block[pos] for pos, byte in enumerate(chunk))
        counter += 1
    return bytes(output)


def _encrypt_bytes(data: bytes, password: str) -> dict:
    salt = secrets.token_bytes(16)
    enc_key, mac_key = _derive_bundle_keys(password, salt)
    ciphertext = _xor_stream(data, enc_key, salt)
    tag = hmac.new(mac_key, salt + ciphertext, hashlib.sha256).hexdigest()
    return {
        "schema": "glikch.secure.bundle.v1",
        "kdf": "pbkdf2-hmac-sha256",
        "iterations": 240000,
        "salt": base64.b64encode(salt).decode("ascii"),
        "tag": tag,
        "payload": base64.b64encode(ciphertext).decode("ascii"),
    }


def _decrypt_bytes(payload: dict, password: str) -> bytes:
    if not password:
        raise ValueError("Secure bundle password required.")
    salt = base64.b64decode(payload.get("salt", ""))
    ciphertext = base64.b64decode(payload.get("payload", ""))
    enc_key, mac_key = _derive_bundle_keys(password, salt)
    expected = hmac.new(mac_key, salt + ciphertext, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(payload.get("tag", ""))):
        raise ValueError("Secure bundle password is incorrect or the bundle was modified.")
    return _xor_stream(ciphertext, enc_key, salt)

def _read_text_file(file_path: str) -> str:
    with open(file_path, "rb") as raw_file:
        data = raw_file.read()
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_docx(file_path: str) -> str:
    with zipfile.ZipFile(file_path) as docx:
        xml = docx.read("word/document.xml").decode("utf-8", errors="replace")
    text = xml.replace("</w:p>", "\n").replace("</w:t>", "")
    chunks = []
    in_tag = False
    current = []
    for char in text:
        if char == "<":
            in_tag = True
            if current:
                chunks.append("".join(current))
                current = []
        elif char == ">":
            in_tag = False
        elif not in_tag:
            current.append(char)
    if current:
        chunks.append("".join(current))
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip())


def _read_xlsx(file_path: str) -> str:
    try:
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(file_path) as workbook:
            shared_strings = []
            if "xl/sharedStrings.xml" in workbook.namelist():
                root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                for item in root.iter():
                    if item.tag.endswith("}t") and item.text:
                        shared_strings.append(item.text)
            sheets = [name for name in workbook.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
            lines = []
            for sheet in sheets[:12]:
                lines.append(f"# {sheet}")
                root = ET.fromstring(workbook.read(sheet))
                row_values = []
                for cell in root.iter():
                    if not cell.tag.endswith("}c"):
                        continue
                    value_node = next((child for child in cell if child.tag.endswith("}v")), None)
                    if value_node is None or value_node.text is None:
                        continue
                    if cell.attrib.get("t") == "s":
                        idx = int(value_node.text)
                        row_values.append(shared_strings[idx] if idx < len(shared_strings) else value_node.text)
                    else:
                        row_values.append(value_node.text)
                if row_values:
                    lines.append(", ".join(row_values[:200]))
            return "\n".join(lines)
    except Exception as exc:
        return f"Excel workbook detected, but extraction failed: {exc}"


def _read_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages[:40]).strip()
    except Exception:
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                return "\n\n".join(page.extract_text() or "" for page in pdf.pages[:40]).strip()
        except Exception as exc:
            return f"PDF detected, but text extraction is unavailable: {exc}"



def _dedupe_agent_templates(templates: list) -> list:
    seen = set()
    cleaned = []
    defaults = [
        {"name": "Unnamed Agent", "mode": "Chat", "instruction": "General local assistant. Keep responses readable and avoid raw JSON unless requested."},
        {"name": "School Guide", "mode": "School", "instruction": "Use reputable, current sources when browsing is available. Keep a professional college-student tone and explain concepts clearly."},
        {"name": "Developer", "mode": "Developer", "instruction": "Use DevSecOps practices, ethical cybersecurity judgment, clean code, and clear documentation."},
        {"name": "Cybersecurity", "mode": "Cybersecurity", "instruction": "Think like an ethical penetration tester and cybersecurity analyst. Cover risk, controls, detection, IDS/IPS, tooling, and responsible boundaries."},
    ]
    for item in [*defaults, *(templates or [])]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "Unnamed Agent").strip()[:80] or "Unnamed Agent"
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({
            "name": name,
            "mode": str(item.get("mode") or item.get("agent_type") or "Chat").strip()[:40] or "Chat",
            "instruction": str(item.get("instruction") or "").strip()[:2000],
            "execution_policy": str(item.get("execution_policy") or item.get("policy") or "ask").strip()[:40],
            "creator": str(item.get("creator") or "").strip()[:120],
            "email": str(item.get("email") or "").strip()[:180],
        })
    return cleaned

def _load_agent_templates() -> list:
    if not os.path.exists(AGENT_TEMPLATES_FILE):
        return [{"name": "Unnamed Agent", "mode": "Chat", "instruction": "General local assistant."}]
    try:
        with open(AGENT_TEMPLATES_FILE, "r", encoding="utf-8") as template_file:
            data = json.load(template_file)
        return _dedupe_agent_templates(data if isinstance(data, list) else [])
    except Exception:
        return [{"name": "Unnamed Agent", "mode": "Chat", "instruction": "General local assistant."}]


def _save_agent_templates(templates: list) -> None:
    cleaned = []
    for item in templates:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "Unnamed Agent").strip()[:80]
        cleaned.append(
            {
                "name": name,
                "mode": str(item.get("mode") or "Chat").strip()[:40],
                "instruction": str(item.get("instruction") or "").strip()[:2000],
            }
        )
    with open(AGENT_TEMPLATES_FILE, "w", encoding="utf-8") as template_file:
        json.dump(_dedupe_agent_templates(cleaned), template_file, ensure_ascii=False, indent=2)


def _should_import_project_file(original_name: str, size: int) -> bool:
    normalized = original_name.replace("\\", "/")
    parts = {part.lower() for part in normalized.split("/")}
    if parts & SKIP_DIR_PARTS:
        return False
    ext = os.path.splitext(original_name)[1].lower()
    if ext == ".zip":
        return size <= 50 * 1024 * 1024
    if ext in IMAGE_EXTENSIONS or ext in DOCUMENT_EXTENSIONS or ext in TEXT_EXTENSIONS:
        return size <= 2 * 1024 * 1024
    return False



def _compact_memory_summary(data: dict) -> str:
    if not isinstance(data, dict):
        return "Imported memory data was detected."
    title = data.get("title") or data.get("id") or "Imported chat"
    created = data.get("created") or "unknown date"
    messages = data.get("messages") if isinstance(data.get("messages"), list) else []
    bullets = [f"Imported compressed chat: {title} ({created})."]
    if data.get("resume_instruction"):
        bullets.append(str(data["resume_instruction"]))
    for item in messages[-8:]:
        if not isinstance(item, dict):
            continue
        role = "Assistant" if item.get("r") == "a" or item.get("role") == "assistant" else "User"
        content = str(item.get("c") or item.get("content") or "").strip()
        if content:
            bullets.append(f"{role}: {' '.join(content.split())[:500]}")
    return "\n".join(f"- {line}" for line in bullets)


def _bundle_manifest_summary(data: dict) -> str:
    parts = [
        f"Bundle for conversation {data.get('conversation_id', 'unknown')} created {data.get('created', 'unknown')}.",
        f"Human transcript: {data.get('human_transcript', 'not listed')}.",
        f"Compact memory: {data.get('compact_memory', 'not listed')}.",
    ]
    if data.get("images"):
        parts.append(f"Images included: {len(data.get('images') or [])}.")
    if data.get("logs"):
        parts.append(f"Logs included: {len(data.get('logs') or [])}.")
    return "\n".join(f"- {part}" for part in parts)

def _detect_import(file_path: str, original_name: str) -> dict:
    extension = os.path.splitext(original_name)[1].lower()
    result = {
        "filename": original_name,
        "extension": extension or "unknown",
        "detected_format": "unknown",
        "status": "detected",
        "messages": [],
        "compact_memory": None,
        "text_preview": "",
        "image_ref": None,
        "error": None,
    }
    try:
        if extension == ".json":
            data = json.loads(_read_text_file(file_path))
            result["detected_format"] = data.get("schema", "json") if isinstance(data, dict) else "json"
            if os.path.basename(original_name).lower() == "agent_templates.json" and isinstance(data, list):
                _save_agent_templates(_load_agent_templates() + [item for item in data if isinstance(item, dict)])
                result["detected_format"] = "agent-templates"
                result["text_preview"] = "Agent presets imported and deduplicated."
                result["messages"] = []
                return result
            if isinstance(data, dict) and data.get("schema") == "glikch.session.bundle.v1":
                result["detected_format"] = "bundle-manifest"
                result["text_preview"] = _bundle_manifest_summary(data)
                result["messages"] = []
                return result
            if isinstance(data, dict) and "messages" in data:
                result["compact_memory"] = data
                result["messages"] = [
                    {
                        "role": "assistant" if item.get("r") == "a" else "user",
                        "content": item.get("c", ""),
                        "timestamp": item.get("t"),
                    }
                    for item in data.get("messages", [])
                    if isinstance(item, dict)
                ]
                result["text_preview"] = _compact_memory_summary(data)
                return result
            result["text_preview"] = json.dumps(data, ensure_ascii=False, indent=2)[:2000]
        elif extension == ".ipynb":
            data = json.loads(_read_text_file(file_path))
            result["detected_format"] = "jupyter-notebook"
            cell_text = []
            for cell in data.get("cells", []):
                source = cell.get("source", [])
                cell_text.append("".join(source) if isinstance(source, list) else str(source))
            result["text_preview"] = "\n\n".join(cell_text)[:4000]
            result["messages"] = [{"role": "user", "content": result["text_preview"]}]
        elif extension == ".csv":
            text = _read_text_file(file_path)
            result["detected_format"] = "csv"
            lines = [line for line in text.splitlines() if line.strip()]
            result["text_preview"] = "\n".join(lines[:50])
            result["messages"] = [{"role": "user", "content": result["text_preview"]}]
        elif os.path.basename(original_name).lower() == "session_report.html":
            result["detected_format"] = "session-report"
            result["status"] = "reference"
            result["text_preview"] = "Session report detected and kept as a readable bundle reference, but not injected into LLM context."
        elif extension in (".txt", ".md"):
            text = _read_text_file(file_path)
            result["detected_format"] = "markdown" if extension == ".md" else "plain-text"
            result["text_preview"] = text[:4000]
            result["messages"] = [{"role": "user", "content": text}]
        elif extension == ".docx":
            text = _read_docx(file_path)
            result["detected_format"] = "word-docx"
            result["text_preview"] = text[:4000]
            result["messages"] = [{"role": "user", "content": text}]
        elif extension in (".xlsx", ".xlsm"):
            text = _read_xlsx(file_path)
            result["detected_format"] = "excel-workbook"
            result["text_preview"] = text[:4000]
            result["messages"] = [{"role": "user", "content": text}]
        elif extension == ".pdf":
            text = _read_pdf(file_path)
            result["detected_format"] = "pdf"
            if text and not text.startswith("PDF detected, but"):
                result["text_preview"] = text[:4000]
                result["messages"] = [{"role": "user", "content": text}]
            else:
                result["status"] = "limited"
                result["error"] = text or "PDF detected, but no text was extracted."
        elif extension in IMAGE_EXTENSIONS:
            result["detected_format"] = "image"
            image_dir = _safe_join(IMAGE_DIR, "imports")
            os.makedirs(image_dir, exist_ok=True)
            image_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}-{secure_filename(os.path.basename(original_name))}"
            image_path = _safe_join(image_dir, image_name)
            with open(file_path, "rb") as src, open(image_path, "wb") as dst:
                dst.write(src.read())
            result["image_ref"] = os.path.relpath(image_path, BASE_DIR).replace("\\", "/")
            result["text_preview"] = f"Image file imported: {original_name}. Stored at {result['image_ref']}."
        else:
            text = _read_text_file(file_path)
            result["detected_format"] = "source-code" if extension in TEXT_EXTENSIONS else "text-like"
            result["text_preview"] = text[:4000]
            result["messages"] = [{"role": "user", "content": text}]
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
    return result


def _extract_zip_import(file_path: str, import_dir: str, original_name: str, password: str = "") -> list:
    detected = []
    bundle_dir = _safe_join(import_dir, f"{secure_filename(os.path.splitext(os.path.basename(original_name))[0])}-unzipped")
    os.makedirs(bundle_dir, exist_ok=True)
    with zipfile.ZipFile(file_path) as probe:
        names = set(probe.namelist())
        if SECURE_BUNDLE_MARKER in names and "secure_payload.json" in names:
            payload = json.loads(probe.read("secure_payload.json").decode("utf-8"))
            decrypted = _decrypt_bytes(payload, password)
            decrypted_zip = _safe_join(import_dir, f"{secure_filename(os.path.splitext(os.path.basename(original_name))[0])}-decrypted.zip")
            with open(decrypted_zip, "wb") as decrypted_file:
                decrypted_file.write(decrypted)
            detected.append({
                "filename": original_name,
                "extension": ".zip",
                "detected_format": "secure-bundle",
                "status": "decrypted",
                "messages": [],
                "compact_memory": None,
                "text_preview": "Secure bundle password accepted. Decrypted payload loaded.",
                "image_ref": None,
                "error": None,
            })
            detected.extend(_extract_zip_import(decrypted_zip, import_dir, f"{original_name}-decrypted.zip"))
            return detected
    with zipfile.ZipFile(file_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            normalized = info.filename.replace("\\", "/")
            if normalized.startswith("/") or ".." in normalized.split("/"):
                detected.append(
                    {
                        "filename": normalized,
                        "extension": os.path.splitext(normalized)[1].lower() or "unknown",
                        "detected_format": "zip-entry",
                        "status": "skipped",
                        "messages": [],
                        "compact_memory": None,
                        "text_preview": "",
                        "image_ref": None,
                        "error": "Skipped unsafe zip path.",
                    }
                )
                continue
            if not _should_import_project_file(normalized, info.file_size):
                continue
            target = _safe_join(bundle_dir, normalized)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            item = _detect_import(target, normalized)
            item["stored_path"] = target
            detected.append(item)
    if not detected:
        detected.append(
            {
                "filename": original_name,
                "extension": ".zip",
                "detected_format": "zip-archive",
                "status": "limited",
                "messages": [],
                "compact_memory": None,
                "text_preview": "",
                "image_ref": None,
                "error": "Zip was readable, but no supported files were found.",
            }
        )
    return detected


def _import_payload_path(import_id: str) -> str:
    return os.path.join(IMPORT_DIR, f"{_safe_filename(import_id)}.json")


def _compact_import_payload(import_payload: dict) -> dict:
    pieces = []
    agent_presets = []
    for item in import_payload.get("files", []):
        fmt = item.get("detected_format")
        if fmt == "agent-templates":
            agent_presets.append(item.get("filename", "agent_templates.json"))
            continue
        if fmt == "session-report":
            continue
        if item.get("compact_memory"):
            pieces.append(f"{item['filename']} ({fmt})\n{_compact_memory_summary(item['compact_memory'])}")
        elif item.get("image_ref"):
            pieces.append(f"{item['filename']} ({fmt}): stored image at {item['image_ref']}")
        elif item.get("text_preview"):
            clean_preview = " ".join(str(item["text_preview"]).split())
            pieces.append(f"{item['filename']} ({fmt}): {clean_preview}")
    if agent_presets:
        pieces.append("Agent presets were imported and deduplicated; do not repeat their JSON unless asked.")
    readable_context = "\n\n".join(pieces)[:12000]
    if readable_context:
        readable_context = (
            "Readable imported context summary. Explain this in your own words when asked; "
            "do not dump raw JSON or HTML unless the user explicitly requests it.\n\n" + readable_context
        )
    return {
        "schema": "glikch.import.compact.v1",
        "import_id": import_payload["import_id"],
        "created": import_payload["created"],
        "files": [
            {
                "filename": item["filename"],
                "format": item["detected_format"],
                "status": item["status"],
                "error": item.get("error"),
                "image_ref": item.get("image_ref"),
            }
            for item in import_payload.get("files", [])
        ],
        "context": readable_context,
    }


def _latest_compact_export_path() -> str | None:
    candidates = [
        os.path.join(EXPORT_DIR, name)
        for name in os.listdir(EXPORT_DIR)
        if name.endswith("-llm.json")
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def _http_error_detail(exc: error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    if body:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                err = parsed.get("error") or parsed.get("message") or parsed.get("detail")
                if isinstance(err, dict):
                    body = err.get("message") or json.dumps(err, ensure_ascii=False)
                elif err:
                    body = str(err)
                else:
                    body = json.dumps(parsed, ensure_ascii=False)[:1200]
        except Exception:
            body = body[:1200]
    detail = body or str(exc)
    lower = detail.lower()
    if "out of memory" in lower or "cuda" in lower:
        return f"LM Studio GPU memory error: {detail}. Unload/reload the model, reduce context or batch pressure, or switch to a smaller loaded model before retrying."
    return f"LM Studio rejected the request ({exc.code}): {detail}"


def _post_json(url: str, payload: dict, timeout: int = REQUEST_TIMEOUT_SECONDS) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError:
        raise
    except Exception as exc:
        raise TimeoutError(f"LM Studio did not complete the request within {timeout} seconds or the local model worker stopped: {exc}") from exc


def _get_json(url: str, timeout: int = 10) -> dict:
    req = urlrequest.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urlrequest.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _lm_studio_model_ids(timeout: int = 5) -> list[str]:
    model_urls = (f"{LM_STUDIO_URL}/v1/models", f"{LM_STUDIO_URL}/api/v1/models")
    for url in model_urls:
        data = _get_json(url, timeout=timeout)
        raw_models = data.get("data") or data.get("models") or []
        models = []
        for item in raw_models:
            if isinstance(item, dict):
                model_id = item.get("id") or item.get("key") or item.get("display_name")
                if model_id:
                    models.append(str(model_id))
            elif isinstance(item, str):
                models.append(item)
        if models:
            return models
    return []


def _resolve_lm_studio_model(requested_model: str = "") -> tuple[str, list[str], bool]:
    models = []
    try:
        models = _lm_studio_model_ids(timeout=5)
    except Exception as exc:
        _log_event("error", "LM Studio model resolve failed", error=str(exc))
    requested_model = "" if "{{" in str(requested_model) else str(requested_model or "").strip()
    saved_default = str(_load_ui_settings().get("default_model") or "").strip()
    for candidate in (requested_model, saved_default, DEFAULT_MODEL):
        if candidate and (not models or candidate in models):
            return candidate, models, False
    if models:
        return models[0], models, bool(requested_model or saved_default or DEFAULT_MODEL)
    return requested_model or saved_default or DEFAULT_MODEL or "", models, False


def _extract_assistant_text(data: dict) -> str:
    def collect_text(value, depth=0):
        if depth > 6:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            parts = []
            for item in value:
                parts.extend(collect_text(item, depth + 1))
            return parts
        if isinstance(value, dict):
            preferred = []
            for key in ("content", "text", "response", "answer", "message", "output", "result"):
                if key in value:
                    preferred.extend(collect_text(value[key], depth + 1))
            if preferred:
                return preferred
            parts = []
            for item in value.values():
                parts.extend(collect_text(item, depth + 1))
            return parts
        return []

    if isinstance(data.get("choices"), list) and data["choices"]:
        choice = data["choices"][0]
        message = choice.get("message") or {}
        content = message.get("content") or choice.get("text")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            ).strip()

    if isinstance(data.get("output"), list):
        parts = []
        for item in data["output"]:
            if isinstance(item, dict):
                content = item.get("content") or item.get("text") or ""
                if isinstance(content, list):
                    parts.extend(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    )
                else:
                    parts.append(str(content))
        return "\n".join(part for part in parts if part).strip()

    for key in ("content", "response", "text"):
        value = data.get(key)
        if isinstance(value, str):
            return value.strip()

    return "\n".join(collect_text(data)).strip()


def _humanize_assistant_text(text: str) -> str:
    def readable_label(value: str) -> str:
        return value.replace("_", " ").strip().title()

    def stringify(value, depth=0) -> str:
        if depth > 6:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            parts = []
            for item in value:
                item_text = stringify(item, depth + 1)
                if item_text:
                    parts.append(f"- {item_text}" if "\n" not in item_text else item_text)
            return "\n".join(parts).strip()
        if isinstance(value, dict):
            sections = []
            for key, item in value.items():
                item_text = stringify(item, depth + 1)
                if not item_text:
                    continue
                label = readable_label(str(key))
                if isinstance(item, (dict, list)):
                    sections.append(f"{label}:\n{item_text}")
                else:
                    sections.append(f"{label}: {item_text}")
            return "\n\n".join(sections).strip()
        return ""

    cleaned = text.strip()
    if not cleaned:
        return ""

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned

    if isinstance(parsed, dict):
        preferred_keys = (
            "response",
            "answer",
            "message",
            "content",
            "text",
            "greeting",
            "summary",
            "result",
        )
        for key in preferred_keys:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        readable_parts = [
            str(value).strip()
            for value in parsed.values()
            if isinstance(value, str) and value.strip()
        ]
        if readable_parts:
            return "\n\n".join(readable_parts)
        return stringify(parsed)

    if isinstance(parsed, list):
        readable_parts = [
            item.strip() if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            for item in parsed
        ]
        return stringify(parsed) or "\n\n".join(part for part in readable_parts if part)

    return stringify(parsed) or str(parsed).strip()


def _format_transcript(conv: Conversation) -> str:
    title = conv.metadata.get("title") or conv.id
    lines = [
        f"Conversation: {title}",
        f"ID: {conv.id}",
        f"Model: {conv.metadata.get('model') or 'Unknown'}",
        f"Created: {conv.metadata.get('created') or 'Unknown'}",
        "",
    ]
    for message in conv.messages:
        role = str(message.get("role", "unknown")).title()
        timestamp = message.get("timestamp") or ""
        content = str(message.get("content", "")).strip()
        label = f"{role} ({timestamp})" if timestamp else role
        lines.extend([label, content, ""])
    return "\n".join(lines).strip() + "\n"


def _compact_conversation(conv: Conversation) -> dict:
    return {
        "schema": "glikch.memory.compact.v1",
        "id": conv.id,
        "title": conv.metadata.get("title") or conv.id,
        "model": conv.metadata.get("model"),
        "created": conv.metadata.get("created"),
        "resume_instruction": (
            "Continue from this compressed memory. Preserve user goals, decisions, "
            "code context, unresolved errors, and next actions."
        ),
        "messages": [
            {
                "r": str(message.get("role", "unknown"))[:1],
                "t": message.get("timestamp"),
                "c": " ".join(str(message.get("content", "")).split()),
            }
            for message in conv.messages
            if str(message.get("content", "")).strip()
        ],
    }


def _build_notebook(conv: Conversation) -> str:
    compact = _compact_conversation(conv)
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                f"# {conv.metadata.get('title') or conv.id}\n",
                "\n",
                "Human-readable transcript and compact LLM memory export.\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [_format_transcript(conv)],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import json\n",
                f"memory = {json.dumps(compact, ensure_ascii=False, indent=2)}\n",
                "print(json.dumps(memory, ensure_ascii=False, indent=2))\n",
            ],
        },
    ]
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(notebook, ensure_ascii=False, indent=2)


def _write_session_report(bundle_dir: str, conv: Conversation, bundle: dict) -> str:
    report_path = os.path.join(bundle_dir, "session_report.html")
    messages = "\n".join(
        f"<section><h3>{str(message.get('role', 'unknown')).title()}</h3><pre>{str(message.get('content', ''))}</pre></section>"
        for message in conv.messages
    )
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{conv.metadata.get('title') or conv.id}</title>
    <style>
      body {{ background: #070707; color: #f4eaea; font-family: Arial, sans-serif; padding: 24px; }}
      h1, h2, h3 {{ color: #ff838b; }}
      pre {{ white-space: pre-wrap; background: #050505; border: 1px solid #3a1717; border-radius: 8px; padding: 12px; }}
      section {{ margin: 16px 0; }}
    </style>
  </head>
  <body>
    <h1>{conv.metadata.get('title') or conv.id}</h1>
    <h2>Bundle Manifest</h2>
    <pre>{json.dumps(bundle, ensure_ascii=False, indent=2)}</pre>
    <h2>Conversation</h2>
    {messages}
  </body>
</html>"""
    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write(html)
    return report_path


def _export_bundle(conv: Conversation, password: str = "") -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base_name = f"{_safe_filename(conv.id)}-{stamp}"
    session_dir = _safe_join(BUNDLE_DIR, base_name)
    os.makedirs(session_dir, exist_ok=True)
    human_path = os.path.join(session_dir, f"{base_name}-human.txt")
    compact_path = os.path.join(session_dir, f"{base_name}-llm.json")

    with open(human_path, "w", encoding="utf-8") as human_file:
        human_file.write(_format_transcript(conv))
    with open(compact_path, "w", encoding="utf-8") as compact_file:
        json.dump(_compact_conversation(conv), compact_file, ensure_ascii=False, separators=(",", ":"))

    copied_images = []
    for image in conv.metadata.get("images", []) if isinstance(conv.metadata.get("images"), list) else []:
        rel_file = image.get("file")
        if not rel_file:
            continue
        src = _safe_join(BASE_DIR, rel_file)
        if os.path.exists(src):
            images_dir = _safe_join(session_dir, "images")
            os.makedirs(images_dir, exist_ok=True)
            dst = _safe_join(images_dir, os.path.basename(src))
            shutil.copy2(src, dst)
            copied_images.append(os.path.relpath(dst, session_dir).replace("\\", "/"))

    copied_logs = []
    logs_dir = _safe_join(session_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    for name in os.listdir(LOG_DIR):
        if name.endswith(".log"):
            src = os.path.join(LOG_DIR, name)
            dst = _safe_join(logs_dir, name)
            shutil.copy2(src, dst)
            copied_logs.append(os.path.relpath(dst, session_dir).replace("\\", "/"))

    agent_template_file = ""
    if os.path.exists(AGENT_TEMPLATES_FILE):
        agent_template_path = _safe_join(session_dir, "agent_templates.json")
        shutil.copy2(AGENT_TEMPLATES_FILE, agent_template_path)
        agent_template_file = os.path.basename(agent_template_path)

    manifest = {
        "schema": "glikch.session.bundle.v1",
        "conversation_id": conv.id,
        "created": _now_iso(),
        "agent_templates": agent_template_file,
        "human_transcript": os.path.basename(human_path),
        "compact_memory": os.path.basename(compact_path),
        "images": copied_images,
        "logs": copied_logs,
    }
    manifest_path = os.path.join(session_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, ensure_ascii=False, indent=2)
    report_path = _write_session_report(session_dir, conv, manifest)
    zip_base = os.path.join(EXPORT_DIR, base_name)
    zip_path = shutil.make_archive(zip_base, "zip", session_dir)
    secure = bool(password)
    if secure:
        with open(zip_path, "rb") as raw_zip:
            encrypted = _encrypt_bytes(raw_zip.read(), password)
        secure_zip_path = os.path.join(EXPORT_DIR, f"{base_name}-secure.zip")
        with zipfile.ZipFile(secure_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as secure_zip:
            secure_zip.writestr(SECURE_BUNDLE_MARKER, json.dumps({"schema": "glikch.secure.wrapper.v1", "created": _now_iso(), "encrypted_payload": "secure_payload.json"}, ensure_ascii=False, indent=2))
            secure_zip.writestr("secure_payload.json", json.dumps(encrypted, ensure_ascii=False, separators=(",", ":")))
        os.remove(zip_path)
        zip_path = secure_zip_path

    _log_event(
        "info",
        "Conversation exported",
        conversation_id=conv.id,
        bundle_dir=session_dir,
        human_path=human_path,
        compact_path=compact_path,
        zip_path=zip_path,
    )
    return {
        "bundle_dir": session_dir,
        "bundle_zip": zip_path,
        "bundle_zip_file": os.path.basename(zip_path),
        "human_path": human_path,
        "compact_path": compact_path,
        "manifest_path": manifest_path,
        "report_path": report_path,
        "human_file": os.path.basename(human_path),
        "compact_file": os.path.basename(compact_path),
        "secure": secure,
        "token_estimate": _estimate_conversation_tokens(conv),
    }


def _chat_with_lm_studio(messages: list, model: str, temperature: float) -> str:
    _chat_with_lm_studio.last_usage = None
    clean_messages = [
        {"role": msg.get("role", "user"), "content": msg.get("content", "")}
        for msg in messages
        if msg.get("content")
    ]
    selected_model = "" if "{{" in str(model) else (model or DEFAULT_MODEL)

    openai_payload = {
        "messages": clean_messages,
        "temperature": temperature,
        "stream": False,
    }
    if MAX_RESPONSE_TOKENS > 0:
        openai_payload["max_tokens"] = MAX_RESPONSE_TOKENS
    if selected_model:
        openai_payload["model"] = selected_model

    try:
        data = _post_json(f"{LM_STUDIO_URL}/v1/chat/completions", openai_payload)
    except error.HTTPError as exc:
        if exc.code not in (404, 405):
            raise ValueError(_http_error_detail(exc)) from exc
        legacy_prompt = "\n\n".join(
            f"{msg['role']}: {msg['content']}" for msg in clean_messages
        )
        legacy_payload = {
            "input": legacy_prompt,
            "temperature": temperature,
        }
        if selected_model:
            legacy_payload["model"] = selected_model
        data = _post_json(f"{LM_STUDIO_URL}/api/v1/chat", legacy_payload)

    _chat_with_lm_studio.last_usage = data.get("usage") if isinstance(data, dict) else None
    text = _humanize_assistant_text(_extract_assistant_text(data))
    if not text:
        _log_event("error", "LM Studio returned no assistant text", model=model, response_preview=json.dumps(data, ensure_ascii=False)[:2000])
        raise ValueError("LM Studio responded, but no assistant text was found.")
    return text


_chat_with_lm_studio.last_usage = None


def _usage_payload(lm_messages: list, assistant_text: str, saved_messages: list | None = None) -> dict:
    raw_usage = _chat_with_lm_studio.last_usage if isinstance(_chat_with_lm_studio.last_usage, dict) else {}
    completion_details = raw_usage.get("completion_tokens_details") if isinstance(raw_usage.get("completion_tokens_details"), dict) else {}
    reasoning_tokens = int(completion_details.get("reasoning_tokens") or 0)
    raw_prompt = int(raw_usage.get("prompt_tokens") or 0)
    raw_completion = int(raw_usage.get("completion_tokens") or 0)
    raw_total = int(raw_usage.get("total_tokens") or 0)
    prompt_tokens = raw_prompt if raw_prompt > 0 else _estimate_tokens_messages(lm_messages)
    completion_tokens = raw_completion if raw_completion > 0 else max(reasoning_tokens, _estimate_tokens_text(assistant_text))
    request_total = raw_total if raw_total > 0 else (prompt_tokens + completion_tokens)
    context_tokens = _estimate_tokens_messages(saved_messages or lm_messages)
    total_tokens = max(request_total, context_tokens + completion_tokens)
    usage_source = "lm-studio" if raw_total > 0 else "estimated"
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "request_total_tokens": request_total,
        "context_tokens": context_tokens,
        "reasoning_tokens": reasoning_tokens,
        "usage_source": usage_source,
        "remaining_tokens": max(0, _token_window() - total_tokens),
        "percent_used": round(min(100, (total_tokens / _token_window()) * 100), 2) if _token_window() else 0,
    }


def _capture_chat(conversation_id: str, title: str, model: str, messages: list) -> Conversation:
    conv = Conversation(
        id=conversation_id,
        metadata={
            "title": title or "LM Studio Chat",
            "created": _now_iso(),
            "participants": ["user", "assistant"],
            "model": model or DEFAULT_MODEL or "LM Studio",
        },
        messages=messages,
    )
    save_conversation(conv)
    return conv

@app.route("/")
@login_required
def index():
    query = request.args.get("q", "").strip()
    show_expired = request.args.get("expired", "") == "1"
    if query:
        items = search_conversations(query, include_expired=show_expired)
    else:
        items = list_conversations(include_expired=show_expired)
    return render_template(
        "index.html",
        conversations=items,
        q=query,
        show_expired=show_expired,
    )


@app.route("/chat")
@login_required
def chat():
    return render_template(
        "chat.html",
        lm_studio_url=LM_STUDIO_URL,
        default_model=DEFAULT_MODEL,
        ui_settings=_load_ui_settings(),
    )

@app.route("/conversation/new", methods=["GET", "POST"])
@login_required
def create_conversation():
    if request.method == "POST":
        conv_id = request.form.get("id", "").strip()
        title = request.form.get("title", "").strip()
        created = request.form.get("created", "").strip()
        expires_at = request.form.get("expires_at", "").strip() or None
        participants = [p.strip() for p in request.form.get("participants", "").split(",") if p.strip()]
        messages_raw = request.form.get("messages", "[]")
        try:
            messages = json.loads(messages_raw)
            if not isinstance(messages, list):
                raise ValueError("Messages must be a JSON array")
            conv = Conversation(
                id=conv_id,
                metadata={"title": title, "created": created, "participants": participants, "expires_at": expires_at},
                messages=messages,
            )
            save_conversation(conv)
            flash("Conversation created successfully.")
            return redirect(url_for("conversation", conv_id=conv_id))
        except Exception as exc:
            flash(f"Invalid input: {exc}")
    return render_template("conversation.html", conv=None, messages_json="[]")

@app.route("/conversation/<conv_id>", methods=["GET", "POST"])
@login_required
def conversation(conv_id):
    conv = load_conversation(conv_id)
    if not conv:
        flash("Conversation not found.")
        return redirect(url_for("index"))

    if request.method == "POST":
        if request.form.get("delete"):
            delete_conversation(conv_id)
            flash("Conversation deleted.")
            return redirect(url_for("index"))

        title = request.form.get("title", "").strip()
        created = request.form.get("created", "").strip()
        expires_at = request.form.get("expires_at", "").strip() or None
        participants = [p.strip() for p in request.form.get("participants", "").split(",") if p.strip()]
        messages_raw = request.form.get("messages", "[]")
        try:
            messages = json.loads(messages_raw)
            if not isinstance(messages, list):
                raise ValueError("Messages must be a JSON array")
            updated = Conversation(
                id=conv_id,
                metadata={"title": title, "created": created, "participants": participants, "expires_at": expires_at},
                messages=messages,
            )
            save_conversation(updated)
            flash("Conversation updated successfully.")
            return redirect(url_for("conversation", conv_id=conv_id))
        except Exception as exc:
            flash(f"Invalid input: {exc}")

    return render_template(
        "conversation.html",
        conv=conv,
        messages_json=json.dumps(conv.messages, indent=2, ensure_ascii=False),
    )

@app.route("/conversation/<conv_id>/delete", methods=["POST"])
@login_required
def delete_conversation_route(conv_id):
    deleted = delete_conversation(conv_id)
    flash("Conversation deleted." if deleted else "Conversation not found.")
    return redirect(url_for("index"))

@app.route("/prune", methods=["POST"])
@login_required
def prune_route():
    removed = prune_expired_conversations()
    if removed:
        flash(f"Removed expired conversations: {', '.join(removed)}")
    else:
        flash("No expired conversations found.")
    return redirect(url_for("index"))

@app.route("/api/capture", methods=["POST"])
@login_required
def api_capture():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    try:
        conv = capture_conversation(data)
        return jsonify({"status": "saved", "id": conv.id}), 201
    except Exception as exc:
        _log_event("error", "Capture API failed", error=str(exc))
        return jsonify({"error": str(exc)}), 400


@app.route("/api/models")
@login_required
def api_models():
    try:
        models = _lm_studio_model_ids()
        selected, _, stale = _resolve_lm_studio_model("")
        return jsonify(
            {
                "models": models,
                "default": selected,
                "saved_default": _load_ui_settings().get("default_model") or DEFAULT_MODEL,
                "stale_default": stale,
            }
        )
    except Exception as exc:
        return jsonify({"models": [], "default": DEFAULT_MODEL, "error": str(exc)}), 502


@app.route("/api/status")
@login_required
def api_status():
    try:
        selected, models, stale = _resolve_lm_studio_model("")
        return jsonify(
            {
                "live": True,
                "lm_studio_url": LM_STUDIO_URL,
                "models": models,
                "default_model": selected,
                "stale_default": stale,
                "ram": "Unavailable from LM Studio API",
                "context_window": _token_window(),
                "note": "LM Studio local API reports loaded models, but does not expose reliable per-model RAM allocation.",
            }
        )
    except Exception as exc:
        _log_event("error", "LM Studio status check failed", error=str(exc))
        return jsonify(
            {
                "live": False,
                "lm_studio_url": LM_STUDIO_URL,
                "models": [],
                "ram": "Unknown",
                "context_window": _token_window(),
                "error": str(exc),
            }
        ), 502


@app.route("/api/conversations", methods=["GET", "POST"])
@login_required
def api_conversations():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        conv_id = str(data.get("id") or f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}").strip()
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        metadata.setdefault("title", data.get("title") or conv_id)
        metadata.setdefault("participants", ["user", "assistant"])
        messages = data.get("messages") if isinstance(data.get("messages"), list) else []
        try:
            conv = Conversation(id=conv_id, metadata=metadata, messages=messages)
            save_conversation(conv)
            _log_event("info", "Conversation created", conversation_id=conv_id)
            return jsonify(_conversation_to_dict(conv)), 201
        except Exception as exc:
            _log_event("error", "Conversation create failed", error=str(exc), conversation_id=conv_id)
            return jsonify({"error": str(exc)}), 400

    items = []
    for item in list_conversations(include_expired=True):
        conv = load_conversation(item["id"])
        item["message_count"] = len(conv.messages) if conv else 0
        items.append(item)
    return jsonify({"conversations": items})


@app.route("/api/agent-templates", methods=["GET", "POST", "DELETE"])
@login_required
def api_agent_templates():
    if request.method == "GET":
        return jsonify({"templates": _load_agent_templates()})

    data = request.get_json(silent=True) or {}
    templates = _load_agent_templates()
    if request.method == "DELETE":
        name = str(data.get("name") or "").strip()
        templates = [item for item in templates if item.get("name") != name]
        _save_agent_templates(templates)
        return jsonify({"templates": _load_agent_templates()})

    template = {
        "name": str(data.get("name") or "Unnamed Agent").strip(),
        "mode": str(data.get("mode") or data.get("agent_type") or "Chat").strip(),
        "instruction": str(data.get("instruction") or "").strip(),
        "execution_policy": str(data.get("execution_policy") or "ask").strip(),
        "creator": str(data.get("creator") or "").strip(),
        "email": str(data.get("email") or "").strip(),
    }
    templates = [item for item in templates if item.get("name") != template["name"]]
    templates.append(template)
    _save_agent_templates(templates)
    return jsonify({"templates": _load_agent_templates()})


@app.route("/api/agent-templates/export/<name>")
@login_required
def api_agent_template_export(name):
    target = next((item for item in _load_agent_templates() if item.get("name") == name), None)
    if not target:
        return jsonify({"error": "Agent template not found."}), 404
    payload = {"schema": "glikch.agent.template.v1", "created": _now_iso(), "template": target}
    filename = f"agent-{_safe_filename(name)}.json"
    return Response(json.dumps(payload, ensure_ascii=False, indent=2), mimetype="application/json", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/api/agent-templates/import", methods=["POST"])
@login_required
def api_agent_template_import():
    files = request.files.getlist("files")
    imported = []
    templates = _load_agent_templates()
    for uploaded in files:
        try:
            data = json.loads(uploaded.read().decode("utf-8"))
            template = data.get("template") if isinstance(data, dict) and data.get("schema") == "glikch.agent.template.v1" else data
            if isinstance(template, dict):
                templates.append(template)
                imported.append(template.get("name") or uploaded.filename)
        except Exception as exc:
            _log_event("error", "Agent template import failed", file=uploaded.filename, error=str(exc))
    _save_agent_templates(templates)
    _log_event("info", "Agent templates imported", templates=imported)
    return jsonify({"imported": imported, "templates": _load_agent_templates()})


@app.route("/api/conversations/<conv_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_conversation_detail(conv_id):
    conv = load_conversation(conv_id)
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404

    if request.method == "DELETE":
        deleted = delete_conversation(conv_id)
        _log_event("info", "Conversation deleted", conversation_id=conv_id)
        return jsonify({"deleted": deleted})

    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else conv.metadata
        messages = data.get("messages") if isinstance(data.get("messages"), list) else conv.messages
        updated = Conversation(id=conv_id, metadata=metadata, messages=messages)
        try:
            save_conversation(updated)
            _log_event("info", "Conversation updated", conversation_id=conv_id)
            return jsonify(_conversation_to_dict(updated))
        except Exception as exc:
            _log_event("error", "Conversation update failed", error=str(exc), conversation_id=conv_id)
            return jsonify({"error": str(exc)}), 400

    return jsonify(_conversation_to_dict(conv))


@app.route("/api/export/<conv_id>")
@login_required
def api_export(conv_id):
    conv = load_conversation(conv_id)
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404

    export_format = request.args.get("format", "txt").lower()
    filename = _safe_filename(conv_id)
    if export_format == "json":
        payload = json.dumps(_compact_conversation(conv), ensure_ascii=False, indent=2)
        mimetype = "application/json"
        download_name = f"{filename}-llm.json"
    elif export_format == "ipynb":
        payload = _build_notebook(conv)
        mimetype = "application/x-ipynb+json"
        download_name = f"{filename}.ipynb"
    elif export_format == "csv":
        rows = ["role,timestamp,content"]
        for message in conv.messages:
            role = str(message.get("role", "")).replace('"', '""')
            timestamp = str(message.get("timestamp", "")).replace('"', '""')
            content = str(message.get("content", "")).replace('"', '""')
            rows.append(f'"{role}","{timestamp}","{content}"')
        payload = "\n".join(rows) + "\n"
        mimetype = "text/csv"
        download_name = f"{filename}.csv"
    else:
        payload = _format_transcript(conv)
        mimetype = "text/plain; charset=utf-8"
        download_name = f"{filename}-human.txt"

    _log_event("info", "Conversation downloaded", conversation_id=conv_id, format=export_format)
    return Response(
        payload,
        mimetype=mimetype,
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )


@app.route("/api/download-export/<filename>")
@login_required
def api_download_export(filename):
    safe_name = secure_filename(filename)
    if not safe_name or not safe_name.endswith(".zip"):
        return jsonify({"error": "Invalid export file."}), 400
    path = _safe_join(EXPORT_DIR, safe_name)
    if not os.path.exists(path):
        return jsonify({"error": "Export file not found."}), 404
    return send_from_directory(EXPORT_DIR, safe_name, as_attachment=True)


@app.route("/api/compress-reset/<conv_id>", methods=["POST"])
@login_required
def api_compress_reset(conv_id):
    conv = load_conversation(conv_id)
    if not conv:
        return jsonify({"error": "Conversation not found."}), 404
    data = request.get_json(silent=True) or {}
    password = str(data.get("password") or "")
    bundle = _export_bundle(conv, password=password)
    return jsonify(
        {
            "status": "exported",
            "reset_instruction": "Clear the browser chat history and start the next session from the compact LLM JSON file.",
            **bundle,
        }
    )


@app.route("/api/load-latest-compressed", methods=["POST"])
@login_required
def api_load_latest_compressed():
    path = _latest_compact_export_path()
    if not path:
        return jsonify({"error": "No compressed LLM export found yet."}), 404

    import_id = f"latest-compressed-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    with open(path, "r", encoding="utf-8") as compact_file:
        compact = json.load(compact_file)
    payload = {
        "import_id": import_id,
        "created": _now_iso(),
        "files": [
            {
                "filename": os.path.basename(path),
                "extension": ".json",
                "detected_format": compact.get("schema", "json"),
                "status": "detected",
                "messages": [],
                "compact_memory": compact,
                "text_preview": json.dumps(compact, ensure_ascii=False, indent=2)[:2000],
                "error": None,
                "stored_path": path,
            }
        ],
    }
    with open(_import_payload_path(import_id), "w", encoding="utf-8") as import_file:
        json.dump(payload, import_file, ensure_ascii=False, indent=2)
    _log_event("info", "Latest compressed export loaded", import_id=import_id, path=path)
    return jsonify({"import": payload, "compact": _compact_import_payload(payload)})




@app.route("/api/ui-settings", methods=["GET", "POST"])
@login_required
def api_ui_settings():
    if request.method == "GET":
        return jsonify({"settings": _load_ui_settings()})
    data = request.get_json(silent=True) or {}
    return jsonify({"settings": _save_ui_settings(data)})


@app.route("/api/ui-settings/wallpaper", methods=["POST"])
@login_required
def api_ui_settings_wallpaper():
    kind = request.form.get("kind", "").strip()
    if kind not in {"login", "app", "logo"}:
        return jsonify({"error": "Wallpaper kind must be login, app, or logo."}), 400
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "No wallpaper file uploaded."}), 400
    extension = os.path.splitext(uploaded.filename)[1].lower()
    if extension not in IMAGE_EXTENSIONS:
        return jsonify({"error": "Wallpaper must be a supported image file."}), 400
    safe_name = f"{kind}-asset{extension}" if kind == "logo" else f"{kind}-wallpaper{extension}"
    target = _safe_join(USER_ASSET_DIR, safe_name)
    uploaded.save(target)
    url = url_for("static", filename=f"user/{safe_name}")
    settings = _load_ui_settings()
    if kind == "logo":
        settings["app_logo"] = url
    else:
        settings[f"{kind}_wallpaper"] = url
    _save_ui_settings(settings)
    _log_event("info", "UI wallpaper saved", kind=kind, file=safe_name)
    return jsonify({"url": url, "settings": settings})


@app.route("/api/open-memory-folder", methods=["POST"])
@login_required
def api_open_memory_folder():
    try:
        if os.name == "nt":
            os.startfile(CONV_DIR)
        else:
            subprocess.Popen(["xdg-open", CONV_DIR])
        _log_event("info", "Memory folder opened", path=CONV_DIR)
        return jsonify({"opened": True, "path": CONV_DIR})
    except Exception as exc:
        _log_event("error", "Open memory folder failed", error=str(exc), path=CONV_DIR)
        return jsonify({"opened": False, "path": CONV_DIR, "warning": str(exc)}), 200


@app.route("/api/reset-ui", methods=["POST"])
@login_required
def api_reset_ui():
    _log_event("info", "Browser UI reset requested")
    return jsonify({"status": "reset", "message": "Reload the page to reset browser state."})


@app.route("/api/developer/source")
@login_required
def api_developer_source():
    with open(__file__, "r", encoding="utf-8") as source_file:
        return Response(source_file.read(), mimetype="text/plain; charset=utf-8")


@app.route("/api/logs")
@login_required
def api_logs():
    logs = []
    for name in sorted(os.listdir(LOG_DIR), reverse=True):
        if name.endswith(".log"):
            path = os.path.join(LOG_DIR, name)
            logs.append({"date": name[:-4], "file": name, "size": os.path.getsize(path)})
    return jsonify({"logs": logs})


@app.route("/api/logs/<log_date>/export")
@login_required
def api_log_export(log_date):
    safe_date = _safe_filename(log_date)
    path = os.path.join(LOG_DIR, f"{safe_date}.log")
    if not os.path.exists(path):
        return jsonify({"error": "Log not found."}), 404
    lines = []
    with open(path, "r", encoding="utf-8") as log_file:
        for raw in log_file:
            try:
                entry = json.loads(raw)
                context = json.dumps(entry.get("context", {}), ensure_ascii=False, indent=2)
                lines.append(f"[{entry.get('timestamp')}] {entry.get('level')}: {entry.get('message')}\n{context}")
            except Exception:
                lines.append(raw.strip())
    payload = "\n\n".join(lines) + "\n"
    return Response(payload, mimetype="text/plain; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=glikch-log-{safe_date}.txt"})


@app.route("/api/logs/import", methods=["POST"])
@login_required
def api_log_import():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No log file uploaded."}), 400
    imported = []
    for uploaded in files:
        original = uploaded.filename or "uploaded-log.txt"
        if os.path.splitext(original)[1].lower() not in {".log", ".txt", ".json"}:
            continue
        safe_name = f"imported-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{secure_filename(os.path.basename(original))}"
        target = _safe_join(LOG_DIR, safe_name)
        uploaded.save(target)
        imported.append(safe_name)
    _log_event("info", "Log data imported", files=imported)
    return jsonify({"imported": imported})


def _default_emotion_presets() -> list[str]:
    return [
        "What's up?",
        "Hey! What's on your mind?",
        "Did you drink water today?",
        "How is Geoff and/or your friends and family doing today?",
        "What's on your mind?",
        "Have you done your school work?",
        "Have you called your father or Mother today?",
        "Have you checked your assignments?",
    ]


@app.route("/api/emotion-presets", methods=["GET", "POST"])
@login_required
def api_emotion_presets():
    if request.method == "GET":
        if os.path.exists(EMOTION_PRESETS_FILE):
            with open(EMOTION_PRESETS_FILE, "r", encoding="utf-8") as preset_file:
                data = json.load(preset_file)
            presets = data.get("presets") if isinstance(data, dict) else data
            return jsonify({"presets": presets if isinstance(presets, list) else _default_emotion_presets()})
        return jsonify({"presets": _default_emotion_presets()})
    files = request.files.getlist("files")
    presets = []
    for uploaded in files:
        try:
            text = uploaded.read().decode("utf-8", errors="replace")
            if uploaded.filename and uploaded.filename.lower().endswith(".json"):
                data = json.loads(text)
                raw = data.get("presets") if isinstance(data, dict) else data
                if isinstance(raw, list):
                    presets.extend(str(item).strip() for item in raw if str(item).strip())
            else:
                presets.extend(line.strip() for line in text.splitlines() if line.strip())
        except Exception as exc:
            _log_event("error", "Emotion preset import failed", file=uploaded.filename, error=str(exc))
    clean = []
    seen = set()
    for item in [*_default_emotion_presets(), *presets]:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            clean.append(item[:240])
    os.makedirs(os.path.dirname(EMOTION_PRESETS_FILE), exist_ok=True)
    with open(EMOTION_PRESETS_FILE, "w", encoding="utf-8") as preset_file:
        json.dump({"schema": "glikch.emotion.presets.v1", "updated": _now_iso(), "presets": clean}, preset_file, ensure_ascii=False, indent=2)
    _log_event("info", "Emotion presets loaded", count=len(clean))
    return jsonify({"presets": clean})


TASKS_FILE = os.path.join(BASE_DIR, "docs", "calendar_tasks.json")




@app.route("/api/extensions", methods=["GET", "POST", "DELETE"])
@login_required
def api_extensions():
    def load_extensions() -> list[dict]:
        if os.path.exists(EXTENSIONS_FILE):
            with open(EXTENSIONS_FILE, "r", encoding="utf-8") as extension_file:
                data = json.load(extension_file)
            items = data.get("extensions") if isinstance(data, dict) else data
            return items if isinstance(items, list) else []
        return []

    items = load_extensions()
    if request.method == "GET":
        return jsonify({"schema": "glikch.nexuz.extensions.v1", "extensions": items})
    if request.method == "DELETE":
        data = request.get_json(silent=True) or {}
        extension_id = str(data.get("id") or "")
        items = [item for item in items if item.get("id") != extension_id]
    else:
        data = request.get_json(silent=True) or {}
        extension_id = str(data.get("id") or "").strip() or f"ext-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        clean = {
            "id": extension_id,
            "name": str(data.get("name") or "Unnamed Extension").strip()[:120],
            "developer": str(data.get("developer") or "").strip()[:120],
            "purpose": str(data.get("purpose") or "").strip()[:1000],
            "business": str(data.get("business") or "").strip()[:160],
            "status": str(data.get("status") or "draft").strip()[:40],
            "created": data.get("created") or _now_iso(),
            "updated": _now_iso(),
        }
        items = [item for item in items if item.get("id") != extension_id]
        items.insert(0, clean)
    os.makedirs(os.path.dirname(EXTENSIONS_FILE), exist_ok=True)
    with open(EXTENSIONS_FILE, "w", encoding="utf-8") as extension_file:
        json.dump({"schema": "glikch.nexuz.extensions.v1", "updated": _now_iso(), "extensions": items}, extension_file, ensure_ascii=False, indent=2)
    _log_event("info", "Extensions updated", count=len(items))
    return jsonify({"extensions": items})


@app.route("/api/tasks", methods=["GET", "POST"])
@login_required
def api_tasks():
    if request.method == "GET":
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, "r", encoding="utf-8") as task_file:
                return jsonify(json.load(task_file))
        return jsonify({"schema": "glikch.calendar.tasks.v1", "tasks": []})
    data = request.get_json(silent=True) or {}
    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as task_file:
        json.dump({"schema": "glikch.calendar.tasks.v1", "updated": _now_iso(), "tasks": tasks}, task_file, ensure_ascii=False, indent=2)
    _log_event("info", "Calendar tasks saved", count=len(tasks))
    return jsonify({"saved": True, "count": len(tasks)})


@app.route("/api/logs/<log_date>")
@login_required
def api_log_detail(log_date):
    safe_date = _safe_filename(log_date)
    path = os.path.join(LOG_DIR, f"{safe_date}.log")
    if not os.path.exists(path):
        return jsonify({"error": "Log not found."}), 404
    with open(path, "r", encoding="utf-8") as log_file:
        return Response(log_file.read(), mimetype="text/plain; charset=utf-8")


@app.route("/api/import-memory", methods=["POST"])
@login_required
def api_import_memory():
    files = request.files.getlist("files")
    import_password = request.form.get("password", "")
    if not files:
        return jsonify({"error": "No files uploaded."}), 400

    import_id = f"import-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    import_dir = os.path.join(IMPORT_DIR, import_id)
    os.makedirs(import_dir, exist_ok=True)
    detected_files = []

    for uploaded in files:
        original_name = uploaded.filename or "uploaded-file"
        if not _should_import_project_file(original_name, getattr(uploaded, "content_length", 0) or 0):
            detected_files.append(
                {
                    "filename": original_name,
                    "extension": os.path.splitext(original_name)[1].lower() or "unknown",
                    "detected_format": "skipped",
                    "status": "skipped",
                    "messages": [],
                    "compact_memory": None,
                    "text_preview": "",
                    "image_ref": None,
                    "error": "Skipped by project import safety filter.",
                }
            )
            continue
        filename = secure_filename(os.path.basename(original_name)) or "uploaded-file"
        file_path = os.path.join(import_dir, filename)
        uploaded.save(file_path)
        if os.path.splitext(original_name)[1].lower() == ".zip":
            try:
                detected_files.extend(_extract_zip_import(file_path, import_dir, original_name, password=import_password))
            except Exception as exc:
                if "password" in str(exc).lower() or "secure bundle" in str(exc).lower():
                    _log_event("error", "Secure bundle import failed", file=original_name, error=str(exc))
                    return jsonify({"error": str(exc), "secure_bundle": True}), 400
                detected_files.append(
                    {
                        "filename": original_name,
                        "extension": ".zip",
                        "detected_format": "zip-archive",
                        "status": "failed",
                        "messages": [],
                        "compact_memory": None,
                        "text_preview": "",
                        "image_ref": None,
                        "error": str(exc),
                        "stored_path": file_path,
                    }
                )
        else:
            detected = _detect_import(file_path, original_name)
            detected["stored_path"] = file_path
            detected_files.append(detected)

    payload = {
        "import_id": import_id,
        "created": _now_iso(),
        "files": detected_files,
    }
    with open(_import_payload_path(import_id), "w", encoding="utf-8") as import_file:
        json.dump(payload, import_file, ensure_ascii=False, indent=2)

    _log_event(
        "info",
        "Import detected",
        import_id=import_id,
        files=[{"name": item["filename"], "format": item["detected_format"], "status": item["status"]} for item in detected_files],
    )
    return jsonify({"import": payload, "compact": _compact_import_payload(payload)})


@app.route("/api/apply-import/<import_id>", methods=["POST"])
@login_required
def api_apply_import(import_id):
    path = _import_payload_path(import_id)
    if not os.path.exists(path):
        return jsonify({"error": "Import not found."}), 404

    data = request.get_json(silent=True) or {}
    requested_model = str(data.get("model") or "").strip()
    model, _, stale_model = _resolve_lm_studio_model(requested_model)
    if stale_model:
        _log_event("error", "Requested import model was not loaded; using loaded model", requested=requested_model, resolved=model)
    conversation_id = str(data.get("conversation_id") or f"applied-{import_id}").strip()
    title = str(data.get("title") or "Imported Memory Context").strip()
    mode = str(data.get("mode") or "Chat").strip()

    with open(path, "r", encoding="utf-8") as import_file:
        import_payload = json.load(import_file)
    compact = _compact_import_payload(import_payload)
    context_text = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    instruction = (
        f"You are running in {mode} mode. The following compact memory payload is context "
        "from an uploaded or exported prior session. Acknowledge what project/task context "
        "you now have in 5 concise bullets. Do not repeat the full payload.\n\n"
        f"{context_text}"
    )

    try:
        assistant_text = _chat_with_lm_studio(
            [
                {
                    "role": "system",
                    "content": "You restore compact project memory and continue work with minimal token usage.",
                },
                {"role": "user", "content": instruction},
            ],
            model,
            0.2,
        )
        messages = [
            {"role": "user", "content": f"Loaded readable import context:\n{context_text}", "timestamp": _now_iso()},
            {"role": "assistant", "content": assistant_text, "timestamp": _now_iso()},
        ]
        _capture_chat(conversation_id, title, model, messages)
        _log_event("info", "Import applied to LLM", import_id=import_id, conversation_id=conversation_id, model=model)
        return jsonify(
            {
                "conversation_id": conversation_id,
                "message": {"role": "assistant", "content": assistant_text},
                "compact": compact,
                "usage": _chat_with_lm_studio.last_usage or {"prompt_tokens": _estimate_tokens_text(context_text), "completion_tokens": _estimate_tokens_text(assistant_text), "total_tokens": _estimate_tokens_text(context_text) + _estimate_tokens_text(assistant_text)},
            }
        )
    except Exception as exc:
        _log_event("error", "Apply import to LLM failed", import_id=import_id, error=str(exc), model=model)
        return jsonify({"error": str(exc), "import_id": import_id}), 502


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get("message", "")).strip()
    history = data.get("history") or []
    if not isinstance(history, list):
        return jsonify({"error": "History must be a list."}), 400
    loaded_context = data.get("loaded_context")
    attachments = data.get("attachments") if isinstance(data.get("attachments"), list) else []
    if not user_message and not attachments:
        return jsonify({"error": "Message or attachment is required."}), 400
    saved_images = []

    conversation_id = str(data.get("conversation_id") or "").strip()
    if not conversation_id:
        conversation_id = f"lmstudio-chat-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    requested_model = str(data.get("model") or "").strip()
    model, _, stale_model = _resolve_lm_studio_model(requested_model)
    if stale_model:
        _log_event("error", "Requested chat model was not loaded; using loaded model", requested=requested_model, resolved=model)
    title = str(data.get("title") or "LM Studio Chat").strip()
    mode = str(data.get("mode") or "Chat").strip()
    agent_id = str(data.get("agent_id") or "default-agent").strip()
    execution_policy = str(data.get("execution_policy") or "ask").strip()
    try:
        temperature = float(data.get("temperature", 0.7))
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = max(0.0, min(2.0, temperature))

    timestamp = _now_iso()
    saved_history = [
        {
            "role": item.get("role", "user"),
            "content": str(item.get("content", "")),
            "timestamp": item.get("timestamp") or timestamp,
        }
        for item in history
        if isinstance(item, dict) and str(item.get("content", "")).strip()
    ]
    # Keep LM Studio responsive by replaying only the recent turn window into the model.
    # The full browser conversation remains in saved_history and is still persisted below.
    safe_history = saved_history[-12:]
    if attachments:
        try:
            for item in attachments:
                if not isinstance(item, dict):
                    continue
                data_url = item.get("data_url")
                if isinstance(data_url, str):
                    saved_images.append(_save_data_url_image(data_url, conversation_id, str(item.get("name", "image"))))
        except Exception as exc:
            _log_event("error", "Image attachment save failed", error=str(exc), conversation_id=conversation_id)
            return jsonify({"error": f"Image attachment could not be saved: {exc}", "conversation_id": conversation_id}), 400
    stored_user_content = user_message
    if saved_images:
        stored_user_content = (
            user_message
            + "\n\n[Attached images]\n"
            + "\n".join(f"- {image['name']} -> {image['file']}" for image in saved_images)
        )
    messages = saved_history + [{"role": "user", "content": stored_user_content, "timestamp": timestamp}]
    lm_messages = list(messages)
    if attachments:
        image_content = [{"type": "text", "text": user_message or "Please analyze the attached image context."}]
        for item in attachments:
            if not isinstance(item, dict):
                continue
            data_url = item.get("data_url")
            if isinstance(data_url, str) and data_url.startswith("data:image/"):
                image_content.append({"type": "image_url", "image_url": {"url": data_url}})
        lm_messages = safe_history + [{"role": "user", "content": image_content}]
    if isinstance(loaded_context, dict) and loaded_context.get("context"):
        lm_messages = [
            {
                "role": "system",
                "content": (
                    "Use this compact imported memory as private context for the conversation. "
                    "When asked what context is loaded, summarize it in plain English and do not dump raw JSON. "
                    "If project files are present, inspect the included filenames and previews before proposing code. "
                    "Respect the selected execution policy; ask before destructive edits or command execution.\n\n"
                    + str(loaded_context.get("context", ""))[:12000]
                ),
            },
            *lm_messages,
        ]
    lm_messages = [
        {
            "role": "system",
            "content": (
                f"Active GLIKCH agent: {agent_id}. Mode: {mode}. Execution policy: {execution_policy}. "
                "Return human-readable answers and never dump raw JSON unless the user explicitly asks for JSON. "
                "For open-ended learning, setup, research, documentation, troubleshooting, or developer questions, "
                "respond with substantial detail: use clear headings, at least five useful paragraphs or sections when appropriate, "
                "step-by-step setup guidance, examples, gotchas, security notes, practical next actions, and an offer for what to help with next. "
                "Be generous, interactive, and willing to solve the user's full problem unless the request is unsafe. "
                "For simple greetings or confirmations, stay concise but invite the next useful step. "
                "For code changes, provide complete copyable code blocks or unified diffs with filenames."
            ),
        },
        *lm_messages,
    ]

    try:
        assistant_text = _chat_with_lm_studio(lm_messages, model, temperature)
    except Exception as exc:
        if saved_images:
            assistant_text = (
                "The image was saved and linked to this conversation, but the selected LM Studio model "
                "or API endpoint did not return a readable vision response.\n\n"
                "Saved image files:\n"
                + "\n".join(f"- {image['name']} -> {image['file']}" for image in saved_images)
                + "\n\nSwitch to a vision-capable model in the model dropdown, then resend or import the saved image."
            )
            messages.append({"role": "assistant", "content": assistant_text, "timestamp": _now_iso()})
            conv = _capture_chat(conversation_id, title, model, messages)
            conv.metadata["mode"] = mode
            conv.metadata["agent_id"] = agent_id
            conv.metadata["execution_policy"] = execution_policy
            conv.metadata["images"] = saved_images
            conv.metadata["vision_error"] = str(exc)
            save_conversation(conv)
            _log_event("error", "Vision chat failed but image was saved", error=str(exc), conversation_id=conversation_id, model=model)
            return jsonify(
                {
                    "conversation_id": conversation_id,
                    "message": {"role": "assistant", "content": assistant_text},
                    "captured": True,
                    "warning": str(exc),
                    "usage": _usage_payload(lm_messages, assistant_text, messages),
                }
            )
        assistant_text = (
            "LM Studio could not complete that turn, but NEXUZ captured the request and stayed ready.\n\n"
            f"Reason: {exc}\n\n"
            "Next step: confirm the selected model is loaded and has enough VRAM/RAM, then retry or switch to a smaller loaded model."
        )
        messages.append({"role": "assistant", "content": assistant_text, "timestamp": _now_iso()})
        conv = _capture_chat(conversation_id, title, model, messages)
        conv.metadata["mode"] = mode
        conv.metadata["agent_id"] = agent_id
        conv.metadata["execution_policy"] = execution_policy
        conv.metadata["lm_studio_error"] = str(exc)
        save_conversation(conv)
        _log_event("error", "Chat request failed but turn was preserved", error=str(exc), conversation_id=conversation_id, model=model)
        return jsonify(
            {
                "conversation_id": conversation_id,
                "message": {"role": "assistant", "content": assistant_text},
                "captured": True,
                "warning": str(exc),
                "usage": _usage_payload(lm_messages, assistant_text, messages),
            }
        )

    try:
        messages.append({"role": "assistant", "content": assistant_text, "timestamp": _now_iso()})
        conv = _capture_chat(conversation_id, title, model, messages)
        conv.metadata["mode"] = mode
        conv.metadata["agent_id"] = agent_id
        conv.metadata["execution_policy"] = execution_policy
        if saved_images:
            conv.metadata["images"] = saved_images
        save_conversation(conv)
        _log_event("info", "Chat turn captured", conversation_id=conversation_id, model=model)
        return jsonify(
            {
                "conversation_id": conversation_id,
                "message": {"role": "assistant", "content": assistant_text},
                "captured": True,
                "usage": _usage_payload(lm_messages, assistant_text, messages),
            }
        )
    except Exception as exc:
        _log_event("error", "Chat request failed", error=str(exc), conversation_id=conversation_id, model=model)
        return jsonify({"error": str(exc), "conversation_id": conversation_id}), 502
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
