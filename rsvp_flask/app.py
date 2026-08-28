import csv
import io
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from openpyxl import Workbook
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB per request (videos)
RESPONSES_DIR = Path(os.environ.get("RSVP_RESPONSES_DIR", "."))
RESPONSES_FILE = RESPONSES_DIR / "responses.csv"
MEAL_RESPONSES_FILE = RESPONSES_DIR / "meal-responses.csv"
PHOTOS_DIR = RESPONSES_DIR / "photos"
THUMBS_DIR = PHOTOS_DIR / "thumbs"
PHOTOS_META_FILE = RESPONSES_DIR / "photos.json"
MEMORIES_DIR = RESPONSES_DIR / "memories"
MEMORIES_THUMBS_DIR = MEMORIES_DIR / "thumbs"
MEMORIES_META_FILE = RESPONSES_DIR / "memories.json"
SITE_BASE_URL = os.environ.get("WEDDING_SITE_URL", "https://www.ryanandcarlygethitched.com")

RSVP_NOTIFY_EMAIL = os.environ.get("RSVP_NOTIFY_EMAIL", "").strip()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RSVP_FROM_EMAIL = os.environ.get("RSVP_FROM_EMAIL", "onboarding@resend.dev").strip()
PHOTO_ADMIN_PASSWORD = os.environ.get("PHOTO_ADMIN_PASSWORD", "").strip()

PHOTO_MAX_EDGE = 1920
THUMB_MAX_EDGE = 480
PHOTO_JPEG_QUALITY = 85
THUMB_JPEG_QUALITY = 80
MAX_PHOTOS_PER_UPLOAD = 12
ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif"}
MAX_MEMORY_MESSAGE = 2000
MAX_VIDEO_BYTES = 80 * 1024 * 1024
ALLOWED_MEMORY_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v", ".mpeg", ".mpg"}
VIDEO_MIMETYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".m4v": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
}


def ensure_responses_file():
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    path = RESPONSES_FILE
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp", "name", "email", "additional_guests", "attending",
                "weekend_scope", "weekend_other", "meal_choices", "meal_other",
                "accommodation_plan", "accommodation_other",
                "open_to_sharing", "prefer_own_room", "interested_glamping",
                "wedding_party", "bunking_with",
            ])
    return path


def ensure_meal_responses_file():
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    path = MEAL_RESPONSES_FILE
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp", "name", "email", "additional_guests", "meal_choices",
                "dietary_restrictions", "staying_plan", "off_site_address",
                "taxi_service", "song_request", "weekend_notes",
            ])
    return path


def ensure_photos_dirs():
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    if not PHOTOS_META_FILE.exists():
        PHOTOS_META_FILE.write_text("[]", encoding="utf-8")
    return PHOTOS_DIR


