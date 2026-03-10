# Deploy RSVP app on Railway

Follow these steps to get your Flask RSVP app live with persistent storage for responses.

---

## 1. Sign up and create a project

1. Go to **[railway.app](https://railway.app)** and sign in (GitHub is easiest).
2. Click **"New Project"**.
3. Choose **"Deploy from GitHub repo"** and select your **Marriage** repository (or the repo that contains `rsvp_flask`).
4. If Railway asks which service to add, pick **"Add a service"** or **"Deploy now"** so it creates one service from the repo.

---

## 2. Configure the service

1. Click the new service to open it.
2. Open the **Settings** tab (or the **Variables** tab for env vars).
3. **Root directory (important):**  
   - In **Settings**, find **"Root Directory"** or **"Source"**.  
   - Set it to **`rsvp_flask`** so Railway builds and runs from that folder.  
   - If you don’t see Root Directory, check under **Settings → Build** or the service’s **Configure** options.
4. **Build:** Railway usually auto-detects Python. If you need a custom build command, use:
   ```bash
   pip install -r requirements.txt
   ```
5. **Start command:** Set to:
   ```bash
   gunicorn -w 1 -b 0.0.0.0:$PORT app:app
   ```
   (Railway sets `PORT` automatically.)

---

## 3. Add a volume (so responses are saved permanently)

Without a volume, `responses.csv` is lost every time the app restarts or redeploys.

1. In your service, open the **Variables** tab.
2. Click **"+ New Variable"** or **"Add Variable"**.
3. In the same area, look for **"Volumes"** or **"Add Volume"** (may be under the service’s **Settings** or a **Storage** section).
4. Add a volume and set the **mount path** to **`/data`** (or another path you prefer).
5. Add a **variable**:
   - **Name:** `RSVP_RESPONSES_DIR`  
   - **Value:** `/data`  
   (This must match the volume mount path.)

---

## 4. Optional environment variables

In **Variables**, you can add:

| Variable            | Example value                              | Purpose |
|---------------------|--------------------------------------------|--------|
| `WEDDING_SITE_URL`  | `https://www.ryanandcarlygethitched.com`   | Used in thank-you / redirect links if needed. |

---

## 5. Deploy

1. Save / deploy. Railway will build and start the app.
2. In the **Settings** or **Deployments** tab, open **"Generate Domain"** or **"Settings → Networking"** to get a public URL (e.g. `https://your-app-name.up.railway.app`).

---

## 6. Use the app

- **RSVP form backend:** Point your wedding site’s RSVP form to this URL (e.g. set the form `action` or the `rsvp-backend-url` meta tag to `https://your-app-name.up.railway.app`).
- **Download responses:**  
  **`https://your-app-name.up.railway.app/data`**  
  Bookmark this; don’t link it from the public site.

---

## 7. Custom domain (optional)

To use `www.ryanandcarlygethitched.com` or a subdomain (e.g. `rsvp.ryanandcarlygethitched.com`):

1. In the service, go to **Settings → Networking → Custom Domain**.
2. Add your domain or subdomain and follow Railway’s DNS instructions (CNAME or A record).
3. Update your wedding site’s RSVP backend URL to that domain.
4. Your data page will be at **`https://your-domain.com/data`**.

---

## Verify your setup

Run the check script in any of these ways:

**From repo root (Marriage):**
```bash
chmod +x check_rsvp.sh
./check_rsvp.sh                                    # uses railway domain or RSVP_BACKEND_URL
./check_rsvp.sh https://your-app.up.railway.app
```

**From `rsvp_flask`:**
```bash
chmod +x check_railway.sh
./check_railway.sh                                 # uses railway domain or RSVP_BACKEND_URL
./check_railway.sh https://your-app.up.railway.app
RSVP_BACKEND_URL=https://your-app.up.railway.app ./check_railway.sh
```

The script tries, in order: (1) first argument, (2) `RSVP_BACKEND_URL` env var, (3) `railway domain` if the CLI is linked. It tests `/`, `/thank-you`, `/data`, `/download-csv`, and `POST /submit`. If any check fails, see Troubleshooting below.

---

## Troubleshooting

- **Build fails:** Confirm **Root Directory** is `rsvp_flask` and that `requirements.txt` is in that folder.
- **App crashes on start:** Check the **Deployments** log. Ensure the start command is `gunicorn -w 1 -b 0.0.0.0:$PORT app:app` and that `PORT` is not overridden.
- **Responses disappear after redeploy:** Make sure a **volume** is added and `RSVP_RESPONSES_DIR` is set to the volume path (e.g. `/data`).
