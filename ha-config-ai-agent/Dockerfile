ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.21
FROM $BUILD_FROM

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src ./src/
COPY static ./static/
COPY templates ./templates/

# Copy run script
COPY run.sh ./
RUN chmod a+x ./run.sh

# Labels for Home Assistant
LABEL \
    io.hass.version="0.3.0" \
    io.hass.type="addon" \
    io.hass.arch="armhf|armv7|aarch64|i386|amd64"

# Run the add-on
CMD [ "./run.sh" ]
