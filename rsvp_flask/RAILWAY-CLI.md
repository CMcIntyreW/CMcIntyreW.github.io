# Deploy RSVP app with Railway CLI (terminal)

Do everything from your Mac terminal (or Cursor’s terminal). No need to use Root Directory in the Railway website.

---

## 1. Install Railway CLI

In Terminal (or Cursor: **Terminal → New Terminal**), run:

```bash
brew install railway
```

If you don’t use Homebrew:

```bash
npm install -g @railway/cli
```

---

## 2. Log in

```bash
railway login
```

A browser window will open to log you into Railway.

---

## 3. Go to the app folder

```bash
cd /Users/carlysoup/Library/CloudStorage/OneDrive-McMasterUniversity/Marriage/rsvp_flask
```

(Or in Cursor, open the `rsvp_flask` folder and run the next commands from there.)

---

## 4. Link to an existing project (if you already created one on Railway)

```bash
railway link
```

Choose your project and the service when asked. That connects this folder to the app you created from GitHub.

---

## 5. Or create a new project from the terminal

If you haven’t created a project yet, or want a new one:

```bash
railway init
```

Follow the prompts to create a new project and service.

---

## 6. Set the variable for saving RSVPs (persistent storage)

If your Railway plan supports volumes, add the variable (replace with your volume path if different):

```bash
railway variables --set RSVP_RESPONSES_DIR=/data
```

If you added a volume in the Railway dashboard with mount path `/data`, this makes the app use it. If you didn’t add a volume yet, you can still deploy; responses will just be lost on restart until you add one.

Optional (for thank-you links):

```bash
railway variables --set WEDDING_SITE_URL=https://www.ryanandcarlygethitched.com
```

---

## 7. Deploy

From inside `rsvp_flask`:

```bash
railway up
```

Railway will build and deploy this folder. Because you’re running the command from `rsvp_flask`, that directory is the root automatically—no need to set Root Directory on the website.

---

## 8. Get your URL

```bash
railway domain
```

Or open the project in the Railway dashboard and generate a domain under your service’s **Settings → Networking**. Use that URL as your RSVP backend and for **`/data`** to download responses.

---

## Summary (copy-paste)

```bash
brew install railway
railway login
cd /Users/carlysoup/Library/CloudStorage/OneDrive-McMasterUniversity/Marriage/rsvp_flask
railway link
railway variables --set RSVP_RESPONSES_DIR=/data
railway up
railway domain
```

After the first time, you can just run `railway up` from `rsvp_flask` to redeploy.
