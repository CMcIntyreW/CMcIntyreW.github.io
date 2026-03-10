"""
Flask RSVP app for Ryan & Carly's wedding.
Saves responses to a CSV file. Run: flask --app app run
"""
import csv
import io
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for
from openpyxl import Workbook

app = Flask(__name__)

RESPONSES_DIR = Path(__file__).resolve().parent
RESPONSES_DIR = Path(os.environ.get("RSVP_RESPONSES_DIR", str(RESPONSES_DIR)))
RESPONSES_FILE = RESPONSES_DIR / "responses.csv"
SITE_BASE_URL = os.environ.get("WEDDING_SITE_URL", "https://cmcintyrew.github.io")


def ensure_responses_file():
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    path = RESPONSES_FILE
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp", "name", "email", "additional_guests", "attending",
                "weekend_scope", "weekend_other", "meal", "meal_other",
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
    meal = request.form.get("meal", "")
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
            weekend_scope, weekend_other, meal, meal_other,
            accommodation_plan, accommodation_other,
            open_to_sharing, prefer_own_room, interested_glamping, bunking_with,
        ])

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
