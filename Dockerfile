FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git && \
    rm -rf /var/lib/apt/lists/*

# Copy all project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    openenv-core \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    openai \
    huggingface_hub

# Set Python path so imports work
ENV PYTHONPATH="/app:$PYTHONPATH"

# Health check — HF Spaces uses port 7860
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Expose port 7860 (required by Hugging Face Spaces)
EXPOSE 7860

# Start the server on port 7860
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]