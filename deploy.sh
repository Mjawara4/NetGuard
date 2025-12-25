#!/bin/bash

# Deployment Script for NetGuard

echo "🚀 Starting Deployment..."

# 1. Pull latest changes
echo "📥 Pulling latest code..."
git pull origin main

# 2. Setup Environment
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    if [ -f .env.production ]; then
        echo "✅ Found .env.production, copying to .env..."
        cp .env.production .env
        echo "Please edit .env with your actual secrets if you haven't already."
        # Optional: Pausing to let user edit
        # read -p "Press [Enter] to continue after editing .env..."
    else
        echo "❌ No .env or .env.production found. Aborting."
        exit 1
    fi
fi

# 3. Build and Start Containers
echo "🏗️  Building and Starting Containers..."
docker compose down
docker compose up -d --build

# 4. Prune unused images
echo "🧹 Cleaning up..."
docker image prune -f

echo "✅ Deployment Complete! NetGuard is running."
echo "   Frontend: http://localhost (or your domain)"
echo "   Backend:  http://localhost:8000 (or your domain)"
