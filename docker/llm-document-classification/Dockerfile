# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Set non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    curl git ffmpeg libsm6 libxext6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements first (extracted from pyproject.toml)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Entry point to run the agent script
ENTRYPOINT ["python", "llm-document-classification.py"]

# Default command arguments (can be overridden at runtime)
CMD ["--project-hash=default_hash"] 