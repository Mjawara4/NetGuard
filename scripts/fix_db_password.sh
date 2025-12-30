#!/bin/bash
VPS_HOST="74.208.167.166"
NEW_DB_PASSWORD="H2ohS1TimTALOuIOP0rByhPeDaMSqyQIA9ArmaP1iH8="

echo "=========================================="
echo "🛠️  Fixing NetGuard Database Password..."
echo "=========================================="
echo "Connecting to $VPS_HOST..."
echo "⚠️  When prompted, enter the password: DCaoY6yl"
echo ""

ssh root@$VPS_HOST "docker compose -f /opt/netguard/docker-compose.yml exec db psql -U postgres -c \"ALTER USER postgres WITH PASSWORD '$NEW_DB_PASSWORD';\""

echo ""
echo "✅ Database password updated."
echo "👉 You should now be able to log in at https://app.netguard.fun"
