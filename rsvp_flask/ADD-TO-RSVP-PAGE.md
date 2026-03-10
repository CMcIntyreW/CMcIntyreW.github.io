# Add this to your RSVP page (rsvp.html)

If your wedding site (with index.html, venue.html, **rsvp.html**) is hosted somewhere **other** than Railway (e.g. GitHub Pages at www.ryanandcarlygethitched.com), the RSVP form needs to know where to send submissions.

## What to add

Open your **rsvp.html** in the main wedding site repo. Inside the `<head>` section (near the top, after `<meta charset="...">` or the title), add this line:

```html
<meta name="rsvp-backend-url" content="https://YOUR-RAILWAY-URL.up.railway.app" />
```

**Replace `YOUR-RAILWAY-URL`** with the real URL Railway gave you. Examples:
- From the Railway dashboard: copy the domain (e.g. `zestful-harmony-production-a1b2.up.railway.app`).
- Or run `railway domain` in the terminal (from the `rsvp_flask` folder) to see or create the URL.

### Example (after you replace the URL)

```html
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="rsvp-backend-url" content="https://zestful-harmony-production-xxxx.up.railway.app" />
  <title>RSVP | Ryan & Carly Get Hitched</title>
  ...
</head>
```

Save the file and redeploy your static site (e.g. push to GitHub if you use GitHub Pages). After that, when someone submits the RSVP form, it will send the data to your Railway app and you can download responses at **https://YOUR-RAILWAY-URL.up.railway.app/data**.
