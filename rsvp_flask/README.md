# RSVP Flask App

Python Flask app for the wedding RSVP form. Responses are saved to `responses.csv`.

## Run locally

```bash
cd rsvp_flask
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app app run
```

Open http://localhost:5000/ for the form.

## Deploy

Host the `rsvp_flask` app on Railway, PythonAnywhere, or similar. Then set the "Open RSVP form" link in your main site's `rsvp.html` to your app URL.
