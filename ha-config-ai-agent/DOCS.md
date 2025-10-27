# AI Configuration Agent - Documentation

Complete guide for installing, configuring, and using the AI Configuration Agent add-on for Home Assistant.

## Table of Contents

- [Installation](#installation)
  - [Manual Installation](#manual-installation)
  - [Local Development](#local-development)
- [Configuration](#configuration)
  - [Configuration Options](#configuration-options)
  - [AI Provider Setup](#ai-provider-setup)
- [Usage Guide](#usage-guide)
  - [Getting Started](#getting-started)
  - [Chat Interface](#chat-interface)
  - [Approval Workflow](#approval-workflow)
- [Features](#features)
  - [Configuration Management](#configuration-management)
  - [Device & Entity Management](#device--entity-management)
  - [Virtual Files](#virtual-files)
- [Advanced Topics](#advanced-topics)
  - [Backup Management](#backup-management)
  - [Troubleshooting](#troubleshooting)
  - [Security](#security)
- [Development](#development)
  - [Local Development Setup](#local-development-setup)
  - [Architecture](#architecture)
  - [Contributing](#contributing)

---

## Installation

### Manual Installation

The AI Configuration Agent can be installed as a local Home Assistant add-on.

#### Prerequisites
- Home Assistant OS or Supervised installation
- Access to the Home Assistant file system
- An OpenAI API key (or compatible provider)

#### Local Installation Steps

1. **Access your Home Assistant configuration directory**
   - Via SSH, Samba share, or Terminal add-on

2. **Create the addons directory** (if it doesn't exist)
   ```bash
   mkdir -p /config/addons
   cd /config/addons
   ```

3. **Clone the repository**
   ```bash
   git clone https://github.com/yinzara/ha-config-ai-agent.git
   ```

4. **Add the local repository in Home Assistant**
   - Navigate to **Settings** → **Add-ons** → **Add-on Store**
   - Click the menu icon (⋮) in the top right
   - Select **Repositories**
   - Add `/addons` as a repository
   - Click **Add** then **Close**

5. **Install the add-on**
   - Refresh the Add-on Store page
   - Find "AI Configuration Agent" in the local add-ons section
   - Click on it and press **Install**
   - Wait for the installation to complete

6. **Configure the add-on**
   - See [Configuration](#configuration) section below

7. **Start the add-on**
   - Click **Start** on the add-on page
   - Optionally enable **Start on boot** and **Watchdog**

8. **Access the interface**
   - Click **Open Web UI** or
   - Find "Config Agent" in your Home Assistant sidebar

### Local Development

For development and testing outside of Home Assistant:

```bash
# Clone the repository
git clone https://github.com/yinzara/ha-config-ai-agent.git
cd ha-config-ai-agent/ha-config-ai-agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create test configuration directory
mkdir -p test_config
echo "# Test config" > test_config/configuration.yaml

# Set environment variables
export HA_CONFIG_DIR="./test_config"
export BACKUP_DIR="./backups"
export OPENAI_API_KEY="sk-your-key-here"
export OPENAI_MODEL="gpt-5-mini"
export LOG_LEVEL="debug"

# Run development server
uvicorn src.main:app --reload --port 8099
```

Visit http://localhost:8099 to access the interface.

---

## Configuration

### Configuration Options

Configure the add-on through the Home Assistant UI: **Settings** → **Add-ons** → **AI Configuration Agent** → **Configuration**

#### Basic Configuration

```yaml
openai_api_key: "sk-your-openai-api-key"
```

#### Full Configuration

```yaml
openai_api_url: "https://api.openai.com/v1"
openai_api_key: "sk-your-api-key"
openai_model: "gpt-4o"
log_level: "info"
system_prompt_file: ""
```

#### Configuration Parameters

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `openai_api_url` | URL | `https://api.openai.com/v1` | API endpoint URL |
| `openai_api_key` | Password | *Required* | API authentication key |
| `openai_model` | String | `gpt-4o` | Model identifier to use |
| `log_level` | List | `info` | Logging level: `debug`, `info`, `warning`, `error` |
| `system_prompt_file` | String | `""` (empty) | Optional: Path to custom system prompt file (relative to `/config`) |

### AI Provider Setup

The add-on supports any OpenAI-compatible API endpoint.

#### OpenAI (Default)

**Best for:** Production use, highest quality responses

1. Sign up at https://platform.openai.com/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://api.openai.com/v1"
   openai_api_key: "sk-proj-your-key-here"
   openai_model: "gpt-5-mini"
   ```

**Recommended models:**
- `gpt-5-mini` - Default, Best balance of speed and quality
- `gpt-5` - High quality, slower
- `gpt-5-nano` - Faster, lower cost (not recommended)

#### OpenRouter

**Best for:** Access to multiple models, competitive pricing

1. Sign up at https://openrouter.ai/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://openrouter.ai/api/v1"
   openai_api_key: "sk-or-v1-your-key"
   openai_model: "anthropic/claude-3.5-sonnet"
   ```

#### Anthropic

Access to the Claude family of models

1. Sign up at https://console.anthropic.com/
2. Create an API key
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://api.anthropic.com/v1/"
   openai_api_key: "sk-or-v1-your-key"
   openai_model: "claude-sonnet-4-5"
   ```

**Recommended models:**
- `anthropic/claude-4.5-sonnet` - Excellent reasoning
- `openai/gpt-5` - OpenAI via OpenRouter
- `google/gemini-pro-2.5` - Long context support

#### Local Ollama

**Best for:** Privacy, offline use, no API costs

1. Install Ollama: https://ollama.ai/
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. Ensure Ollama is accessible from Home Assistant
4. Configure the add-on:
   ```yaml
   openai_api_url: "http://host.docker.internal:11434/v1"
   openai_api_key: "ollama"
   openai_model: "llama3.2"
   ```

**Recommended models:**
- `llama3.2` - Good general performance
- `mistral` - Fast and capable
- `codellama` - Optimized for code

**Note:** Performance depends on your hardware. GPU recommended.

### Custom System Prompt

You can customize the AI agent's behavior by providing a custom system prompt file. This allows you to modify the agent's personality, instructions, and capabilities without modifying the add-on code.

#### Creating a Custom System Prompt

1. **Create a prompt file** in your Home Assistant `/config` directory:
   ```bash
   # Example: Create a file at /config/ai_agent_prompt.txt
   nano /config/ai_agent_prompt.txt
   ```

2. **Write your custom instructions**. Start with the default prompt and modify as needed:

<details>
<summary><b>Default System Prompt (Click to expand)</b></summary>

```text
You are a Home Assistant Configuration Assistant.

Your role is to help users manage their Home Assistant configuration files safely and effectively.

Key Responsibilities:
1. **Understanding Requests**: Interpret user requests about Home Assistant configuration
2. **Reading Configuration**: Use tools to examine current configuration files
3. **Proposing Changes**: Suggest configuration changes with clear explanations using the propose_config_changes tool without requesting confirmation
4. **Safety First**: Always explain the impact of changes before proposing them
5. **Best Practices**: Guide users toward Home Assistant best practices

Available Tools:
- search_config_files: Search for terms in configuration (use first)
- propose_config_changes: Propose changes for user approval

Important Guidelines:
- NEVER suggest changes directly - always use propose_config_change
- Always read the current configuration before proposing changes
- Explain WHY you're proposing changes, not just WHAT
- Preserve all existing code, comments and structure when possible
- Only change what's needed to complete the request of the user
- Validate that changes align with Home Assistant documentation
- Warn users about potential breaking changes
- Suggest testing in a development environment for major changes
- Remember when searching for files that terms are case-insensitive so don't search for multiple case variations of a word

Response Style:
- Be concise but thorough
- Use technical terms appropriately
- Provide examples when helpful
- Format code blocks with YAML syntax
- Ask clarifying questions if request is ambiguous

Remember: You're helping manage a production Home Assistant system. Safety and clarity are paramount.
```

</details>

3. **Configure the add-on** to use your custom prompt:
   ```yaml
   system_prompt_file: "ai_agent_prompt.txt"
   ```

4. **Restart the add-on** to load the new prompt

#### File Path Requirements

- Path must be **relative** to `/config`
- Security: Path traversal is blocked (cannot access files outside `/config`)
- Examples:
  - `ai_agent_prompt.txt` → `/config/ai_agent_prompt.txt`
  - `prompts/custom.txt` → `/config/prompts/custom.txt`
  - `ai/system_prompt.md` → `/config/ai/system_prompt.md`

#### Fallback Behavior

- If `system_prompt_file` is empty or not set, the built-in default prompt is used
- If the specified file is not found, a warning is logged and the default prompt is used
- If there's an error reading the file, the default prompt is used

#### Tips for Custom Prompts

**Structure your prompt with:**
- Clear role definition
- Key responsibilities
- Available tools (search_config_files, propose_config_changes)
- Important guidelines and constraints
- Response style preferences

**Example use cases:**
- Focus on specific integrations (e.g., "You specialize in Zigbee and Z-Wave configurations")
- Emphasize automation best practices
- Add domain-specific knowledge (e.g., "You understand solar energy systems")
- Customize personality and tone
- Add custom validation rules

**Note:** The system prompt significantly affects the agent's behavior. Test changes carefully.

#### Azure OpenAI

**Best for:** Enterprise deployments, compliance requirements

1. Set up Azure OpenAI resource
2. Deploy a model
3. Configure the add-on:
   ```yaml
   openai_api_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2024-02-15-preview"
   openai_api_key: "your-azure-api-key"
   openai_model: "gpt-5-mini"
   ```

---

## Usage Guide

### Getting Started

After installation and configuration:

1. **Access the interface**
   - Open Home Assistant
   - Click "Config Agent" in the sidebar
   - Or go to the add-on page and click "Open Web UI"

2. **Verify the connection**
   - The interface should show: "✅ AI Configuration Agent ready"
   - If not, check your API key and logs

3. **Start chatting**
   - Type your request in the text box
   - Press Enter or click Send
   - Wait for the AI to respond

### Chat Interface

The chat interface supports natural language requests about your Home Assistant configuration.

#### Query Examples

Ask questions to understand your configuration:

```
"Show me all my automations"
"What entities are in the living room?"
"List all my MQTT sensors"
"Which automations trigger at sunset?"
```

#### Modification Examples

Request changes to your configuration:

```
"Enable debug logging for homeassistant.core"
"Add a new automation to turn off all lights at 11pm"
"Change the friendly name of sensor.temperature to 'Living Room Temp'"
"Create a script that announces 'Welcome home' when I arrive"
```

#### Device Management Examples

Manage devices and entities:

```
"Rename the device 'Button 1' to 'Office Button'"
"Move all bedroom devices to the bedroom area"
"Disable the entity sensor.old_sensor"
"Show me all Zigbee devices"
```

### Approval Workflow

When the AI proposes changes:

1. **Review the proposal**
   - An approval card appears in the chat
   - Shows changeset ID and number of files

2. **View changes**
   - Click **👁️ View Changes**
   - A modal displays the diff for each file
   - Lines with `+` are additions
   - Lines with `-` are removals

3. **Make a decision**
   - **✓ Approve & Apply** - Apply changes immediately
   - **✗ Reject** - Discard the changes
   - **Cancel** - Close modal, decide later

4. **Changes are applied**
   - Backup created automatically
   - Files written with atomic operations
   - Home Assistant validates the configuration
   - If validation passes, configuration reloads
   - If validation fails, automatic rollback

5. **Confirmation**
   - Success message shows applied files
   - Any errors are displayed clearly

---

## Features

### Configuration Management

The add-on can read and modify all Home Assistant configuration files:

- `configuration.yaml` - Main configuration
- `automations.yaml` - Automation rules
- `scripts.yaml` - Scripts
- `scenes.yaml` - Scene definitions
- `customize.yaml` - Entity customizations
- Any YAML file in `/config`

**Capabilities:**
- Comment-preserving edits (preserves your notes)
- Multi-file changes in single operation
- Automatic backup before changes
- Configuration validation before applying
- Automatic rollback on failure

### Device & Entity Management

Manage devices and entities through the registry:

**Devices:**
- Rename devices
- Assign to areas
- Add labels
- Enable/disable devices

**Entities:**
- Rename entities (friendly name or entity_id)
- Change icons
- Assign to areas
- Add labels

**Areas:**
- Create new areas
- Rename areas
- Add icons and pictures
- Set aliases

### Virtual Files

The AI can work with "virtual files" that represent registry data:

#### `lovelace.yaml`
- Represents your Lovelace dashboard configuration
- Read via WebSocket API
- Write updates back via API
- **Note:** Only works if Lovelace is in storage mode (not YAML mode)

#### `devices/{device_id}.json`
- Individual device from device registry
- Contains: name, manufacturer, model, area, etc.
- Modifications update the registry via WebSocket

#### `entities/{entity_id}.json`
- Individual entity from entity registry
- Contains: name, icon, area, platform, etc.
- Modifications update the registry via WebSocket

#### `areas/{area_id}.json`
- Individual area from area registry
- Contains: name, icon, picture, aliases
- Can create new areas or update existing ones

**Example:**
```
You: "Rename device abc123 to 'Kitchen Light Switch'"
AI: [Proposes changes to devices/abc123.json]
You: [Approves]
AI: ✅ Updated device via WebSocket registry
```

---

## Advanced Topics

### Backup Management

The add-on automatically creates backups before every change.

#### Backup Naming

Backups are named with timestamps:
```
configuration_20250126_143022.yaml.backup
automations_20250126_143145.yaml.backup
```

#### Backup Location

Backups are stored in the `/backup` directory within the add-on.

#### Backup Rotation

- Default: Keep 10 most recent backups per file
- Configurable: `max_backups` option (5-50)
- Older backups automatically deleted

#### Manual Restore

To restore a backup:

1. **Via API:**
   ```bash
   curl -X POST http://localhost:8099/api/config/restore \
     -H "Content-Type: application/json" \
     -d '{"backup_name": "configuration_20250126_143022.yaml.backup", "validate": true}'
   ```

2. **Manually:**
   - Copy backup file from `/backup`
   - Remove `.backup` extension
   - Replace original file in `/config`
   - Restart Home Assistant or reload config

#### List Backups

Via API:
```bash
curl http://localhost:8099/api/config/backups?file_path=configuration.yaml
```

### Troubleshooting

#### "Agent system not initialized"

**Cause:** OpenAI API key not configured or invalid

**Solution:**
1. Check add-on configuration
2. Verify API key is correct
3. Check logs for connection errors
4. Restart add-on after configuration change

#### "Validation failed"

**Cause:** Proposed changes result in invalid Home Assistant configuration

**Solution:**
1. Review the error message in logs
2. Changes are automatically rolled back
3. Ask the AI to try a different approach
4. Manually review the proposed changes for issues

#### "SUPERVISOR_TOKEN not available"

**Cause:** Add-on doesn't have proper API access

**Solution:**
1. Verify `hassio_api: true` in `config.yaml`
2. Check `hassio_role: manager` is set
3. Restart the add-on
4. Check Home Assistant supervisor logs

#### "WebSocket connection failed"

**Cause:** Cannot connect to Home Assistant WebSocket API

**Solution:**
1. Verify Home Assistant is running
2. Check network connectivity
3. Review WebSocket URL: `ws://supervisor/core/websocket`
4. Check supervisor token is available
5. Try restarting both add-on and Home Assistant

#### Changes not applied

**Cause:** Various reasons

**Solution:**
1. Check logs for specific error
2. Verify file permissions
3. Check disk space
4. Ensure configuration directory is writable
5. Review backup directory has space

#### AI responses are slow

**Cause:** Model or network latency

**Solution:**
1. Try a faster model (e.g., `gpt-4o` instead of `gpt-4`)
2. Use local Ollama for faster responses
3. Check API provider status
4. Check network connectivity

### Security

#### Authentication

- **Ingress:** All requests authenticated by Home Assistant
- **No direct access:** Add-on not exposed to network
- **Token-based:** WebSocket API uses supervisor token

#### Container Isolation

- **AppArmor:** Security profile limits system access
- **Volume mapping:** Only `/config`, `/backup`, and add-on config accessible
- **Network:** No privileged network access

#### Input Validation

- **Path traversal protection:** File paths validated
- **YAML validation:** Syntax checked before applying
- **HA validation:** Home Assistant validates before reload

#### Backup Safety

- **Automatic backups:** Created before every change
- **Atomic writes:** Changes written to temp file first
- **Rollback:** Automatic restore on validation failure
- **Rotation:** Old backups pruned automatically

#### Sensitive Data

- **API keys:** Stored as password fields in HA
- **Logs:** Sensitive data not logged
- **Conversation history:** Stored in browser only (not server)

#### Best Practices

1. **External backups:** Maintain separate backups of your configuration
2. **Review changes:** Always review diffs before approving
3. **Test first:** Test major changes in development environment
4. **Monitor logs:** Check logs after applying changes
5. **Keep updated:** Update add-on regularly for security patches

---

## Development

### Local Development Setup

#### Prerequisites

- Python 3.11 or higher
- Git
- Virtual environment tool (venv)

#### Setup Steps

```bash
# Clone repository
git clone https://github.com/yinzara/ha-config-ai-agent.git
cd ha-config-ai-agent

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create test directories
mkdir -p test_config backups addon_config

# Create test configuration
cat > test_config/configuration.yaml << EOF
homeassistant:
  name: Test Home
  unit_system: metric
  time_zone: America/New_York

logger:
  default: info
EOF

# Set environment variables
export HA_CONFIG_DIR="./test_config"
export BACKUP_DIR="./backups"
export OPENAI_API_KEY="sk-your-key-here"
export OPENAI_MODEL="gpt-4o"
export LOG_LEVEL="debug"
export SYSTEM_PROMPT_FILE=""  # Optional: path to custom prompt file

# Run development server
uvicorn src.main:app --reload --port 8099
```

#### Development Workflow

1. **Make changes** to source files
2. **Server auto-reloads** with `--reload` flag
3. **Test in browser** at http://localhost:8099
4. **Check logs** in terminal
5. **Review changes** in `test_config/` directory

#### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests (when implemented)
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Architecture

#### Components

1. **FastAPI Application** (`src/main.py`)
   - Web framework and API endpoints
   - Lifespan management
   - Request/response handling

2. **Agent System** (`src/agents/`)
   - AI orchestration using OpenAI SDK
   - Function calling for tool execution
   - Conversation management

3. **Configuration Manager** (`src/config/`)
   - YAML file operations
   - Backup management
   - Validation and rollback

4. **WebSocket Client** (`src/ha/`)
   - Home Assistant WebSocket API
   - Device/entity/area registry access
   - Configuration reload

5. **Frontend** (`static/`, `templates/`)
   - Chat interface
   - Diff viewer
   - Approval workflow UI

#### Data Flow

```
User Input → Frontend → /api/chat → Agent System → Tools
                                        ↓
                                  Configuration Manager
                                        ↓
                                 HA Validation API
                                        ↓
                                  WebSocket Reload
                                        ↓
                                  Response → Frontend
```

#### Tech Stack

- **Backend:** Python 3.11, FastAPI, Uvicorn
- **AI:** OpenAI Agents SDK
- **YAML:** ruamel.yaml (comment-preserving)
- **WebSocket:** aiohttp, websockets
- **Frontend:** Vanilla JavaScript, Marked.js, Diff.js
- **Container:** Docker, Alpine Linux

### Contributing

Contributions are welcome! Please follow these guidelines:

#### Getting Started

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

#### Code Style

- **Python:** PEP 8 style guide
- **Type hints:** Use for all function signatures
- **Docstrings:** Google style docstrings
- **Async:** Use async/await for I/O operations

#### Commit Messages

Follow conventional commits:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

#### Pull Request Process

1. Update documentation for changes
2. Add tests for new features
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review from maintainers

---

## Support & Resources

- **GitHub Issues:** https://github.com/yinzara/ha-config-ai-agent/issues
- **Home Assistant Community:** https://community.home-assistant.io/
- **Documentation:** You're reading it!
- **Technical Details:** See [CLAUDE.md](../CLAUDE.md)

---

**Last Updated:** January 26, 2025
**Version:** 0.6.0
