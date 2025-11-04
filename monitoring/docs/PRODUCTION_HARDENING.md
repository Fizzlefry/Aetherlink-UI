# Production Hardening Guide - External Access & Security

## 🔒 Overview

This guide covers production hardening for your monitoring stack:
1. **External URL Configuration** - Make Slack buttons work from anywhere
2. **Authentication & Authorization** - Protect Alertmanager silence endpoint
3. **TLS/SSL Configuration** - Secure communications
4. **Reverse Proxy Patterns** - Nginx, Traefik, Caddy

---

## 🌐 Part 1: External URL Configuration

### Problem: Localhost URLs Don't Work Remotely

**Current Slack buttons** (localhost - only works on same machine):
```
[📊 Dashboard] → http://localhost:3000/d/crm-events-pipeline
[🔍 Prometheus] → http://localhost:9090/alerts
[🔕 Silence]   → http://localhost:9093/#/silences/new
```

**Production Slack buttons** (external hostnames - work from anywhere):
```
[📊 Dashboard] → https://grafana.aetherlink.local/d/crm-events-pipeline
[🔍 Prometheus] → https://prometheus.aetherlink.local/alerts
[🔕 Silence]   → https://alertmanager.aetherlink.local/#/silences/new
```

---

### Solution 1: Internal DNS + VPN (Recommended for Internal Teams)

**Setup**:
1. Add internal DNS entries
2. Configure reverse proxy
3. Update Alertmanager URLs
4. Team accesses via VPN

**DNS Configuration** (Windows Server DNS or hosts file):
```
# C:\Windows\System32\drivers\etc\hosts (on each team member's machine)
192.168.1.100  grafana.aetherlink.local
192.168.1.100  prometheus.aetherlink.local
192.168.1.100  alertmanager.aetherlink.local
```

**Alertmanager Configuration**:
```yaml
# monitoring/alertmanager.yml
global:
  external_url: 'http://alertmanager.aetherlink.local'

receivers:
  - name: slack_crm
    slack_configs:
      - actions:
          - type: button
            text: "📊 View Dashboard"
            url: "http://grafana.aetherlink.local/d/crm-events-pipeline"
          
          - type: button
            text: "🔍 Prometheus Alerts"
            url: "http://prometheus.aetherlink.local/alerts"
          
          - type: button
            text: "🔕 Silence 1h"
            url: "http://alertmanager.aetherlink.local/#/silences/new?filter=%7Bservice%3D%22crm-events-sse%22%2Cteam%3D%22crm%22%7D"
```

---

### Solution 2: Public DNS + TLS (Recommended for Remote Teams)

