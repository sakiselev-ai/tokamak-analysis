#!/bin/bash
# Deploy Tokamak Analysis to VPS
# Usage: ./deploy.sh <ip> [domain]

set -e

IP=${1:?"Usage: ./deploy.sh <ip> [domain]"}
DOMAIN=${2:-""}
REMOTE="root@$IP"
DEPLOY_DIR="/opt/tokamak-analysis"

echo "=== Deploying to $IP ==="

# Sync code
echo "1. Uploading project..."
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
    --exclude='.env' --exclude='test.db' --exclude='.claude' --exclude='data/' --exclude='models/' \
    -e "ssh -o StrictHostKeyChecking=no" \
    . "$REMOTE:$DEPLOY_DIR/"

# Setup SSL
echo "2. Setting up SSL..."
ssh -o StrictHostKeyChecking=no "$REMOTE" "cd $DEPLOY_DIR && bash deploy/setup_ssl.sh $DOMAIN"

# Setup .env if not exists
echo "3. Configuring environment..."
ssh -o StrictHostKeyChecking=no "$REMOTE" "
    cd $DEPLOY_DIR
    if [ ! -f .env ]; then
        cp .env.example .env
        # Generate random secrets
        JWT_SECRET=\$(openssl rand -hex 32)
        sed -i \"s|changeme_jwt_secret_key_in_production|\$JWT_SECRET|\" .env
        MINIO_PASS=\$(openssl rand -hex 16)
        sed -i \"s|minioadmin123|\$MINIO_PASS|\" .env
        PG_PASS=\$(openssl rand -hex 16)
        sed -i \"s|changeme_in_production|\$PG_PASS|\" .env
    fi
"

# Build and deploy
echo "4. Building Docker images..."
ssh -o StrictHostKeyChecking=no "$REMOTE" "cd $DEPLOY_DIR && docker compose build --parallel"

echo "5. Starting services..."
if [ -n "$DOMAIN" ]; then
    ssh -o StrictHostKeyChecking=no "$REMOTE" "cd $DEPLOY_DIR && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
else
    ssh -o StrictHostKeyChecking=no "$REMOTE" "cd $DEPLOY_DIR && docker compose up -d"
fi

# Init DB
echo "6. Running database migrations..."
ssh -o StrictHostKeyChecking=no "$REMOTE" "cd $DEPLOY_DIR && docker compose exec backend python3 -c '
import asyncio
from app.database import engine, Base
from app.models import *
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(\"Tables created\")
asyncio.run(init())
'"

echo ""
echo "=== Deployment complete ==="
echo "Frontend: http://$IP/"
echo "API Docs: http://$IP/docs"
echo "Grafana:  http://$IP:3001/"
if [ -n "$DOMAIN" ]; then
    echo "HTTPS:    https://$DOMAIN/"
fi
