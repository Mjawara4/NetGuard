#!/bin/bash
# Source the env file to get the key
if [ -f .env.production ]; then
    export $(grep -v '^#' .env.production | xargs)
elif [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "Error: GEMINI_API_KEY not found."
    exit 1
fi

echo "Checking available models for API Key..."
curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=$GEMINI_API_KEY" | grep "\"name\": \"models/gemini"
