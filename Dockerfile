# Base image
FROM python:3.9-slim

# Set working directory
WORKDIR /usr/src/app

# Copy files
COPY . .

# Install dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libx11-6 libxext6 libxrender1 libxtst6 libxi6 && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Default command
CMD ["python", "your_script.py"]
