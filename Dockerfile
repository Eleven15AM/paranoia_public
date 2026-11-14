FROM python:3.12-slim

# Non-root user; the app never needs root at runtime.
RUN useradd --create-home --uid 1000 paranoia
WORKDIR /app

# Install deps first so code edits don't invalidate the pip layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app. .dockerignore excludes caches and .env.
COPY --chown=paranoia:paranoia . .

USER paranoia
EXPOSE 8080

# Healthcheck hits the unauthenticated /api/health endpoint. If the
# scheduler has stopped and the cache is empty this still returns 200
# with an empty object, which is fine — we only want to know Flask is up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/api/health', timeout=4).status==200 else 1)"

CMD ["python", "app.py"]