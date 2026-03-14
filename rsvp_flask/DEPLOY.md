# Deploying the RSVP Flask app

The app saves responses to `responses.csv` in the app directory. For deployment you need a host that either keeps the filesystem between deploys or gives you a persistent volume.

---

## Option 1: Render (recommended, free tier)

1. **Sign up:** [render.com](https://render.com) (free account).

2. **New Web Service:** Connect your GitHub repo, choose the **Marriage** repo.

3. **Settings:**
   - **Root directory:** `rsvp_flask`
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
   - **Environment:** Add `WEDDING_SITE_URL` = your main site URL (e.g. `https://www.ryanandcarlygethitched.com`)

4. **Important – data persistence:** On Render’s free tier, the filesystem is **ephemeral**: `responses.csv` is lost on every new deploy or restart. To keep data:
   - Use **Render Disk** (paid add‑on), and set `RSVP_RESPONSES_DIR` to the path Render gives you for the disk, **or**
   - Use **Option 2 (Railway)** or **Option 3 (PythonAnywhere)** if you want free persistence.

5. After deploy, your RSVP backend URL will be like `https://your-app-name.onrender.com`. Use that as the backend URL for your form (same origin or `rsvp-backend-url` meta tag). Download data at:
   - `https://your-app-name.onrender.com/data`

---

## Option 2: Railway (free tier, persistent disk)

1. **Sign up:** [railway.app](https://railway.app).

2. **New project:** Deploy from GitHub → select **Marriage** repo.

3. **Settings:**
   - Set **Root directory** to `rsvp_flask` (or add a `railway.toml` / configure in dashboard).
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
   - Add **Volume** and mount it to a path (e.g. `/data`). In **Variables** set:
     - `RSVP_RESPONSES_DIR=/data`

4. Your app URL will be like `https://your-app.up.railway.app`. Download data at:
   - `https://your-app.up.railway.app/data`

5. **Email notifications (optional):** Railway blocks outbound SMTP, so use **Resend** instead:
   - Sign up at [resend.com](https://resend.com) (free tier: 100 emails/day)
   - Create an API key in the Resend dashboard
   - In Railway **Variables**, add:
     - `RSVP_NOTIFY_EMAIL` = your email (e.g. `carly@example.com`)
     - `RESEND_API_KEY` = your Resend API key
   - Emails will be sent from `onboarding@resend.dev` by default. To use your own domain, verify it in Resend and set `RSVP_FROM_EMAIL=Wedding <rsvp@yourdomain.com>`

---

## Option 3: PythonAnywhere (free tier, files persist)

1. **Sign up:** [pythonanywhere.com](https://www.pythonanywhere.com) (free account).

2. **Upload project:** Clone your repo or upload the `rsvp_flask` folder into your account.

3. **Virtualenv:** In a bash console:
   ```bash
   cd rsvp_flask
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Web app:** In the **Web** tab, add a new app → **Manual configuration** → Python 3.x. Set:
   - **Source code:** your project path (e.g. `/home/yourusername/Marriage/rsvp_flask`)
   - **WSGI file:** Edit the WSGI file and point it to your app, e.g.:
     ```python
     import sys
     sys.path.insert(0, '/home/yourusername/Marriage/rsvp_flask')
     from app import app as application
     ```
   - **Virtualenv:** `/home/yourusername/Marriage/rsvp_flask/venv`

5. **Static site on same domain:** If your main site is elsewhere (e.g. GitHub Pages at `www.ryanandcarlygethitched.com`), keep the form’s `action` or `rsvp-backend-url` pointing to your PythonAnywhere app URL (e.g. `https://yourusername.pythonanywhere.com`). Download data at:
   - `https://yourusername.pythonanywhere.com/data`

---

## Using your own domain (e.g. www.ryanandcarlygethitched.com)

- **If the whole site is on the same host as Flask:** Point the domain to the Flask app; `/data` will be at `https://www.ryanandcarlygethitched.com/data`.
- **If the main site is static (e.g. GitHub Pages):** Either:
  - Keep the backend on a subdomain (e.g. `rsvp.ryanandcarlygethitched.com` or `api.ryanandcarlygethitched.com`) and set your static RSVP form’s `rsvp-backend-url` meta tag to that URL, or
  - Put the static site and Flask behind the same domain using a reverse proxy (e.g. Cloudflare, Nginx) so that `/submit`, `/data`, `/download-csv` are served by Flask and the rest by the static site.

---

## Quick test locally

```bash
cd rsvp_flask
pip install -r requirements.txt
flask --app app run
```

Then open `http://127.0.0.1:5000` for the RSVP form and `http://127.0.0.1:5000/data` to download responses.
