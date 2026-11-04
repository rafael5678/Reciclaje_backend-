# Python 3.12 slim image for the FastAPI service.
FROM python:3.12-slim-bookworm

WORKDIR /app

# libgomp is required by ONNX Runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application package and local vision models.
COPY app.py .
COPY app ./app
COPY models ./models

# Runtime folder for optional photo dumps.
RUN mkdir -p /app/data/uploads

EXPOSE 8000

CMD ["python", "app.py"]
