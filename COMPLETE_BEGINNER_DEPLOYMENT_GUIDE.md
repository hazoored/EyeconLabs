# 🚀 Complete Beginner's Guide to Deploying EyeconLabs.com

**You bought a domain from GoDaddy and a VPS from OVH Cloud. This guide will walk you through EVERY step to get your website live.**

No prior experience needed - I'll explain exactly where to click and what to do.

---

## 📋 What You're Building

You'll have:
- **Main website**: `eyeconlabs.com` (marketing pages)
- **App portal**: `app.eyeconlabs.com` (login/dashboard)
- **API**: `app.eyeconlabs.com/api` (backend services)

---

## 🔧 Before You Start - What You Need

1. **Your OVH VPS IP address** (find it in OVH dashboard)
2. **GoDaddy login** (where you bought eyeconlabs.com)
3. **SSH client** (Windows: use PuTTY or Windows Terminal, Mac/Linux: built-in Terminal)
4. **Your project code** (the EyeconBumps repository)

---

## 🌐 Step 1: Configure DNS on GoDaddy

**Time: 5 minutes | Difficulty: Easy**

1. **Go to GoDaddy.com** → Login → My Products → Domain Settings → eyeconlabs.com
2. **Click "DNS"** under "Additional Settings"
3. **Add these records:**

   **Record 1 - Main Domain:**
   - Type: `A`
   - Name: `@` 
   - Value: `YOUR_VPS_IP` (replace with your actual OVH IP)
   - TTL: `1 Hour`

   **Record 2 - App Subdomain:**
   - Type: `A`
   - Name: `app`
   - Value: `YOUR_VPS_IP` (same IP)
   - TTL: `1 Hour`

   **Record 3 - WWW:**
   - Type: `CNAME`
   - Name: `www`
   - Value: `eyeconlabs.com`
   - TTL: `1 Hour`

4. **Save changes** - DNS can take 5-30 minutes to work

---

## 🖥️ Step 2: Connect to Your VPS

**Time: 10 minutes | Difficulty: Easy**

1. **Find your VPS IP in OVH dashboard**
2. **Open Terminal/PuTTY** and connect:
   ```bash
   ssh root@YOUR_VPS_IP
   ```
3. **Accept the fingerprint** (type 'yes')
4. **Enter your root password** (from OVH)

---

## 🛡️ Step 3: Basic Server Security

**Time: 15 minutes | Difficulty: Medium**

### 3.1 Create a User (safer than using root)

```bash
# Create a user named 'deploy'
adduser deploy

# Add admin rights
usermod -aG sudo deploy

# Switch to your new user
su - deploy
```

### 3.2 Setup Firewall

```bash
# Go back to root for setup
exit

# Install and configure firewall
sudo apt update && sudo apt -y upgrade
sudo apt -y install ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

### 3.3 Switch back to deploy user

```bash
su - deploy
```

---

## 📦 Step 4: Install Required Software

**Time: 20 minutes | Difficulty: Medium**

### 4.1 Install Basic Tools

```bash
sudo apt -y install ca-certificates curl gnupg git unzip nginx python3-venv python3-pip
```

### 4.2 Install Node.js

```bash
# Install Node Version Manager
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Reload your shell
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Install Node.js LTS
nvm install 20
nvm use 20

# Verify installation
node -v
npm -v
```

### 4.3 Install SSL Certificate Tool

```bash
sudo apt -y install certbot python3-certbot-nginx
```

---

## 📁 Step 5: Upload Your Project

**Time: 15 minutes | Difficulty: Medium**

### Option A: Using Git (Recommended)

```bash
# Create project directory
sudo mkdir -p /opt/eyeconlabs
sudo chown -R deploy:deploy /opt/eyeconlabs

# Go to directory
cd /opt/eyeconlabs