def _load_photo_meta():
    ensure_photos_dirs()
    try:
        data = json.loads(PHOTOS_META_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_photo_meta(entries):
    ensure_photos_dirs()
    PHOTOS_META_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _request_base_url():
    base = request.host_url.rstrip("/")
    if request.headers.get("X-Forwarded-Proto") == "https" and base.startswith("http://"):
        base = "https://" + base[7:]
    return base


def _photo_urls(photo_id):
    base = _request_base_url()
    return {
        "id": photo_id,
        "url": f"{base}/photos/file/{photo_id}.jpg",
        "thumb_url": f"{base}/photos/thumb/{photo_id}.jpg",
    }


def _process_and_save_image(file_storage, uploader_name):
    filename = (file_storage.filename or "").strip()
    ext = Path(filename).suffix.lower()
    if ext and ext not in ALLOWED_PHOTO_EXTS:
        raise ValueError(f"Unsupported file type: {ext}")

    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty file")

    try:
        img = Image.open(io.BytesIO(raw))
    except UnidentifiedImageError as exc:
        raise ValueError("Could not read image") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        alpha = img.split()[-1] if img.mode in ("RGBA", "LA") else None
        background.paste(img, mask=alpha)
        img = background
    else:
        img = img.convert("RGB")

    photo_id = uuid.uuid4().hex
    full_path = PHOTOS_DIR / f"{photo_id}.jpg"
    thumb_path = THUMBS_DIR / f"{photo_id}.jpg"

    full = img.copy()
    full.thumbnail((PHOTO_MAX_EDGE, PHOTO_MAX_EDGE), Image.Resampling.LANCZOS)
    full.save(full_path, format="JPEG", quality=PHOTO_JPEG_QUALITY, optimize=True)

    thumb = img.copy()
    thumb.thumbnail((THUMB_MAX_EDGE, THUMB_MAX_EDGE), Image.Resampling.LANCZOS)
    thumb.save(thumb_path, format="JPEG", quality=THUMB_JPEG_QUALITY, optimize=True)

    entry = {
        "id": photo_id,
        "uploader": uploader_name,
        "original_name": filename,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return entry


def _parse_meal_choices(form):
    meal_names = {
        "chicken": "chicken",
        "beef": "beef",
        "fish": "fish",
        "vegetarian": "vegetarian",
        "vegan": "vegan",
    }
    parts = []
    for key, label in meal_names.items():
        count = int(form.get(f"meal_count_{key}") or "0") or 0
        if count > 0:
            parts.append(f"{count} {label}")
    return ", ".join(parts) if parts else ""


def _parse_guest_meals(form):
    names = form.getlist("guest_meal_name")
    choices = form.getlist("guest_meal_choice")
    child_ages = form.getlist("guest_meal_child_age")
    under_threes = form.getlist("guest_meal_under_three")
    labels = {
        "vegetarian_ravioli": "Vegetarian Ravioli (V)",
        "poulet_du_nord": "Poulet du Nord",
        "braised_short_rib": "Braised Short Rib (GF)",
        "ham_cheddar_toasty": "Grilled Ham & Cheddar Toasty",
        "chicken_strips": "Chicken Strips",
        "grilled_chicken_strips": "Grilled Chicken Strips",
        "buddy_burger": "Buddy Burger",
        "fish_goujons_chips": "Fish Goujons & Chips",
        "mac_n_cheese": "Creamy Mac N'Cheese",
    }
    if not child_ages:
        child_ages = ["no"] * len(names)
    if not under_threes:
        under_threes = ["no"] * len(names)
    parts = []
    for name, choice, child_age, under_three in zip(names, choices, child_ages, under_threes):
        name = (name or "").strip()
        choice = (choice or "").strip().lower()
        child_age = (child_age or "").strip().lower()
        under_three = (under_three or "").strip().lower()
        if not name:
            continue
        if under_three == "yes":
            parts.append(f"{name}: no dinner (<3 years)")
            continue
        if choice:
            entry = f"{name}: {labels.get(choice, choice)}"
            if child_age == "yes":
                entry += " (3-10 years)"
            parts.append(entry)
    return "; ".join(parts) if parts else ""


def _send_email(subject, body):
    if not RSVP_NOTIFY_EMAIL:
        app.logger.warning("Email not sent: RSVP_NOTIFY_EMAIL not set.")
        return
    if not RESEND_API_KEY:
        app.logger.warning("Email not sent: RESEND_API_KEY not set.")
        return
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        resend.Emails.send({
            "from": RSVP_FROM_EMAIL,
            "to": [RSVP_NOTIFY_EMAIL],
            "subject": subject,
            "text": body,
        })
        app.logger.info("Notification email sent via Resend")
    except Exception as e:
        app.logger.error("Resend email failed: %s", e, exc_info=True)


def _send_rsvp_notification(name, email, attending, weekend_scope, meal_choices, accommodation_plan):
    data_url = os.environ.get("RSVP_BACKEND_URL", "").rstrip("/") or "(set RSVP_BACKEND_URL)"
    subject = f"New RSVP: {name}"
    body = f"""Someone just submitted an RSVP!

Name: {name}
Email: {email or "(not provided)"}
Attending: {attending or "(not provided)"}
Weekend plans: {weekend_scope or "(not provided)"}
Meal choices: {meal_choices or "(none)"}
Accommodation: {accommodation_plan or "(not provided)"}

View all responses: {data_url}/data
"""
    _send_email(subject, body)


def _send_meal_notification(
    name, email, additional_guests, meal_choices, dietary_restrictions,
    staying_plan, off_site_address, taxi_service, song_request, weekend_notes,
):
    data_url = os.environ.get("RSVP_BACKEND_URL", "").rstrip("/") or "(set RSVP_BACKEND_URL)"
    subject = f"New meal selection: {name}"
    body = f"""Someone just submitted a meal selection!

Name: {name}
Email: {email or "(not provided)"}
Additional guests: {additional_guests or "(none)"}
Meal choices: {meal_choices or "(none)"}
Dietary restrictions / allergies: {dietary_restrictions or "(none)"}
Staying: {staying_plan or "(not provided)"}
Off-site address: {off_site_address or "(n/a)"}
Taxi service: {taxi_service or "(n/a)"}
Song request: {song_request or "(none)"}
Other notes: {weekend_notes or "(none)"}

View all meal responses: {data_url}/data
"""
    _send_email(subject, body)


def _send_photo_upload_notification(uploader, count):
    album_url = f"{SITE_BASE_URL.rstrip('/')}/photos.html"
    subject = f"New photo upload: {uploader} ({count})"
    body = f"""Someone just uploaded photos to the wedding album!

Uploader: {uploader}
Photos: {count}

View the album: {album_url}
"""
    _send_email(subject, body)


def ensure_memories_dirs():
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    MEMORIES_DIR.mkdir(parents=True, exist_ok=True)
    MEMORIES_THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORIES_META_FILE.exists():
        MEMORIES_META_FILE.write_text("[]", encoding="utf-8")
    return MEMORIES_DIR


def _load_memory_meta():
    ensure_memories_dirs()
    try:
        data = json.loads(MEMORIES_META_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_memory_meta(entries):
    ensure_memories_dirs()
    MEMORIES_META_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _memory_media_path(entry):
    memory_id = entry.get("id")
    media_type = entry.get("media_type")
    if not memory_id or not media_type:
        return None
    if media_type == "image":
        return MEMORIES_DIR / f"{memory_id}.jpg"
    if media_type == "video":
        ext = entry.get("media_ext") or ".mp4"
        return MEMORIES_DIR / f"{memory_id}{ext}"
    return None


def _memory_urls(entry):
    base = _request_base_url()
    memory_id = entry["id"]
    media_type = entry.get("media_type")
    payload = {
        "id": memory_id,
        "author": entry.get("author") or "",
        "message": entry.get("message") or "",
        "media_type": media_type or "",
        "timestamp": entry.get("timestamp") or "",
        "media_url": "",
        "thumb_url": "",
    }
    if media_type == "image":
        payload["media_url"] = f"{base}/memories/file/{memory_id}.jpg"
        payload["thumb_url"] = f"{base}/memories/thumb/{memory_id}.jpg"
    elif media_type == "video":
        ext = entry.get("media_ext") or ".mp4"
        payload["media_url"] = f"{base}/memories/file/{memory_id}{ext}"
    return payload


def _save_memory_image(file_storage, memory_id):
    filename = (file_storage.filename or "").strip()
    ext = Path(filename).suffix.lower()
    if ext and ext not in ALLOWED_PHOTO_EXTS:
        raise ValueError(f"Unsupported image type: {ext}")

    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty file")

    try:
        img = Image.open(io.BytesIO(raw))
    except UnidentifiedImageError as exc:
        raise ValueError("Could not read image") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        alpha = img.split()[-1] if img.mode in ("RGBA", "LA") else None
        background.paste(img, mask=alpha)
        img = background
    else:
        img = img.convert("RGB")

    full_path = MEMORIES_DIR / f"{memory_id}.jpg"
    thumb_path = MEMORIES_THUMBS_DIR / f"{memory_id}.jpg"

    full = img.copy()
    full.thumbnail((PHOTO_MAX_EDGE, PHOTO_MAX_EDGE), Image.Resampling.LANCZOS)
    full.save(full_path, format="JPEG", quality=PHOTO_JPEG_QUALITY, optimize=True)

    thumb = img.copy()
    thumb.thumbnail((THUMB_MAX_EDGE, THUMB_MAX_EDGE), Image.Resampling.LANCZOS)
    thumb.save(thumb_path, format="JPEG", quality=THUMB_JPEG_QUALITY, optimize=True)


def _save_memory_video(file_storage, memory_id, ext):
    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty video file")
    if len(raw) > MAX_VIDEO_BYTES:
        raise ValueError("Video is too large (max 80 MB)")
    (MEMORIES_DIR / f"{memory_id}{ext}").write_bytes(raw)


def _send_memory_notification(author, message, media_type):
    memories_url = f"{SITE_BASE_URL.rstrip('/')}/memories.html"
    if media_type == "image":
        attachment = "Photo attached"
    elif media_type == "video":
        attachment = "Video attached"
    else:
        attachment = "Message only"
    message_preview = (message or "").strip()
    if len(message_preview) > 500:
        message_preview = message_preview[:500] + "…"
    subject = f"New memory from {author}"
    body = f"""Someone just shared a memory on your wedding site!

From: {author}
Type: {attachment}
Message:
{message_preview or "(no message)"}

View memories: {memories_url}
"""
    _send_email(subject, body)


def _valid_photo_id(photo_id):
    return bool(photo_id) and all(c in "0123456789abcdef" for c in photo_id.lower()) and len(photo_id) <= 64


def _valid_memory_id(memory_id):
    return _valid_photo_id(memory_id)


def _uploaded_file_has_content(file_storage):
    if not file_storage:
        return False
    try:
        stream = file_storage.stream
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(0)
        return size > 0
    except Exception:
        return bool((file_storage.filename or "").strip())


def _sniff_media_kind(file_storage):
    try:
        stream = file_storage.stream
        pos = stream.tell()
        header = stream.read(16)
        stream.seek(pos)
    except Exception:
        return None, ""

    if header.startswith(b"\xff\xd8\xff"):
        return "image", ".jpg"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"heic", b"heix", b"mif1", b"hevc"):
            return "image", ".heic"
        if brand in (b"qt  ", b"moov"):
            return "video", ".mov"
        return "video", ".mp4"
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return "image", ".webp"
    return None, ""


def _guess_media_kind(file_storage):
    filename = (file_storage.filename or "").strip()
    ext = Path(filename).suffix.lower()
    mimetype = (file_storage.mimetype or "").lower()

    if ext in ALLOWED_PHOTO_EXTS:
        return "image", ext
    if ext in ALLOWED_MEMORY_VIDEO_EXTS:
        return "video", ext
    if mimetype.startswith("image/"):
        return "image", ext or ".jpg"
    if mimetype.startswith("video/"):
        if "quicktime" in mimetype:
            return "video", ".mov"
        if "webm" in mimetype:
            return "video", ".webm"
        return "video", ext or ".mp4"

    sniffed_kind, sniffed_ext = _sniff_media_kind(file_storage)
    if sniffed_kind:
        return sniffed_kind, sniffed_ext
    return None, ext


@app.after_request
def add_cors_headers(response):
    photo_paths = (
        request.path == "/photos/upload"
        or request.path == "/photos/list"
        or request.path == "/photos/delete"
        or request.path.startswith("/photos/file/")
        or request.path.startswith("/photos/thumb/")
    )
    memory_paths = (
        request.path == "/memories/upload"
        or request.path == "/memories/list"
        or request.path == "/memories/delete"
        or request.path.startswith("/memories/file/")
        or request.path.startswith("/memories/thumb/")
    )
    if request.path in ("/submit", "/meal-submit") or photo_paths or memory_paths:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/")
def index():
    return (
        "RSVP backend is running. "
        f"Download responses at {request.host_url.rstrip('/')}/data",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@app.route("/thank-you")
def thank_you():
    return (
        "Thanks! Your response was received.",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@app.route("/data")
def data_page():
    return render_template("rsvp_export.html")


@app.route("/submit", methods=["OPTIONS"])
@app.route("/meal-submit", methods=["OPTIONS"])
@app.route("/photos/upload", methods=["OPTIONS"])
@app.route("/photos/list", methods=["OPTIONS"])
@app.route("/photos/delete", methods=["OPTIONS"])
@app.route("/memories/upload", methods=["OPTIONS"])
@app.route("/memories/list", methods=["OPTIONS"])
@app.route("/memories/delete", methods=["OPTIONS"])
def cors_preflight():
    return "", 204


@app.route("/submit", methods=["POST"])
def submit():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    additional_guests_raw = request.form.getlist("additional_guests")
    additional_guests = "\n".join((g or "").strip() for g in additional_guests_raw if (g or "").strip())
    attending = (request.form.get("attending") or "").strip()
    weekend_scope = (request.form.get("weekend_scope") or "").strip()
    weekend_other = (request.form.get("weekend_other") or "").strip()
    meal_choices = _parse_meal_choices(request.form)
    meal_other = (request.form.get("meal_other") or "").strip()
    accommodation_plan = (request.form.get("accommodation_plan") or "").strip()
    accommodation_other = (request.form.get("accommodation_other") or "").strip()
    open_to_sharing = "yes" if request.form.get("open_to_sharing") == "yes" else ""
    prefer_own_room = "yes" if request.form.get("prefer_own_room") == "yes" else ""
    interested_glamping = "yes" if request.form.get("interested_glamping") == "yes" else ""
    wedding_party = "yes" if request.form.get("wedding party") == "yes" else ""
    bunking_with = (request.form.get("bunking_with") or "").strip()

    path = ensure_responses_file()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.utcnow().isoformat() + "Z",
            name, email, additional_guests, attending,
            weekend_scope, weekend_other, meal_choices, meal_other,
            accommodation_plan, accommodation_other,
            open_to_sharing, prefer_own_room, interested_glamping,
            wedding_party, bunking_with,
        ])

    _send_rsvp_notification(name, email, attending, weekend_scope, meal_choices, accommodation_plan)
    return {"ok": True}, 200


@app.route("/meal-submit", methods=["POST"])
def meal_submit():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    additional_guests_raw = request.form.getlist("additional_guests")
    additional_guests = "\n".join((g or "").strip() for g in additional_guests_raw if (g or "").strip())
    meal_choices = _parse_guest_meals(request.form)
    dietary_restrictions = (request.form.get("dietary_restrictions") or "").strip()
    staying_plan = (request.form.get("staying_plan") or "").strip()
    off_site_address = (request.form.get("off_site_address") or "").strip()
    taxi_service = (request.form.get("taxi_service") or "").strip()
    song_request = (request.form.get("song_request") or "").strip()
    weekend_notes = (request.form.get("weekend_notes") or "").strip()

    if not name:
        return {"ok": False, "error": "name required"}, 400

    path = ensure_meal_responses_file()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.utcnow().isoformat() + "Z",
            name, email, additional_guests, meal_choices, dietary_restrictions,
            staying_plan, off_site_address, taxi_service, song_request, weekend_notes,
        ])

    _send_meal_notification(
        name, email, additional_guests, meal_choices, dietary_restrictions,
        staying_plan, off_site_address, taxi_service, song_request, weekend_notes,
    )
    return {"ok": True}, 200


