# EyeconLabs VPS Deployment (A–Z)

This document shows how to deploy and operate this repository on a VPS so you get:

- **Marketing site**: `https://eyeconlabs.com` (static export from `Site/`)
- **Portal + API**: `https://app.eyeconlabs.com` (Next.js portal + FastAPI API at `/api`)
- **Bots / Broadcaster**: long-running services on the same VPS

---

## 0) What you’re deploying

### Domains
- **Root domain**: `eyeconlabs.com` (+ `www.eyeconlabs.com`) → serves `Site/` (static)
- **Subdomain**: `app.eyeconlabs.com` → serves:
  - Next.js portal at `/` (e.g. `/login`)
  - FastAPI API at `/api/*`

### Services (ports)
- **Nginx**: 80/443 (public)
- **Next.js**: `127.0.0.1:3000` (internal)
- **FastAPI**: `127.0.0.1:8000` (internal)

---

## 1) VPS sizing notes for 50+ Telegram accounts

Your OVH VPS-2 (6 vCores / 12 GB RAM / NVMe) is **fine** to run everything.

What will limit you is usually **Telegram** (FloodWait/spam bans), not CPU.

Recommended operational notes when you’re at **50+ accounts**:

- Use **longer delays** and account rotation; don’t blast from all accounts at once.
- Keep **bots + broadcaster** running under `systemd` and monitor logs.
- **Plan to migrate from SQLite to Postgres** if you have many clients/logs (SQLite works to start, but will become a bottleneck eventually).
- Consider **separating broadcaster workers** later (another VPS) if you scale hard, to isolate load and avoid one-machine single point of failure.

---

## 2) Buy domain on GoDaddy + configure DNS

In GoDaddy DNS for `eyeconlabs.com`:

### Required records
- **A** record
  - **Host**: `@`
  - **Points to**: `<YOUR_VPS_PUBLIC_IP>`

- **A** record
  - **Host**: `app`
  - **Points to**: `<YOUR_VPS_PUBLIC_IP>`

### Recommended records
- **CNAME** record
  - **Host**: `www`
  - **Points to**: `eyeconlabs.com`

DNS propagation can take a few minutes to a few hours.

---

## 3) Initial VPS setup (Ubuntu recommended)

### 3.1 Create a non-root user + SSH hardening
(Commands below are the standard approach. If you’re not comfortable, do it with a sysadmin.)

- Create user (example `deploy`)
- Add SSH key
- Disable root password login
- Enable firewall

### 3.2 Firewall (UFW)
Allow only:
- `22` (SSH)
- `80` (HTTP)
- `443` (HTTPS)

---

## 4) Install system packages

### Install Nginx + Certbot
- Install `nginx`
- Install `certbot` + nginx plugin

### Install Python
- Python 3 + `python3-venv`

### Install Node.js
Use either:
- NodeSource packages, or
- `nvm` (recommended)

Use an LTS Node version (18 or 20).

---

## 5) Deploy the repo to the VPS

### 5.1 Upload / clone
Put the repo somewhere like:
- `/opt/eyeconlabs`

### 5.2 Backend environment file
Create:
- `/opt/eyeconlabs/backend/.env`

Example keys you will likely need:
- `SECRET_KEY=...`
- `ADMIN_USERNAME=...`
- `ADMIN_PASSWORD=...`
- `DATABASE_PATH=/opt/eyeconlabs/data/eyeconbumps_webapp.db`
- Telegram bot tokens / API creds (whatever your project uses)

### 5.3 Create a data directory
Example:
- `/opt/eyeconlabs/data/`

Store:
- database file
- uploads
- group files

### 5.4 Python install (backend)
Inside `/opt/eyeconlabs/backend`:
- create venv
- `pip install -r requirements.txt`

### 5.5 Node install (frontend)
Inside `/opt/eyeconlabs/frontend`:
- `npm ci`
- `npm run build`

---

## 6) Serve the marketing site (root domain)

### 6.1 Copy the static site
Copy the contents of repo folder:
- `/opt/eyeconlabs/Site/*`

to a web root like:
- `/var/www/eyeconlabs-site/`

