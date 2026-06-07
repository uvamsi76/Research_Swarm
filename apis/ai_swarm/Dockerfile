# AI Swarm Service Dockerfile
FROM python:3.11-slim

WORKDIR /workspace/ai_swarm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files into the container working directory
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "entrypoint.py"]