**Setup**:
1. Register domain: `aetherlink.com`
2. Create subdomains: `grafana.aetherlink.com`, `alertmanager.aetherlink.com`
3. Get TLS certificates (Let's Encrypt)
4. Configure reverse proxy with TLS + auth

**Alertmanager Configuration**:
```yaml
# monitoring/alertmanager.yml
global:
  external_url: 'https://alertmanager.aetherlink.com'

receivers:
  - name: slack_crm
    slack_configs:
      - actions:
          - type: button
            text: "📊 View Dashboard"
            url: "https://grafana.aetherlink.com/d/crm-events-pipeline"
          
          - type: button
            text: "🔍 Prometheus Alerts"
            url: "https://prometheus.aetherlink.com/alerts"
          
          - type: button
            text: "🔕 Silence 1h"
            url: "https://alertmanager.aetherlink.com/#/silences/new?filter=%7Bservice%3D%22crm-events-sse%22%2Cteam%3D%22crm%22%7D"
```

---

## 🔐 Part 2: Authentication & Authorization

### Problem: Alertmanager Silence Endpoint is Powerful

Anyone with access to Alertmanager can silence alerts. This can mask real issues.

### Solution: Add Authentication Layer

---

### Option 1: Nginx Reverse Proxy with Basic Auth (Simple)

**File Structure**:
```
monitoring/
├─ nginx/
│  ├─ nginx.conf
│  ├─ .htpasswd
│  └─ Dockerfile
├─ docker-compose.yml
└─ alertmanager.yml
```

**Create Password File**:
```powershell
# Install htpasswd (from Apache Utils or via Docker)
docker run --rm httpd:alpine htpasswd -nbB admin "SecurePassword123" > monitoring/nginx/.htpasswd

# Output: admin:$2y$05$...encrypted...
```

**Nginx Configuration** (`monitoring/nginx/nginx.conf`):
```nginx
# monitoring/nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    # Upstream services
    upstream grafana {
        server grafana:3000;
    }

    upstream prometheus {
        server prometheus:9090;
    }

    upstream alertmanager {
        server alertmanager:9093;
    }

    # Grafana (no auth - has built-in auth)
    server {
        listen 80;
        server_name grafana.aetherlink.local;

        location / {
            proxy_pass http://grafana;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # Prometheus (read-only - basic auth)
    server {
        listen 80;
        server_name prometheus.aetherlink.local;

        location / {
            auth_basic "Aetherlink Prometheus";
            auth_basic_user_file /etc/nginx/.htpasswd;

            proxy_pass http://prometheus;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

    # Alertmanager (silence endpoint - strict auth)
    server {
        listen 80;
        server_name alertmanager.aetherlink.local;

        # ✅ Silence API - Requires authentication
        location /api/v2/silences {
            auth_basic "Aetherlink Alertmanager API";
            auth_basic_user_file /etc/nginx/.htpasswd;

            proxy_pass http://alertmanager;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # ✅ Silence UI - Requires authentication
        location /#/silences {
            auth_basic "Aetherlink Alertmanager";
            auth_basic_user_file /etc/nginx/.htpasswd;

            proxy_pass http://alertmanager;
            proxy_set_header Host $host;
        }

        # Read-only endpoints (alerts, status) - No auth
        location / {
            proxy_pass http://alertmanager;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

**Nginx Dockerfile** (`monitoring/nginx/Dockerfile`):
```dockerfile
FROM nginx:alpine

# Copy nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy password file
COPY .htpasswd /etc/nginx/.htpasswd

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Docker Compose Integration**:
```yaml
# monitoring/docker-compose.yml
services:
  nginx:
    build: ./nginx
    container_name: aether-nginx
    ports:
      - "80:80"
    networks:
      - aether-monitoring
    depends_on:
      - grafana
      - prometheus
      - alertmanager
    restart: unless-stopped

  grafana:
    # Remove host port mapping (nginx handles it)
    # ports:
    #   - "3000:3000"  # ← Remove this
    expose:
      - "3000"
    environment:
      - GF_SERVER_ROOT_URL=http://grafana.aetherlink.local
      - GF_SERVER_DOMAIN=grafana.aetherlink.local

  prometheus:
    expose:
      - "9090"
    command:
      - '--web.external-url=http://prometheus.aetherlink.local'

  alertmanager:
    expose:
      - "9093"
    # external_url set in alertmanager.yml global section
```

---

### Option 2: Traefik Reverse Proxy with Basic Auth + TLS (Advanced)

**Traefik Configuration** (`monitoring/traefik/traefik.yml`):
```yaml
# monitoring/traefik/traefik.yml
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

certificatesResolvers:
  letsencrypt:
    acme:
      email: ops@aetherlink.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web

providers:
  docker:
    exposedByDefault: false

api:
  dashboard: true
```

**Traefik Labels in Docker Compose**:
```yaml
# monitoring/docker-compose.yml
services:
  traefik:
    image: traefik:v2.10
    container_name: aether-traefik
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik:/etc/traefik
      - ./letsencrypt:/letsencrypt
    networks:
      - aether-monitoring

  grafana:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grafana.rule=Host(`grafana.aetherlink.com`)"
      - "traefik.http.routers.grafana.entrypoints=websecure"
      - "traefik.http.routers.grafana.tls.certresolver=letsencrypt"
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"

  prometheus:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.prometheus.rule=Host(`prometheus.aetherlink.com`)"
      - "traefik.http.routers.prometheus.entrypoints=websecure"
      - "traefik.http.routers.prometheus.tls.certresolver=letsencrypt"
      - "traefik.http.services.prometheus.loadbalancer.server.port=9090"
      # Basic auth
      - "traefik.http.routers.prometheus.middlewares=prometheus-auth"
      - "traefik.http.middlewares.prometheus-auth.basicauth.users=admin:$$apr1$$...htpasswd..."

  alertmanager:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.alertmanager.rule=Host(`alertmanager.aetherlink.com`)"
      - "traefik.http.routers.alertmanager.entrypoints=websecure"
      - "traefik.http.routers.alertmanager.tls.certresolver=letsencrypt"
      - "traefik.http.services.alertmanager.loadbalancer.server.port=9093"
      # Basic auth for silence endpoints
      - "traefik.http.routers.alertmanager.middlewares=alertmanager-auth"
      - "traefik.http.middlewares.alertmanager-auth.basicauth.users=admin:$$apr1$$...htpasswd..."
```

---

### Option 3: Caddy Reverse Proxy (Simplest TLS)

**Caddyfile** (`monitoring/Caddyfile`):
```
# monitoring/Caddyfile

# Grafana (no auth - has built-in)
grafana.aetherlink.com {
    reverse_proxy grafana:3000
}

# Prometheus (read-only with auth)
prometheus.aetherlink.com {
    basicauth {
        admin $2a$14$...bcrypt_hash...
    }
    reverse_proxy prometheus:9090
}

# Alertmanager (silence endpoint with auth)
alertmanager.aetherlink.com {
    # Silence API requires auth
    @silence_api path /api/v2/silences*
    handle @silence_api {
        basicauth {
            admin $2a$14$...bcrypt_hash...
        }
        reverse_proxy alertmanager:9093
    }

    # Everything else (read-only)
    handle {
        reverse_proxy alertmanager:9093
    }
}
```

**Docker Compose**:
```yaml
services:
  caddy:
    image: caddy:latest
    container_name: aether-caddy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - aether-monitoring

volumes:
  caddy_data:
  caddy_config:
```

---

## 🔥 Part 3: Firewall Rules (Defense in Depth)

### Windows Firewall (Local Development)

```powershell
# Allow only from local network (192.168.1.0/24)
New-NetFirewallRule -DisplayName "Grafana (LAN Only)" `
  -Direction Inbound `
  -LocalPort 3000 `
  -Protocol TCP `
  -RemoteAddress 192.168.1.0/24 `
  -Action Allow

New-NetFirewallRule -DisplayName "Prometheus (LAN Only)" `
  -Direction Inbound `
  -LocalPort 9090 `
  -Protocol TCP `
  -RemoteAddress 192.168.1.0/24 `
  -Action Allow

New-NetFirewallRule -DisplayName "Alertmanager (LAN Only)" `
  -Direction Inbound `
  -LocalPort 9093 `
  -Protocol TCP `
  -RemoteAddress 192.168.1.0/24 `
  -Action Allow
```

### Linux iptables

```bash
# Allow only from VPN subnet (10.8.0.0/24)
iptables -A INPUT -p tcp --dport 3000 -s 10.8.0.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 3000 -j DROP

iptables -A INPUT -p tcp --dport 9090 -s 10.8.0.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 9090 -j DROP

iptables -A INPUT -p tcp --dport 9093 -s 10.8.0.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 9093 -j DROP
```

---

## 📋 Part 4: Quick Deployment Checklist

### For Internal Teams (VPN Access)

- [ ] Set up internal DNS entries (`.local` domains)
- [ ] Deploy Nginx reverse proxy with basic auth
- [ ] Update `alertmanager.yml` external_url
- [ ] Update Slack button URLs to internal hostnames
- [ ] Configure firewall to allow only VPN subnet
- [ ] Test from team member's machine on VPN
- [ ] Verify Slack buttons work (click → opens dashboard)
- [ ] Test silence endpoint (requires auth)

### For Remote Teams (Public Internet)

- [ ] Register public domain (`aetherlink.com`)
- [ ] Create DNS A records for subdomains
- [ ] Deploy Traefik/Caddy with Let's Encrypt
- [ ] Enable basic auth for Prometheus + Alertmanager
- [ ] Update `alertmanager.yml` external_url (HTTPS)
- [ ] Update Slack button URLs to public HTTPS hostnames
- [ ] Configure rate limiting (optional)
- [ ] Test from public internet (no VPN)
- [ ] Verify TLS certificates are valid
- [ ] Test silence endpoint (requires auth)

---

## 🧪 Part 5: Testing & Validation

### Test External URLs

```powershell
# Test Grafana
curl -I http://grafana.aetherlink.local/d/crm-events-pipeline
# Expected: 200 OK or 302 Redirect (if auth enabled)

# Test Prometheus
curl -I http://prometheus.aetherlink.local/alerts
# Expected: 401 Unauthorized (if auth enabled)

# Test with auth
curl -u admin:password http://prometheus.aetherlink.local/alerts
# Expected: 200 OK

# Test Alertmanager silence endpoint
curl -I http://alertmanager.aetherlink.local/api/v2/silences
# Expected: 401 Unauthorized (if auth enabled)

curl -u admin:password http://alertmanager.aetherlink.local/api/v2/silences
# Expected: 200 OK with JSON array of silences
```

### Test Slack Buttons

1. **Trigger Alert**:
   ```powershell
   docker stop aether-crm-events
   # Wait 7 minutes for alert
   ```

2. **Check Slack Message**:
   - Should have 3 buttons
   - URLs should use external hostnames (not localhost)

3. **Click [📊 View Dashboard]**:
   - Opens: `http://grafana.aetherlink.local/d/crm-events-pipeline`
   - Should work from any machine (not just server)

4. **Click [🔕 Silence 1h]**:
   - Opens: `http://alertmanager.aetherlink.local/#/silences/new`
   - Should prompt for username/password (if auth enabled)
   - Form should be pre-filled with: `service="crm-events-sse"` and `team="crm"`

5. **Create Silence**:
   - Duration: 1h
   - Comment: "Working on hot-key issue"
   - Click Create
   - Verify at: `http://alertmanager.aetherlink.local/#/silences`

---

## 🔐 Part 6: Default Credentials Management

### Create Team Accounts

```powershell
# Generate multiple users for .htpasswd
docker run --rm httpd:alpine htpasswd -nbB alice "AlicePass123" >> .htpasswd
docker run --rm httpd:alpine htpasswd -nbB bob "BobPass456" >> .htpasswd
docker run --rm httpd:alpine htpasswd -nbB ops "OpsSecure789" >> .htpasswd
```

### Rotate Credentials Quarterly

```powershell
# Update password for user
docker run --rm httpd:alpine htpasswd -nbB admin "NewPassword123" > .htpasswd.new
mv .htpasswd.new .htpasswd

# Restart Nginx to pick up new passwords
docker compose restart nginx
```

### Use Secrets Management (Production)

```yaml
# docker-compose.yml with secrets
services:
  nginx:
    secrets:
      - nginx_htpasswd

secrets:
  nginx_htpasswd:
    file: ./nginx/.htpasswd
```

---

## 📊 Part 7: Recommended Configuration

### Recommended Stack for Internal Teams

```yaml
# monitoring/alertmanager.yml
global:
  external_url: 'http://alertmanager.aetherlink.local'

receivers:
  - name: slack_crm
    slack_configs:
      - actions:
          - type: button
            text: "📊 View Dashboard"
            url: "http://grafana.aetherlink.local/d/crm-events-pipeline"
            style: "primary"
          
          - type: button
            text: "🔍 Prometheus Alerts"
            url: "http://prometheus.aetherlink.local/alerts"
          
          - type: button
            text: "🔕 Silence 1h"
            # ✅ Tighter filter with team + service
            url: "http://alertmanager.aetherlink.local/#/silences/new?filter=%7Bservice%3D%22crm-events-sse%22%2Cteam%3D%22crm%22%7D"
            style: "danger"
```

### Recommended Stack for Remote Teams

```yaml
# monitoring/alertmanager.yml
global:
  external_url: 'https://alertmanager.aetherlink.com'

receivers:
  - name: slack_crm
    slack_configs:
      - actions:
          - type: button
            text: "📊 View Dashboard"
            url: "https://grafana.aetherlink.com/d/crm-events-pipeline"
            style: "primary"
          
          - type: button
            text: "🔍 Prometheus Alerts"
            url: "https://prometheus.aetherlink.com/alerts"
          
          - type: button
            text: "🔕 Silence 1h"
            url: "https://alertmanager.aetherlink.com/#/silences/new?filter=%7Bservice%3D%22crm-events-sse%22%2Cteam%3D%22crm%22%7D"
            style: "danger"
```

---

## 🎯 Quick Start Scripts

### Script 1: Setup Internal DNS

```powershell
# monitoring/setup-internal-dns.ps1
$entries = @(
    @{IP="192.168.1.100"; Hostname="grafana.aetherlink.local"},
    @{IP="192.168.1.100"; Hostname="prometheus.aetherlink.local"},
    @{IP="192.168.1.100"; Hostname="alertmanager.aetherlink.local"}
)

$hostsFile = "C:\Windows\System32\drivers\etc\hosts"

Write-Host "Adding DNS entries to hosts file..." -ForegroundColor Yellow

foreach ($entry in $entries) {
    $line = "$($entry.IP)`t$($entry.Hostname)"
    Add-Content -Path $hostsFile -Value $line
    Write-Host "  ✅ Added: $line" -ForegroundColor Green
}

