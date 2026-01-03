FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock* ./

# Create venv and install dependencies
RUN uv venv && uv sync --no-dev

# Copy the rest of the application
COPY app/ app/

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run the application using the venv
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