# Clone your repository (replace with your actual repo URL)
git clone https://github.com/YOUR_USERNAME/EyeconBumps.git .
```

### Option B: Manual Upload (if no Git)

1. **Use FileZilla or SCP** to upload your project files to `/home/deploy/`
2. **Move files to correct location:**
   ```bash
   sudo mkdir -p /opt/eyeconlabs
   sudo mv /home/deploy/EyeconBumps/* /opt/eyeconlabs/
   sudo chown -R deploy:deploy /opt/eyeconlabs
   ```

---

## 🐍 Step 6: Setup Backend (Python/FastAPI)

**Time: 10 minutes | Difficulty: Medium**

```bash
# Go to backend directory
cd /opt/eyeconlabs/backend

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 6.1 Create Environment File

```bash
nano /opt/eyeconlabs/backend/.env
```

**Paste this content** (modify the values):

```env
SECRET_KEY=CHANGE_THIS_TO_A_LONG_RANDOM_STRING
ADMIN_USERNAME=admin
ADMIN_PASSWORD=CHANGE_THIS_TO_A_STRONG_PASSWORD
DATABASE_PATH=/opt/eyeconlabs/data/eyeconbumps_webapp.db
```

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

### 6.2 Create Data Directory

```bash
sudo mkdir -p /opt/eyeconlabs/data
sudo chown -R deploy:deploy /opt/eyeconlabs/data
```

---

## ⚛️ Step 7: Setup Frontend (Next.js)

**Time: 15 minutes | Difficulty: Medium**

```bash
# Go to frontend directory
cd /opt/eyeconlabs/frontend

# Install dependencies
npm ci

# Build for production
npm run build
```

### 7.1 Create Production Environment File

```bash
nano /opt/eyeconlabs/frontend/.env.production
```

**Add this line:**

```env
NEXT_PUBLIC_API_URL=https://app.eyeconlabs.com/api
```

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

---

## 🌐 Step 8: Configure Web Server (Nginx)

**Time: 20 minutes | Difficulty: Hard**

### 8.1 Setup App Subdomain (Portal + API)

```bash
# Copy the nginx config from your project
sudo cp /opt/eyeconlabs/deploy/nginx.conf /etc/nginx/sites-available/app.eyeconlabs.com

# Enable the site
sudo ln -sf /etc/nginx/sites-available/app.eyeconlabs.com /etc/nginx/sites-enabled/app.eyeconlabs.com
```

### 8.2 Setup Main Domain (Marketing Site)

```bash
# Create site directory
sudo mkdir -p /var/www/eyeconlabs-site

# Copy your marketing pages
sudo rsync -av --delete /opt/eyeconlabs/Site/ /var/www/eyeconlabs-site/

# Create nginx config
sudo nano /etc/nginx/sites-available/eyeconlabs.com
```

**Paste this entire config:**

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

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

### 8.3 Enable Sites and Test

```bash
# Enable main site
sudo ln -sf /etc/nginx/sites-available/eyeconlabs.com /etc/nginx/sites-enabled/eyeconlabs.com

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# If no errors, reload nginx
sudo systemctl reload nginx
```

---

## 🔒 Step 9: Get SSL Certificates (HTTPS)

**Time: 10 minutes | Difficulty: Easy**

**Important:** Wait until DNS propagation is complete (Step 1) before doing this.

```bash
# Get SSL for app subdomain
sudo certbot --nginx -d app.eyeconlabs.com

# Get SSL for main domain
sudo certbot --nginx -d eyeconlabs.com -d www.eyeconlabs.com
```

**Follow the prompts:**
- Enter your email
- Agree to terms
- Choose whether to share email (your choice)
- Choose redirect option (recommended: option 2)

---

## 🚀 Step 10: Setup Auto-Starting Services

**Time: 25 minutes | Difficulty: Hard**

### 10.1 Backend API Service

```bash
sudo nano /etc/systemd/system/eyeconlabs-api.service
```

**Paste this:**

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

### 10.2 Frontend Web Service

```bash
sudo nano /etc/systemd/system/eyeconlabs-web.service
```

**Paste this:**

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

### 10.3 Bot Service (if you have bots)

```bash
sudo nano /etc/systemd/system/eyeconlabs-bot-runner.service
```

**Paste this:**

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

### 10.4 Enable and Start All Services

```bash
# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable and start API
sudo systemctl enable --now eyeconlabs-api

# Enable and start web frontend
sudo systemctl enable --now eyeconlabs-web

# Enable and start bot (if you have it)
sudo systemctl enable --now eyeconlabs-bot-runner

# Check status of all services
sudo systemctl status eyeconlabs-api --no-pager
sudo systemctl status eyeconlabs-web --no-pager
sudo systemctl status eyeconlabs-bot-runner --no-pager
```

---

## ✅ Step 11: Test Everything

**Time: 5 minutes | Difficulty: Easy**

### 11.1 Test API Health

```bash
curl -s https://app.eyeconlabs.com/api/health
```

You should see a JSON response like `{"status": "healthy"}`

### 11.2 Test Websites in Browser

Open these URLs in your browser:

1. **https://eyeconlabs.com** → Should show your marketing site
2. **https://app.eyeconlabs.com** → Should show your app portal
3. **https://app.eyeconlabs.com/login** → Should show login page

### 11.3 Check Service Logs (if something doesn't work)

```bash
# API logs
sudo journalctl -u eyeconlabs-api -f

# Web logs
sudo journalctl -u eyeconlabs-web -f

# Bot logs
sudo journalctl -u eyeconlabs-bot-runner -f
```

Press `Ctrl+C` to exit logs

---

## 🔄 Step 12: How to Update Your Site Later

**Time: 5 minutes | Difficulty: Easy**

### Update Backend

```bash
cd /opt/eyeconlabs
git pull
cd backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart eyeconlabs-api
```

### Update Frontend

```bash
cd /opt/eyeconlabs
git pull
cd frontend
npm ci
npm run build
sudo systemctl restart eyeconlabs-web
```

### Update Marketing Site

```bash
sudo rsync -av --delete /opt/eyeconlabs/Site/ /var/www/eyeconlabs-site/
sudo systemctl reload nginx
```

---

## 🆘 Troubleshooting Common Issues

### "Site not found" or DNS errors
- **Wait longer** - DNS can take up to 24 hours
- **Check GoDaddy DNS settings** - make sure IP is correct
- **Use a DNS checker** like whatsmydns.net

### "502 Bad Gateway" error
- **Check if services are running:** `sudo systemctl status eyeconlabs-api`
- **Check logs:** `sudo journalctl -u eyeconlabs-api -f`
- **Restart services:** `sudo systemctl restart eyeconlabs-api`

### SSL certificate errors
- **Make sure DNS is working first**
- **Check certbot status:** `sudo certbot certificates`
- **Renew manually:** `sudo certbot renew`

### Permission errors
- **Make sure deploy user owns files:** `sudo chown -R deploy:deploy /opt/eyeconlabs`
- **Check file permissions:** `ls -la /opt/eyeconlabs/`

---

## 🎉 Congratulations! 

Your EyeconLabs website is now live! You have:
- ✅ Marketing site at `https://eyeconlabs.com`
- ✅ App portal at `https://app.eyeconlabs.com`
- ✅ API at `https://app.eyeconlabs.com/api`
- ✅ SSL certificates (HTTPS)
- ✅ Auto-restarting services

---

## 📞 Need Help?

If you get stuck:
1. **Check the logs** - they usually tell you what's wrong
2. **Google the error message** - someone else probably had the same issue
3. **Restart services** - fixes many problems
4. **Check file permissions** - common cause of issues

Remember: Every developer breaks things. The key is learning how to fix them!

---

**🌟 You just deployed a real web application. That's impressive!**