@app.route("/photos/upload", methods=["POST"])
def photos_upload():
    ensure_photos_dirs()
    uploader = (request.form.get("name") or "").strip()[:80]
    if not uploader:
        return jsonify({"ok": False, "error": "Name is required"}), 400
    files = request.files.getlist("photos")
    if not files:
        # Also accept a single "photo" field
        one = request.files.get("photo")
        files = [one] if one else []
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify({"ok": False, "error": "No photos selected"}), 400
    if len(files) > MAX_PHOTOS_PER_UPLOAD:
        return jsonify({
            "ok": False,
            "error": f"Please upload at most {MAX_PHOTOS_PER_UPLOAD} photos at a time",
        }), 400

    meta = _load_photo_meta()
    saved = []
    errors = []
    for f in files:
        try:
            entry = _process_and_save_image(f, uploader)
            meta.append(entry)
            saved.append({**entry, **_photo_urls(entry["id"])})
        except Exception as exc:
            app.logger.warning("Photo upload failed for %s: %s", f.filename, exc)
            errors.append({"file": f.filename, "error": str(exc)})

    if not saved:
        return jsonify({"ok": False, "error": "No photos could be saved", "errors": errors}), 400

    _save_photo_meta(meta)
    _send_photo_upload_notification(uploader, len(saved))
    return jsonify({"ok": True, "saved": saved, "errors": errors}), 200


