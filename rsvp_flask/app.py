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
                "timestamp", "name", "email", "attending",
                "friday", "saturday", "sunday",
                "guests", "dietary", "song_request", "message"
            ])
    return path


@app.route("/")
def index():
    return render_template("rsvp.html", site_base_url=SITE_BASE_URL)


@app.route("/submit", methods=["POST"])
def submit():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    attending = request.form.get("attending", "")
    friday = "yes" if request.form.get("friday") else "no"
    saturday = "yes" if request.form.get("saturday") else "no"
    sunday = "yes" if request.form.get("sunday") else "no"
    guests = (request.form.get("guests") or "").strip()
    dietary = (request.form.get("dietary") or "").strip()
    song_request = (request.form.get("song_request") or "").strip()
    message = (request.form.get("message") or "").strip()

    path = ensure_responses_file()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.utcnow().isoformat() + "Z",
            name, email, attending,
            friday, saturday, sunday,
            guests, dietary, song_request, message,
        ])

    return redirect(url_for("thank_you"))


@app.route("/thank-you")
def thank_you():
    return render_template("thank_you.html", site_base_url=SITE_BASE_URL)


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
