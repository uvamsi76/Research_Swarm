# Tool Service Dockerfile
FROM python:3.11-slim

WORKDIR /workspace/tool_service

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files into the container working directory
COPY . .

# Expose port
EXPOSE 3000

# Run the application
CMD ["python", "entrypoint.py"]