@app.route("/photos/delete", methods=["POST"])
def photos_delete():
    ensure_photos_dirs()
    if not PHOTO_ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Photo delete is not configured"}), 503

    payload = request.get_json(silent=True) or {}
    photo_id = (payload.get("id") or request.form.get("id") or "").strip()
    password = payload.get("password") or request.form.get("password") or ""
    if not _valid_photo_id(photo_id):
        return jsonify({"ok": False, "error": "Invalid photo id"}), 400
    if password != PHOTO_ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Incorrect password"}), 403

    meta = _load_photo_meta()
    new_meta = [entry for entry in meta if entry.get("id") != photo_id]
    if len(new_meta) == len(meta):
        return jsonify({"ok": False, "error": "Photo not found"}), 404

    full_path = PHOTOS_DIR / f"{photo_id}.jpg"
    thumb_path = THUMBS_DIR / f"{photo_id}.jpg"
    try:
        if full_path.exists():
            full_path.unlink()
        if thumb_path.exists():
            thumb_path.unlink()
    except OSError as exc:
        app.logger.error("Failed to delete photo files for %s: %s", photo_id, exc)
        return jsonify({"ok": False, "error": "Could not delete photo files"}), 500

    _save_photo_meta(new_meta)
    return jsonify({"ok": True, "id": photo_id}), 200


