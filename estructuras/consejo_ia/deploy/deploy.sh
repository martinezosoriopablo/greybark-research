#!/bin/bash
# deploy.sh — VPS Setup & Deployment Script
# Usage: bash deploy.sh <domain> <email>
# Example: bash deploy.sh research.greybark.com admin@greybark.com

set -euo pipefail

DOMAIN="${1:?Usage: deploy.sh <domain> <email>}"
EMAIL="${2:?Usage: deploy.sh <domain> <email>}"

echo "=== Greybark Research Portal — Deploy ==="
echo "Domain: $DOMAIN"
echo "Email:  $EMAIL"
echo ""

# ── 1. System packages ─────────────────────────

echo "→ Installing system packages..."
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-plugin ufw fail2ban

systemctl enable docker
systemctl start docker

# ── 2. Firewall ─────────────────────────────────

echo "→ Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ── 3. Directories ──────────────────────────────

echo "→ Creating directories..."
mkdir -p /opt/greybark/data/output
mkdir -p /opt/greybark/backups

# ── 4. SSL certificate ─────────────────────────

echo "→ Obtaining SSL certificate..."
# First run with HTTP-only nginx for cert issuance
docker run --rm -v greybark_certs:/etc/letsencrypt \
    -v greybark_certbot-www:/var/www/certbot \
    -p 80:80 certbot/certbot certonly \
    --standalone --agree-tos --no-eff-email \
    -d "$DOMAIN" -m "$EMAIL"

# ── 5. Configure nginx domain ──────────────────

echo "→ Configuring nginx for $DOMAIN..."
sed -i "s/DOMAIN/$DOMAIN/g" nginx.conf

# ── 6. Environment file ────────────────────────

if [ ! -f .env ]; then
    echo "→ Creating .env file..."
    JWT_SECRET=$(openssl rand -hex 32)
    cat > .env <<EOF
JWT_SECRET=$JWT_SECRET
ANTHROPIC_API_KEY=sk-ant-CHANGE-ME
FRED_API_KEY=CHANGE-ME
TOKEN_EXPIRE_MINUTES=480
EOF
    echo "  !! Edit .env with your API keys before starting !!"
fi

# ── 7. Passwords file ──────────────────────────

if [ ! -f /opt/greybark/data/passwords.json ]; then
    echo "→ Creating default passwords file..."
    echo '{}' > /opt/greybark/data/passwords.json
    echo "  !! Add client passwords: python -c \"from deploy.auth import hash_password; print(hash_password('mypass'))\" !!"
fi

# ── 8. Build & start ───────────────────────────

echo "→ Building and starting containers..."
docker compose build
docker compose up -d

# ── 9. Backup cron ──────────────────────────────

echo "→ Setting up daily backup cron..."
CRON_CMD="0 3 * * * docker cp greybark-app:/data/greybark.db /opt/greybark/backups/greybark_\$(date +\%Y\%m\%d).db && find /opt/greybark/backups -name '*.db' -mtime +30 -delete"
(crontab -l 2>/dev/null || true; echo "$CRON_CMD") | sort -u | crontab -

# ── 10. Verify ──────────────────────────────────

echo ""
echo "=== Deploy complete ==="
echo "Portal: https://$DOMAIN"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Add client passwords to /opt/greybark/data/passwords.json"
echo "  3. Copy/seed your greybark.db to /opt/greybark/data/"
echo "  4. Restart: docker compose restart app"
echo ""
docker compose ps
