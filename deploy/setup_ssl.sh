#!/bin/bash
# Setup TLS/HTTPS for Tokamak Analysis
# Usage: ./setup_ssl.sh [domain]
# Without domain: creates self-signed cert for IP access
# With domain: uses Let's Encrypt certbot

set -e

DOMAIN=${1:-""}
DEPLOY_DIR="/opt/tokamak-analysis"

if [ -z "$DOMAIN" ]; then
    echo "=== Creating self-signed certificate for IP-only access ==="
    mkdir -p $DEPLOY_DIR/ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout $DEPLOY_DIR/ssl/privkey.pem \
        -out $DEPLOY_DIR/ssl/fullchain.pem \
        -subj "/C=RU/ST=Moscow/L=Moscow/O=MEPhI/CN=tokamak-analysis"
    echo "Self-signed certificate created"
else
    echo "=== Installing Let's Encrypt certificate for $DOMAIN ==="
    apt-get update && apt-get install -y certbot
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email admin@mephi.ru

    # Symlink certs
    mkdir -p $DEPLOY_DIR/ssl
    ln -sf /etc/letsencrypt/live/$DOMAIN/fullchain.pem $DEPLOY_DIR/ssl/fullchain.pem
    ln -sf /etc/letsencrypt/live/$DOMAIN/privkey.pem $DEPLOY_DIR/ssl/privkey.pem

    # Auto-renewal cron
    echo "0 0 1 * * certbot renew --quiet && docker compose -f $DEPLOY_DIR/docker-compose.yml restart nginx" | crontab -
    echo "Let's Encrypt certificate installed with auto-renewal"
fi
