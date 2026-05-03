#!/bin/bash

# Start the WhatsApp Gateway in the background
echo "Starting WhatsApp Gateway..."
npm start &

# Run migrations
echo "Running Database Migrations..."
python migrate_db.py

# Start the FastAPI Application
echo "Starting Sentinel API..."
uvicorn api:app --host 0.0.0.0 --port 8000 --forwarded-allow-ips='*' --timeout-keep-alive 60
