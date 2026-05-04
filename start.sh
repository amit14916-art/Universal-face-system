#!/bin/bash

# WhatsApp Gateway disabled as requested
# npm start &

# Run migrations
echo "Running Database Migrations..."
python migrate_db.py

# Start the FastAPI Application
echo "Starting Sentinel API..."
uvicorn api:app --host 0.0.0.0 --port 8000 --forwarded-allow-ips='*' --timeout-keep-alive 60