Write-Host "`nDNS entries added. Test with:" -ForegroundColor Cyan
Write-Host "  ping grafana.aetherlink.local" -ForegroundColor White
```

### Script 2: Deploy Nginx Reverse Proxy

```powershell
# monitoring/deploy-nginx-proxy.ps1
Write-Host "Deploying Nginx reverse proxy..." -ForegroundColor Yellow

# Generate htpasswd
Write-Host "Creating password file..." -ForegroundColor Cyan
$password = Read-Host "Enter admin password" -AsSecureString
$passwordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

docker run --rm httpd:alpine htpasswd -nbB admin $passwordPlain | Out-File -Encoding ASCII nginx/.htpasswd
Write-Host "  ✅ Password file created" -ForegroundColor Green

# Build and start Nginx
Write-Host "Building Nginx container..." -ForegroundColor Cyan
docker compose up -d nginx

Write-Host "`n✅ Nginx deployed!" -ForegroundColor Green
Write-Host "Test with:" -ForegroundColor Cyan
Write-Host "  curl -u admin:password http://alertmanager.aetherlink.local" -ForegroundColor White
```

---

## 🏆 Final Hardened Configuration

**What You Get**:
- ✅ External URLs (work from anywhere, not just localhost)
- ✅ Basic auth on Alertmanager silence endpoint
- ✅ Tighter silence filters (service + team)
- ✅ Firewall rules (VPN/LAN only)
- ✅ TLS option (Let's Encrypt)
- ✅ Production-ready reverse proxy

**Security Layers**:
1. **Network**: Firewall (VPN/LAN only)
2. **Authentication**: Basic auth (username/password)
3. **Authorization**: Read-only vs write access
4. **Encryption**: TLS/SSL (for remote teams)

**Result**: Your team can safely silence alerts from Slack without exposing the endpoint to the world. 🎯