@app.route("/photos/list", methods=["GET"])
def photos_list():
    ensure_photos_dirs()
    meta = _load_photo_meta()
    # Newest first
    ordered = sorted(meta, key=lambda e: e.get("timestamp", ""), reverse=True)
    photos = []
    for entry in ordered:
        photo_id = entry.get("id")
        if not photo_id:
            continue
        full = PHOTOS_DIR / f"{photo_id}.jpg"
        if not full.exists():
            continue
        photos.append({
            "id": photo_id,
            "uploader": entry.get("uploader") or "",
            "timestamp": entry.get("timestamp") or "",
            **_photo_urls(photo_id),
        })
    return jsonify({"ok": True, "count": len(photos), "photos": photos})


@app.route("/photos/file/<photo_id>.jpg")
def photos_file(photo_id):
    ensure_photos_dirs()
    if not _valid_photo_id(photo_id):
        return "Not found", 404
    path = PHOTOS_DIR / f"{photo_id}.jpg"
    if not path.exists():
        return "Not found", 404
    return send_file(path, mimetype="image/jpeg", max_age=86400)


@app.route("/photos/thumb/<photo_id>.jpg")
def photos_thumb(photo_id):
    ensure_photos_dirs()
    if not _valid_photo_id(photo_id):
        return "Not found", 404
    path = THUMBS_DIR / f"{photo_id}.jpg"
    if not path.exists():
        # Fall back to full image if thumb missing
        path = PHOTOS_DIR / f"{photo_id}.jpg"
    if not path.exists():
        return "Not found", 404
    return send_file(path, mimetype="image/jpeg", max_age=86400)