Make sure it contains:
- `/var/www/eyeconlabs-site/page.html`
- `/var/www/eyeconlabs-site/about/page.html`
- etc.

---

## 7) Nginx configuration (two server blocks)

### 7.1 `app.eyeconlabs.com` (portal + API)
Your repo already includes a template at:
- `deploy/nginx.conf`

Install it as:
- `/etc/nginx/sites-available/app.eyeconlabs.com`

Symlink to enabled:
- `/etc/nginx/sites-enabled/app.eyeconlabs.com`

It proxies:
- `/` → Next.js `127.0.0.1:3000`
- `/api/` → FastAPI `127.0.0.1:8000/api/`

### 7.2 `eyeconlabs.com` (marketing site)
Create a second nginx site file, for example:
- `/etc/nginx/sites-available/eyeconlabs.com`

Template:

```nginx
server {
    listen 80;
    server_name eyeconlabs.com www.eyeconlabs.com;

    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name eyeconlabs.com www.eyeconlabs.com;

    ssl_certificate /etc/letsencrypt/live/eyeconlabs.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/eyeconlabs.com/privkey.pem;

    root /var/www/eyeconlabs-site;
    index page.html;

    location / {
        try_files $uri $uri/ $uri/page.html /page.html;
    }
}
```

---

## 8) SSL certificates (Let’s Encrypt)

After DNS is pointing to the VPS, run certbot for all hostnames:

- `eyeconlabs.com`
- `www.eyeconlabs.com`
- `app.eyeconlabs.com`

If you use certbot nginx plugin, it can auto-configure cert paths.

---

## 9) Run everything as services (systemd)

You want these always running, auto-restarting on crashes/reboots:

- **FastAPI** (uvicorn)
- **Next.js** (`next start`)
- **Bots** (collector bot, broadcaster worker)

### 9.1 FastAPI systemd example
Create a unit like `/etc/systemd/system/eyeconlabs-api.service` that runs:

- Working directory: `/opt/eyeconlabs/backend`
- Exec: `uvicorn main:app --host 127.0.0.1 --port 8000`

### 9.2 Next.js systemd example
Create `/etc/systemd/system/eyeconlabs-web.service` that runs:

- Working directory: `/opt/eyeconlabs/frontend`
- Exec: `npm run start -- --port 3000`

### 9.3 Bot services
Create one service per bot/worker, for example:

- `eyeconlabs-template-bot.service`
- `eyeconlabs-broadcaster.service`

Run them from `/opt/eyeconlabs/backend` with your existing entrypoints.

### Logs
Use:
- `journalctl -u <service> -f`

---

## 10) Operational runbook: “How to run ads” (campaign workflow)

### A) Add Telegram accounts
In the portal:
- Go to accounts
- Add session/phone
- Verify login

Best practice for 50+ accounts:
- Warm up accounts gradually
- Don’t join/send too aggressively
- Keep per-account delays and rotation conservative

### B) Create message templates (formatted ads)
Use your template collector bot (the Telegram bot in your project):
- Send your client token
- Send your formatted message (with emojis/formatting/media)
- Save it as a template name

### C) Upload / manage target groups
In admin panel:
- Upload group lists / manage group files
- Make sure accounts can access/join those groups

### D) Create a campaign
In client portal:
- Campaign name
- Select accounts
- Select template or paste message
- Set delay

### E) Start broadcasting
- Start campaign
- Monitor logs/analytics
- Stop campaign if FloodWait/spam signals show up

### F) Monitoring checklist
- Watch for FloodWait and slowmode errors
- Ensure accounts aren’t getting restricted
- Keep delays higher than you think you need

---

## 11) Backups

At minimum back up:
- `/opt/eyeconlabs/data/` (DB + uploads)
- `.env` files (securely)

OVH daily VPS backup helps, but also do periodic offsite backups.

---

## 12) Quick “does it work?” checklist

- `https://eyeconlabs.com` loads the marketing site
- `https://app.eyeconlabs.com/login` loads the portal
- `https://app.eyeconlabs.com/api/health` returns healthy JSON
- systemd services are enabled and restart on reboot

