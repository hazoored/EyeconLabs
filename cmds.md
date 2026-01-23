# Ubuntu 24.04 VPS Commands (EyeconLabs)

This file is **copy/paste commands** to set up:

- Marketing site: `https://eyeconlabs.com` (+ `www.eyeconlabs.com`) → static `Site/`
- Portal + API: `https://app.eyeconlabs.com` → Next.js on `/` and FastAPI on `/api`
- Long-running bots/workers via `systemd`

Assumptions:
- Your VPS public IP = `$VPS_IP`
- You own the domain on GoDaddy
- You will deploy this repo to `/opt/eyeconlabs`

---

## 0) DNS (GoDaddy)

Do this first:

- A record `@` → `$VPS_IP`
- A record `app` → `$VPS_IP`
- CNAME `www` → `eyeconlabs.com`

Wait for propagation.

---

## 1) Server updates + basics

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install ca-certificates curl gnupg git unzip
```

---

## 2) Create deploy user (recommended)

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
```

(Optional) allow passwordless sudo (only if you understand the risk):

```bash
sudo visudo
```

Add:

```
deploy ALL=(ALL) NOPASSWD:ALL
```

---

## 3) Firewall (UFW)

```bash
sudo apt -y install ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

---

## 4) Install Nginx

```bash
sudo apt -y install nginx
sudo systemctl enable --now nginx
```

---

## 5) Install Certbot (Let’s Encrypt)

```bash
sudo apt -y install certbot python3-certbot-nginx
```

---

## 6) Install Python venv tools

```bash
sudo apt -y install python3-venv python3-pip
```

---

## 7) Install Node.js via nvm (simplest for Ubuntu 24.04)

As the `deploy` user:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

Reload shell:

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```

Install Node LTS:

```bash
nvm install 20
nvm use 20
node -v
npm -v
```

---

## 8) Deploy the repo

### Option A: git clone (recommended)

```bash
sudo mkdir -p /opt/eyeconlabs
sudo chown -R deploy:deploy /opt/eyeconlabs
cd /opt/eyeconlabs
# Replace with your repo URL
git clone <YOUR_REPO_GIT_URL> .
```

### Option B: upload manually (SCP/SFTP)
Upload your project folder to `/opt/eyeconlabs`.

---

## 9) Backend setup (FastAPI)

```bash
cd /opt/eyeconlabs/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create backend env file:

```bash
nano /opt/eyeconlabs/backend/.env
```

Example (adjust):

```dotenv
SECRET_KEY=CHANGE_ME_LONG_RANDOM
ADMIN_USERNAME=admin
ADMIN_PASSWORD=CHANGE_ME
DATABASE_PATH=/opt/eyeconlabs/data/eyeconbumps_webapp.db
```

Create data folder:

```bash
sudo mkdir -p /opt/eyeconlabs/data
sudo chown -R deploy:deploy /opt/eyeconlabs/data
```

---

## 10) Frontend setup (Next.js portal)

```bash
cd /opt/eyeconlabs/frontend
npm ci
npm run build
```

Make sure `/opt/eyeconlabs/frontend/.env.production` has:

```dotenv
NEXT_PUBLIC_API_URL=https://app.eyeconlabs.com/api
```

---

## 11) Nginx configs (two domains)

### 11.1 app subdomain (portal + api)

Copy repo config:

```bash
sudo cp /opt/eyeconlabs/deploy/nginx.conf /etc/nginx/sites-available/app.eyeconlabs.com
sudo ln -sf /etc/nginx/sites-available/app.eyeconlabs.com /etc/nginx/sites-enabled/app.eyeconlabs.com
```

### 11.2 root domain (marketing site)

Create site folder and copy marketing pages:

```bash
sudo mkdir -p /var/www/eyeconlabs-site
sudo rsync -av --delete /opt/eyeconlabs/Site/ /var/www/eyeconlabs-site/
```

Create nginx file:

```bash
sudo nano /etc/nginx/sites-available/eyeconlabs.com
```

Paste:

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

Enable:

```bash
sudo ln -sf /etc/nginx/sites-available/eyeconlabs.com /etc/nginx/sites-enabled/eyeconlabs.com
```

Disable default site:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

Test + reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 12) Get SSL certs (Certbot)

Run these after DNS works:

```bash
sudo certbot --nginx -d app.eyeconlabs.com
sudo certbot --nginx -d eyeconlabs.com -d www.eyeconlabs.com
```

Verify auto-renew:

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

---

## 13) systemd services (always-on)

### 13.1 FastAPI service

Create:

```bash
sudo nano /etc/systemd/system/eyeconlabs-api.service
```

Paste:

```ini
[Unit]
Description=EyeconLabs FastAPI API
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/eyeconlabs/backend
EnvironmentFile=/opt/eyeconlabs/backend/.env
ExecStart=/opt/eyeconlabs/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now eyeconlabs-api
sudo systemctl status eyeconlabs-api --no-pager
```

Logs:

```bash
journalctl -u eyeconlabs-api -f
```

### 13.2 Next.js service

Create:

```bash
sudo nano /etc/systemd/system/eyeconlabs-web.service
```

Paste:

```ini
[Unit]
Description=EyeconLabs Next.js Portal
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/eyeconlabs/frontend
Environment=NODE_ENV=production
ExecStart=/usr/bin/env bash -lc 'cd /opt/eyeconlabs/frontend && export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && nvm use 20 && npm run start -- --port 3000'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now eyeconlabs-web
sudo systemctl status eyeconlabs-web --no-pager
```

Logs:

```bash
journalctl -u eyeconlabs-web -f
```

### 13.3 Bots / broadcaster services

You need to confirm the correct entrypoints in your backend. Common patterns:
- `python bot_runner.py`
- `python broadcaster.py`

Create one service per process:

```bash
sudo nano /etc/systemd/system/eyeconlabs-bot-runner.service
```

Example template:

```ini
[Unit]
Description=EyeconLabs Bot Runner
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/eyeconlabs/backend
EnvironmentFile=/opt/eyeconlabs/backend/.env
ExecStart=/opt/eyeconlabs/backend/.venv/bin/python bot_runner.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now eyeconlabs-bot-runner
journalctl -u eyeconlabs-bot-runner -f
```

Repeat similarly for broadcaster if needed.

---

## 14) Quick verification

```bash
curl -s https://app.eyeconlabs.com/api/health | cat
```

Open in browser:
- `https://eyeconlabs.com`
- `https://app.eyeconlabs.com/login`

---

## 15) Updating deployments

### Backend updates

```bash
cd /opt/eyeconlabs
git pull
cd backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart eyeconlabs-api
```

### Frontend updates

```bash
cd /opt/eyeconlabs
git pull
cd frontend
npm ci
npm run build
sudo systemctl restart eyeconlabs-web
```

### Marketing site updates

```bash
sudo rsync -av --delete /opt/eyeconlabs/Site/ /var/www/eyeconlabs-site/
sudo systemctl reload nginx
```
