FROM python:3.12.7-slim

# Set work directory
WORKDIR /app

# Copy only the necessary files first (to leverage caching)
COPY ./requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy the rest of the application code
COPY . /app

# Create a non-root user and change ownership
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port 8000
EXPOSE 8000

# Command to run the app
CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
