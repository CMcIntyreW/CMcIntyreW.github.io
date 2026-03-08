# RSVP Flask App

Python Flask app for the wedding RSVP form. **Responses are saved to `responses.csv`** in this folder (or the path in `RSVP_RESPONSES_DIR` if set).

## How you get responses

- **CSV file:** Responses are appended to `responses.csv`. Open it in Excel or any spreadsheet.
- **Download as Excel:** Visit **`/download-excel`** on your Flask app (e.g. `https://your-rsvp.railway.app/download-excel`) to download all responses as **wedding-rsvp-responses.xlsx**.
- **Download as CSV:** Visit **`/download-csv`** to download **wedding-rsvp-responses.csv** (opens in Excel).  
  Keep these URLs private (don’t link them on the public site) so only you can download responses.

## Run locally

```bash
cd rsvp_flask
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run
```

Open http://localhost:5000/ for the built-in form.

## Use the main site’s RSVP form with Flask

The main site has a step-by-step RSVP form in `rsvp.html`. To send those submissions to Flask:

1. Deploy this Flask app (e.g. Railway, PythonAnywhere, Heroku) and note its URL (e.g. `https://your-rsvp.railway.app`).
2. In the **main project** open `rsvp.html` and set the form’s `action` to your Flask URL + `/submit`:
   ```html
   <form id="rsvp-form" action="https://your-rsvp.railway.app/submit" method="post">
   ```
3. If you serve the whole wedding site from this Flask app (same origin), you can keep `action="/submit"` and it will work without changing the URL.