@app.route("/memories/upload", methods=["POST"])
def memories_upload():
    ensure_memories_dirs()
    author = (request.form.get("name") or "").strip()[:80]
    message = (request.form.get("message") or "").strip()[:MAX_MEMORY_MESSAGE]
    if not author:
        return jsonify({"ok": False, "error": "Name is required"}), 400

    media = request.files.get("media")
    has_media = _uploaded_file_has_content(media)
    if not message and not has_media:
        return jsonify({"ok": False, "error": "Please add a message, photo, or video"}), 400

    memory_id = uuid.uuid4().hex
    media_type = ""
    media_ext = ""
    original_name = ""

    if has_media:
        original_name = (media.filename or "").strip()
        kind, ext = _guess_media_kind(media)
        if kind == "image":
            try:
                _save_memory_image(media, memory_id)
                media_type = "image"
                media_ext = ".jpg"
            except Exception as exc:
                app.logger.warning("Memory image upload failed: %s", exc)
                return jsonify({"ok": False, "error": str(exc)}), 400
        elif kind == "video":
            video_ext = ext if ext in ALLOWED_MEMORY_VIDEO_EXTS else ".mp4"
            try:
                _save_memory_video(media, memory_id, video_ext)
                media_type = "video"
                media_ext = video_ext
            except Exception as exc:
                app.logger.warning("Memory video upload failed: %s", exc)
                return jsonify({"ok": False, "error": str(exc)}), 400
        else:
            return jsonify({
                "ok": False,
                "error": "Unsupported file type. Use JPG, PNG, HEIC, MP4, MOV, or WebM.",
            }), 400

    entry = {
        "id": memory_id,
        "author": author,
        "message": message,
        "media_type": media_type or None,
        "media_ext": media_ext,
        "original_name": original_name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    meta = _load_memory_meta()
    meta.append(entry)
    _save_memory_meta(meta)
    _send_memory_notification(author, message, media_type or None)
    return jsonify({"ok": True, "memory": {**entry, **_memory_urls(entry)}}), 200


@app.route("/memories/delete", methods=["POST"])
def memories_delete():
    ensure_memories_dirs()
    if not PHOTO_ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Delete is not configured"}), 503

    payload = request.get_json(silent=True) or {}
    memory_id = (payload.get("id") or request.form.get("id") or "").strip()
    password = payload.get("password") or request.form.get("password") or ""
    if not _valid_memory_id(memory_id):
        return jsonify({"ok": False, "error": "Invalid memory id"}), 400
    if password != PHOTO_ADMIN_PASSWORD:
        return jsonify({"ok": False, "error": "Incorrect password"}), 403

    meta = _load_memory_meta()
    target = next((entry for entry in meta if entry.get("id") == memory_id), None)
    if not target:
        return jsonify({"ok": False, "error": "Memory not found"}), 404

    media_path = _memory_media_path(target)
    thumb_path = MEMORIES_THUMBS_DIR / f"{memory_id}.jpg"
    try:
        if media_path and media_path.exists():
            media_path.unlink()
        if thumb_path.exists():
            thumb_path.unlink()
    except OSError as exc:
        app.logger.error("Failed to delete memory files for %s: %s", memory_id, exc)
        return jsonify({"ok": False, "error": "Could not delete memory files"}), 500

    _save_memory_meta([entry for entry in meta if entry.get("id") != memory_id])
    return jsonify({"ok": True, "id": memory_id}), 200


@app.route("/memories/list", methods=["GET"])
def memories_list():
    ensure_memories_dirs()
    meta = _load_memory_meta()
    ordered = sorted(meta, key=lambda e: e.get("timestamp", ""), reverse=True)
    memories = []
    for entry in ordered:
        memory_id = entry.get("id")
        if not memory_id:
            continue
        media_type = entry.get("media_type")
        if media_type:
            media_path = _memory_media_path(entry)
            if not media_path or not media_path.exists():
                entry = dict(entry)
                entry["media_type"] = None
                entry["media_ext"] = ""
                memories.append(_memory_urls(entry))
                continue
        memories.append(_memory_urls(entry))
    return jsonify({"ok": True, "count": len(memories), "memories": memories})


@app.route("/memories/file/<memory_id>.<ext>")
def memories_file(memory_id, ext):
    ensure_memories_dirs()
    if not _valid_memory_id(memory_id):
        return "Not found", 404
    ext = f".{ext.lower()}"
    if ext in ALLOWED_PHOTO_EXTS or ext == ".jpg":
        path = MEMORIES_DIR / f"{memory_id}.jpg"
        if not path.exists():
            return "Not found", 404
        return send_file(path, mimetype="image/jpeg", max_age=86400)
    if ext in ALLOWED_MEMORY_VIDEO_EXTS:
        path = MEMORIES_DIR / f"{memory_id}{ext}"
        if not path.exists():
            return "Not found", 404
        return send_file(path, mimetype=VIDEO_MIMETYPES.get(ext, "video/mp4"), max_age=86400)
    return "Not found", 404


@app.route("/memories/thumb/<memory_id>.jpg")
def memories_thumb(memory_id):
    ensure_memories_dirs()
    if not _valid_memory_id(memory_id):
        return "Not found", 404
    path = MEMORIES_THUMBS_DIR / f"{memory_id}.jpg"
    if not path.exists():
        path = MEMORIES_DIR / f"{memory_id}.jpg"
    if not path.exists():
        return "Not found", 404
    return send_file(path, mimetype="image/jpeg", max_age=86400)


@app.route("/download-csv")
def download_csv():
    if not RESPONSES_FILE.exists():
        ensure_responses_file()
    return send_file(
        RESPONSES_FILE,
        mimetype="text/csv",
        as_attachment=True,
        download_name="wedding-rsvp-responses.csv",
    )


@app.route("/download-excel")
def download_excel():
    ensure_responses_file()
    wb = Workbook()
    ws = wb.active
    ws.title = "RSVP Responses"
    with open(RESPONSES_FILE, "r", newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="wedding-rsvp-responses.xlsx",
    )


@app.route("/download-meal-csv")
def download_meal_csv():
    if not MEAL_RESPONSES_FILE.exists():
        ensure_meal_responses_file()
    return send_file(
        MEAL_RESPONSES_FILE,
        mimetype="text/csv",
        as_attachment=True,
        download_name="wedding-meal-responses.csv",
    )


@app.route("/download-meal-excel")
def download_meal_excel():
    ensure_meal_responses_file()
    wb = Workbook()
    ws = wb.active
    ws.title = "Meal Responses"
    with open(MEAL_RESPONSES_FILE, "r", newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="wedding-meal-responses.xlsx",
    )
