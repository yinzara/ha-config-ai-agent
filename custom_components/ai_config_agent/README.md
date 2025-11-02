# AI Configuration Agent - HACS Custom Component

This is the HACS-installable custom component version of the AI Configuration Agent for Home Assistant.

## Installation via HACS

1. **Add Custom Repository:**
   - Open HACS in Home Assistant
   - Go to "Integrations"
   - Click the three dots menu (⋮) in the top right
   - Select "Custom repositories"
   - Add repository URL: `https://github.com/yinzara/ha-config-ai-agent`
   - Category: `Integration`
   - Click "Add"

2. **Install the Integration:**
   - Search for "AI Configuration Agent" in HACS
   - Click "Download"
   - Restart Home Assistant

3. **Configure the Integration:**
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "AI Configuration Agent"
   - Enter your configuration:
     - **API Key:** Your OpenAI-compatible API key
     - **API URL:** API endpoint (default: `https://api.openai.com/v1`)
     - **Model:** Model name (e.g., `gpt-4o`, `gemini-2.5-flash`)
     - **Log Level:** Logging verbosity (info, debug, warning, error)
     - **Temperature:** (Optional) Model temperature for creativity
     - **System Prompt File:** (Optional) Custom system prompt file path
     - **Enable Cache Control:** Enable prompt caching
     - **Usage Tracking:** Token usage tracking method

## Usage

Once configured, the AI Configuration Agent provides two services:

### Service: `ai_config_agent.chat`

Send a message to the AI agent and receive a response.

**Example:**
```yaml
service: ai_config_agent.chat
data:
  message: "Enable debug logging for homeassistant.core"
```

**Response:**
```json
{
  "success": true,
  "response": "I'll help you enable debug logging...",
  "messages": [...]
}
```

### Service: `ai_config_agent.approve`

Approve or reject proposed configuration changes.

**Example:**
```yaml
service: ai_config_agent.approve
data:
  change_id: "abc123def456"
  approved: true
  validate: true
```

## Features

- **Natural Language Configuration:** Ask questions and request changes in plain English
- **Safe Change Application:** All changes require explicit approval with visual diffs
- **Automatic Backups:** Creates backups before each change
- **Home Assistant Validation:** Validates configuration before applying
- **Automatic Rollback:** Restores from backup if validation fails
- **Virtual File Support:** Manage Lovelace, devices, entities, and areas
- **Provider Flexibility:** Works with OpenAI, Anthropic, OpenRouter, Ollama, Azure

## Differences from Add-on Version

The custom component version runs the FastAPI server directly within Home Assistant, while the add-on version runs in a separate Docker container. Both provide the same functionality, but the custom component:

- Runs on any Home Assistant installation (not just Supervisor-based)
- Doesn't require add-on support
- Integrates directly with Home Assistant's configuration flow
- Exposes services that can be called from automations

## Support

- **GitHub Issues:** https://github.com/yinzara/ha-config-ai-agent/issues
- **Documentation:** See main repository README

## License

MIT License - See LICENSE file for details
