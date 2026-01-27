# NBA Stats Pipeline - Cloud Run Container
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies and Google Cloud SDK
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    gnupg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get install -y google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY trained_models/ ./trained_models/

# Create data and logs directories
RUN mkdir -p data logs

# Entry point scripts
COPY scripts/cloud_run_entrypoint.sh /entrypoint.sh
COPY scripts/cloud_run_scrape.sh /scrape.sh
RUN chmod +x /entrypoint.sh /scrape.sh

# Default environment variables
ENV DB_PATH=/app/data/nba_stats.db
ENV GCS_BUCKET=nba-stats-pipeline-data
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
