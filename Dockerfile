# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
RUN apt-get update && apt-get install -y build-essential
WORKDIR /app/frontend
# Only copy package.json to ignore any Windows-specific lock files
COPY frontend/package.json ./
ENV NODE_OPTIONS="--max-old-space-size=450"
RUN rm -f package-lock.json && npm install
COPY frontend/ ./
RUN npm run build -- --logLevel info

# Stage 2: Build the Django backend
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies for psycopg2 and other tools
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the backend
COPY backend/ ./backend/

# Copy the built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=core.settings

# Final setup: Run migrations and collectstatic during build (optional, but safer to do here)
# Note: For Render, you might want to run migrations in the start command instead.
WORKDIR /app/backend

# Expose port and start
EXPOSE 10000
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --no-input && python add_admin.py && gunicorn core.wsgi:application --bind 0.0.0.0:10000"]
