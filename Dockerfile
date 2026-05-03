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

# Install system dependencies + Node.js
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package.json for WA Gateway and install
COPY package*.json ./
RUN npm install

# Copy all project files
COPY . .

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure static directories and auth directory exist
RUN mkdir -p static/faces auth_info_baileys
RUN chmod +x start.sh

EXPOSE 8000

# Start services
CMD ["./start.sh"]
