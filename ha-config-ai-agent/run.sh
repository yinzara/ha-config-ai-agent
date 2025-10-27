#!/usr/bin/with-contenv bashio

# Disable Python output buffering for real-time streaming
export PYTHONUNBUFFERED=1

# Get configuration from add-on options
export OPENAI_API_URL=$(bashio::config 'openai_api_url' ${OPENAI_API_URL:-})
export OPENAI_API_KEY=$(bashio::config 'openai_api_key' ${OPENAI_API_KEY:-})
export OPENAI_MODEL=$(bashio::config 'openai_model' ${OPENAI_MODEL:-})
export LOG_LEVEL=$(bashio::config 'log_level' ${LOG_LEVEL:-debug})
export SYSTEM_PROMPT_FILE=$(bashio::config 'system_prompt_file' ${SYSTEM_PROMPT_FILE:-})

# Home Assistant configuration
export HA_CONFIG_DIR="/homeassistant"
export ADDON_CONFIG_DIR="/config"
export BACKUP_DIR="/backup/config-agent"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Log startup
bashio::log.info "Starting AI Configuration Agent..."
bashio::log.info "OpenAI API: ${OPENAI_API_URL}"
bashio::log.info "Model: ${OPENAI_MODEL}"
bashio::log.info "HA Config: ${HA_CONFIG_DIR}"

# Start application
exec uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8099 \
    --log-level "${LOG_LEVEL}" \
    --no-access-log \
    --timeout-keep-alive 300
