# Future Tech Cyber Security Academy — Deployment Guide

## 1. Overview
Future Tech Cyber Security Academy is designed for automated containerized deployment using Docker Compose, Kubernetes, or conventional virtual machines behind an Nginx reverse proxy.

---

## 2. Docker Compose Deployment

The platform includes a production-ready `docker-compose.yml` with isolated internal networking:
- **`web`**: Django 4.2 application server running on Python 3.12 with Gunicorn / ASGI.
- **`postgres`**: PostgreSQL 15 database (unexposed to host; internal network only).
- **`redis`**: In-memory message broker and caching engine.

### Launching the Stack:
```bash
# 1. Configure environment
cp .env.example .env

# Edit .env and ensure DEBUG=False, production SECRET_KEY, and ALLOWED_HOSTS are configured

# 2. Build and start containers
docker compose up -d --build

# 3. Apply database migrations inside container
docker compose exec web python manage.py migrate

# 4. Seed demo curriculum
docker compose exec web python manage.py seed_demo_data

# 5. Collect static assets
docker compose exec web python manage.py collectstatic --noinput
```

---

## 3. Production Security Checklist

When deploying to a public domain (e.g. `academy.college.edu`):
1. **Set `DJANGO_SETTINGS_MODULE=config.settings.production`**.
2. **`DEBUG = False`**: Enforced in `production.py` to prevent stack trace disclosures.
3. **SSL/TLS & HSTS**:
   - `SECURE_SSL_REDIRECT = True`
   - `SECURE_HSTS_SECONDS = 31536000` (1 Year)
   - `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
   - `SECURE_HSTS_PRELOAD = True`
4. **Secure Cookies**:
   - `SESSION_COOKIE_SECURE = True`
   - `CSRF_COOKIE_SECURE = True`
   - `SESSION_COOKIE_HTTPONLY = True`
5. **Frame Options**:
   - `X_FRAME_OPTIONS = 'DENY'` to block clickjacking attacks.

---

## 4. Sample Nginx Reverse Proxy Configuration

```nginx
server {
    listen 80;
    server_name academy.example.edu;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name academy.example.edu;

    ssl_certificate /etc/letsencrypt/live/academy.example.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/academy.example.edu/privkey.pem;

    client_max_body_size 30M;

    location /static/ {
        alias /var/www/futuretech/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias /var/www/futuretech/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

