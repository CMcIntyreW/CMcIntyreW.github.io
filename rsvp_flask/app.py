"""
Flask RSVP app for Ryan & Carly's wedding.
Saves responses to a CSV file. Run: flask --app app run
"""
import csv
import io
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook

app = Flask(__name__)

RESPONSES_DIR = Path(__file__).resolve().parent
RESPONSES_DIR = Path(os.environ.get("RSVP_RESPONSES_DIR", str(RESPONSES_DIR)))
RESPONSES_FILE = RESPONSES_DIR / "responses.csv"
SITE_BASE_URL = os.environ.get("WEDDING_SITE_URL", "https://cmcintyrew.github.io")

# Optional: notify email when someone RSVPs (set RSVP_NOTIFY_EMAIL + SMTP vars)
RSVP_NOTIFY_EMAIL = os.environ.get("RSVP_NOTIFY_EMAIL", "").strip()
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()


def _send_rsvp_notification(name, email, attending, weekend_scope, meal_choices, accommodation_plan):
    """Send an email when someone submits an RSVP. Fails silently if not configured."""
    if not RSVP_NOTIFY_EMAIL or not SMTP_USER or not SMTP_PASSWORD:
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = RSVP_NOTIFY_EMAIL
        msg["Subject"] = f"New RSVP: {name}" + (" — Attending!" if attending == "yes" else " — Not attending")
        data_url = os.environ.get("RSVP_BACKEND_URL", "").rstrip("/") or "(set RSVP_BACKEND_URL)"
        body = f"""Someone just submitted an RSVP!

Name: {name}
Email: {email}
Attending: {"Yes" if attending == "yes" else "No"}
Weekend: {weekend_scope or "(not specified)"}
Meal choices: {meal_choices or "(none)"}
Accommodation: {accommodation_plan or "(not specified)"}

View all responses: {data_url}/data
"""
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, RSVP_NOTIFY_EMAIL, msg.as_string())
    except Exception:
        pass  # Don't fail the RSVP if email fails


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
                "open_to_sharing", "prefer_own_room", "interested_glamping", "bunking_with"
            ])
    return path


@app.route("/")
def index():
    return render_template("rsvp.html", site_base_url=SITE_BASE_URL)


@app.route("/submit", methods=["POST"])
def submit():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    additional_guests_raw = request.form.getlist("additional_guests")
    additional_guests = "\n".join((g or "").strip() for g in additional_guests_raw if (g or "").strip())
    attending = request.form.get("attending", "")
    weekend_scope = request.form.get("weekend_scope", "")
    weekend_other = (request.form.get("weekend_other") or "").strip()
    meal_names = {
        "chicken": "chicken",
        "beef": "beef",
        "fish": "fish",
        "vegetarian": "vegetarian",
        "vegan": "vegan",
    }
    parts = []
    for key, label in meal_names.items():
        count = int(request.form.get(f"meal_count_{key}") or "0") or 0
        if count > 0:
            parts.append(f"{count} {label}")
    meal_choices = ", ".join(parts) if parts else ""
    meal_other = (request.form.get("meal_other") or "").strip()
    accommodation_plan = request.form.get("accommodation_plan", "")
    accommodation_other = (request.form.get("accommodation_other") or "").strip()
    open_to_sharing = "yes" if request.form.get("open_to_sharing") else "no"
    prefer_own_room = "yes" if request.form.get("prefer_own_room") else "no"
    interested_glamping = "yes" if request.form.get("interested_glamping") else "no"
    bunking_with = (request.form.get("bunking_with") or "").strip()

    path = ensure_responses_file()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.utcnow().isoformat() + "Z",
            name, email, additional_guests, attending,
            weekend_scope, weekend_other, meal_choices, meal_other,
            accommodation_plan, accommodation_other,
            open_to_sharing, prefer_own_room, interested_glamping, bunking_with,
        ])

    _send_rsvp_notification(name, email, attending, weekend_scope, meal_choices, accommodation_plan)

    return redirect(url_for("thank_you"))


@app.route("/thank-you")
def thank_you():
    return render_template("thank_you.html", site_base_url=SITE_BASE_URL)


@app.route("/data")
def rsvp_export():
    """Unlinked page to download RSVP responses. Bookmark this URL; do not link from the site."""
    return render_template("rsvp_export.html")


@app.route("/download-excel")
def download_excel():
    """Download all RSVP responses as an Excel (.xlsx) file."""
    ensure_responses_file()
    wb = Workbook()
    ws = wb.active
    ws.title = "RSVP Responses"
    with open(RESPONSES_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
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


@app.route("/download-csv")
def download_csv():
    """Download all RSVP responses as a CSV file (opens in Excel)."""
    if not RESPONSES_FILE.exists():
        ensure_responses_file()
    return send_file(
        RESPONSES_FILE,
        mimetype="text/csv",
        as_attachment=True,
        download_name="wedding-rsvp-responses.csv",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
