# Use Debian 12 with Python 3.10 as the base image
FROM python:3.10-slim-bookworm AS base

# Copy requirements.txt to the root directory
COPY requirements.txt .

# Build cache and install strict versions from requirements.txt using pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/pkg -r requirements.txt

# Second-stage production build
FROM base AS production

# Set the working directory
WORKDIR /app/api

# Define environment variables
ENV FLASK_APP=app/http/app.py
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV NLTK_DATA=/app/api/internal/core/unstructured/nltk_data

# Set container timezone to US Eastern Time (New York)
ENV TZ America/New_York

# Copy third-party dependencies and source code
COPY --from=base /pkg /usr/local
COPY . /app/api

# Copy the entrypoint script and set execute permissions
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port 5001
EXPOSE 5001

# Run the entrypoint script to start the application
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
