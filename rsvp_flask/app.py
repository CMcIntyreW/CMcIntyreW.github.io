import csv
import io
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, send_file
from openpyxl import Workbook

app = Flask(__name__)

RESPONSES_DIR = Path(os.environ.get("RSVP_RESPONSES_DIR", "."))
RESPONSES_FILE = RESPONSES_DIR / "responses.csv"
MEAL_RESPONSES_FILE = RESPONSES_DIR / "meal-responses.csv"
SITE_BASE_URL = os.environ.get("WEDDING_SITE_URL", "https://www.ryanandcarlygethitched.com")

RSVP_NOTIFY_EMAIL = os.environ.get("RSVP_NOTIFY_EMAIL", "").strip()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RSVP_FROM_EMAIL = os.environ.get("RSVP_FROM_EMAIL", "onboarding@resend.dev").strip()


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
            parts.append(f"{name}: no dinner (below 3)")
            continue
        if choice:
            entry = f"{name}: {labels.get(choice, choice)}"
            if child_age == "yes":
                entry += " (aged 3-10)"
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


@app.after_request
def add_cors_headers(response):
    if request.path in ("/submit", "/meal-submit"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
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
