# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Final Image
FROM python:3.11-bullseye
WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install system dependencies for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure static directories exist
RUN mkdir -p static/faces frontend/dist/assets

EXPOSE 8000

# Run migrations and start API
CMD ["sh", "-c", "python migrate_db.py && uvicorn api:app --host 0.0.0.0 --port 8000 --forwarded-allow-ips='*' --timeout-keep-alive 60"]
