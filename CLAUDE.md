# CLAUDE.md - AI Configuration Agent for Home Assistant

## Project Overview

**AI Configuration Agent** is a Home Assistant add-on that provides an AI-powered assistant for managing Home Assistant configuration files through natural language. It uses OpenAI-compatible models to understand user requests, read configurations, propose changes, and apply them after user approval.

**Current Version:** 0.1.2

## Repository Information
- **GitHub:** https://github.com/yinzara/ha-config-ai-agent
- **License:** MIT
- **Primary Language:** Python 3.11+
- **Framework:** FastAPI with Uvicorn

---

## Architecture Summary

### Technology Stack
- **Backend:** FastAPI 0.109.0 (async web framework)
- **AI:** OpenAI Agents SDK (supports GPT-4, GPT-4o, OpenRouter, Ollama, Azure)
- **YAML:** ruamel.yaml 0.18.5 (comment-preserving parser)
- **WebSocket:** aiohttp 3.9.3 + websockets
- **Frontend:** Vanilla JavaScript with Marked.js, Diff.js
- **Deployment:** Docker container as Home Assistant add-on

### System Components

#### 1. Main Application (`src/main.py`)
- FastAPI application with Ingress support
- Health check endpoint: `/health`
- Configuration info: `/api/config`
- Chat endpoint: `/api/chat` (POST)
- Approval endpoint: `/api/approve` (POST)
- UI serving: `/` (index.html)

#### 2. Agent System (`src/agents/`)
- **agent_system.py:** Multi-agent orchestration using OpenAI function calling
- **tools.py:** AI tool functions for configuration operations
- **Configuration Agent:** Main agent that handles requests, reads configs, proposes changes
- **Tool Functions:**
  - `search_config_files`: Search and read all YAML files + virtual files (Lovelace, devices, entities, areas)
  - `propose_config_changes`: Batch file changes for approval workflow

#### 3. Configuration Manager (`src/config/manager.py`)
- Comment-preserving YAML operations (ruamel.yaml)
- Atomic file writes (write to temp, then move)
- Automatic backups with rotation (max 10 by default)
- Home Assistant validation via Supervisor API
- Automatic rollback on validation failure
- Path traversal protection
- Handles both real files and virtual files (devices, entities, areas, Lovelace)

#### 4. Home Assistant Integration (`src/ha_websocket.py`)
- WebSocket API client for HA Core
- Lovelace configuration retrieval and saving
- Device/Entity/Area registry access and updates
- Service call support
- Config reload triggers

#### 5. Workflow System (`src/workflow/`)
- Currently minimal (placeholder for Phase 4 enhancements)
- Approval workflow managed in AgentSystem
- Changeset storage with 1-hour expiration
- Diff generation in frontend

#### 6. User Interface (`templates/index.html`, `static/`)
- Dark-themed chat interface
- Real-time conversation with AI agent
- Approval cards with "View Changes" button
- Modal diff viewer with unified diff format
- Markdown rendering for assistant messages
- Loading indicators and system messages

---

## Key Features

### 1. Natural Language Configuration Management
- Ask questions about your configuration
- Request changes in plain English
- AI reads current config before proposing changes
- Explains the reasoning behind proposed changes

### 2. Safe Change Application
- All changes require explicit approval
- Visual diff before applying
- Automatic backups before each change
- Home Assistant validation before applying
- Automatic rollback if validation fails
- Supports batch changes to multiple files

### 3. Virtual File Support
- **Lovelace:** Read/write Lovelace dashboards via WebSocket API
- **Devices:** View/rename devices from device registry
- **Entities:** View/rename entities from entity registry
- **Areas:** View/create/update areas from area registry
- Virtual files appear as: `lovelace.yaml`, `devices/{id}.json`, `entities/{id}.json`, `areas/{id}.json`

### 4. Provider Flexibility
Configure any OpenAI-compatible API:
- **OpenAI:** GPT-5, GPT-5-mini, GPT-5-nano
- **Anthropic** Claude models
- **OpenRouter:** 100+ models
- **Local Ollama:** Privacy-first option
- **Azure OpenAI:** Enterprise deployments

### 5. Security Features
- Ingress authentication (Home Assistant login required)
- AppArmor container isolation
- Path traversal prevention
- Atomic file operations
- Validation before applying changes
- Automatic backups with rotation
- Manager-level Supervisor API access (required for validation)

---

## File Structure

```
ha-config-ai-agent/
├── config.yaml              # Add-on manifest (Ingress, options, permissions)
├── Dockerfile               # Container definition (Python 3.11-slim)
├── requirements.txt         # Python dependencies
├── run.sh                   # Startup script (reads options, sets env vars)
├── apparmor.txt            # Security profile
├── build.yaml              # Build configuration
│
├── src/
│   ├── main.py             # FastAPI application (315 lines)
│   ├── agents/
│   │   ├── agent_system.py # AI agent orchestration (454 lines)
│   │   └── tools.py        # Agent tool functions (989 lines)
│   ├── config/
│   │   └── manager.py      # Configuration management (556 lines)
│   └── ha/ 
|       └── ha_websocket.py # WebSocket API client (505 lines)
│
├── templates/
│   └── index.html          # Main UI (66 lines)
└── static/
    ├── css/
    │   └── styles.css      # Dark theme stylesheet
    └── js/
        └── app.js          # Frontend logic (502 lines)
/
├── README.md               # User documentation
├── LICENSE                 # MIT License
├── CLAUDE.md               # This file
└── repository.yaml         # repository metadata file
```

---

## API Endpoints

### Health & Status
- `GET /health` - Health check with component status

### Chat Interface
- `POST /api/chat` - Send message to AI agent
  ```json
  {
    "message": "Enable debug logging",
    "conversation_history": [...]
  }
  ```
  Returns:
  ```json
  {
    "success": true,
    "response": "I'll help you enable debug logging...",
    "messages": [...]
  }
  ```

### Approval Workflow
- `POST /api/approve` - Approve/reject changes
  ```json
  {
    "change_id": "abc123",
    "approved": true,
    "validate": true
  }
  ```

---

## Environment Variables

Set via `config.yaml` options or `.env` file for local development:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key or compatible | (required) |
| `OPENAI_API_URL` | API endpoint URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model to use | `gpt-4o` |
| `HA_CONFIG_DIR` | Home Assistant config path | `/config` |
| `BACKUP_DIR` | Backup storage path | `/backup` |
| `LOG_LEVEL` | Logging level | `info` |
| `SUPERVISOR_TOKEN` | Supervisor API token | (auto-set by HA) |

---

## Agent System Architecture

### Function Calling Flow

1. **User Message** → `/api/chat`
2. **Agent System** processes with OpenAI function calling
3. **Tool Execution:**
   - Agent calls `search_config_files` to read current config
   - Agent analyzes and prepares changes
   - Agent calls `propose_config_changes` with full file contents
4. **Changeset Creation:**
   - Stored in memory with unique ID
   - 1-hour expiration
   - Contains file paths, new content, reason
5. **Frontend Display:**
   - Approval card shown in chat
   - "View Changes" button
6. **User Approval:**
   - Modal shows unified diff
   - User approves or rejects
7. **Application:**
   - ConfigurationManager writes files atomically
   - Creates backups
   - Validates with HA API
   - Rollback on failure

### System Prompt

The agent is instructed to:
- **Never apply changes directly** - always use `propose_config_changes`
- Always read current config before proposing changes
- Explain WHY changes are needed, not just WHAT
- Preserve comments and structure
- Warn about breaking changes
- Suggest testing for major changes

### Tool Functions

#### `search_config_files(search_pattern: Optional[str])`
- Searches all YAML files in /config
- Includes virtual files: lovelace.yaml, devices/{id}.json, entities/{id}.json, areas/{id}.json
- Returns file path, content, and match count
- Case-insensitive search
- Excludes custom_components

#### `propose_config_changes(changes: List[Dict], reason: str)`
- Accepts multiple file changes in one batch
- Each change: `{file_path, new_content}`
- Validates YAML/JSON syntax
- Creates changeset with expiration
- Returns changeset_id for approval

---

## Virtual File System

The agent can work with both real files and virtual registry data:

### Real Files
- `configuration.yaml`, `automations.yaml`, `scripts.yaml`, etc.
- Any YAML file in `/config`
- Written directly to filesystem with backups

### Virtual Files (via WebSocket API)

**lovelace.yaml**
- Represents Lovelace dashboard config
- Read via `lovelace/config` WebSocket command
- Write via `lovelace/config/save` WebSocket command

**devices/{device_id}.json**
- Individual device from device registry
- Read via `config/device_registry/list`
- Update via `config/device_registry/update`
- Supports: name_by_user, area_id, labels, disabled_by

**entities/{entity_id}.json**
- Individual entity from entity registry
- Read via `config/entity_registry/list`
- Update via `config/entity_registry/update`
- Supports: name, icon, area_id, labels, new_entity_id

**areas/{area_id}.json**
- Individual area from area registry
- Read via `config/area_registry/list`
- Create via `config/area_registry/create`
- Update via `config/area_registry/update`
- Supports: name (required), picture, icon, aliases

---

## Common Workflows

### 1. Modify Configuration
**User:** "Enable debug logging for homeassistant.core"

**Flow:**
1. Agent calls `search_config_files()` to find configuration.yaml
2. Agent analyzes current logger config
3. Agent calls `propose_config_changes()` with updated logger section
4. Frontend shows approval card
5. User clicks "View Changes"
6. User sees unified diff
7. User clicks "Approve & Apply"
8. Backend creates backup, writes file, validates, applies

### 2. Rename Device
**User:** "Rename the device called 'Call Button' to 'Ludell Call Button'"

**Flow:**
1. Agent calls `search_config_files(search_pattern="Call Button")`
2. Finds `devices/{device_id}.json` with matching device
3. Agent calls `propose_config_changes()` with updated device JSON
4. Approval workflow (same as above)
5. Backend calls WebSocket API `config/device_registry/update`

### 3. View Configuration
**User:** "Show me my MQTT configuration"

**Flow:**
1. Agent calls `search_config_files(search_pattern="mqtt")`
2. Finds relevant files with MQTT config
3. Agent responds with formatted information
4. No changes proposed

---

## Development Setup

### Local Development
```bash
cd /Users/yinzara/github/ha-config-ai-agent

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export HA_CONFIG_DIR="./test_config"
export BACKUP_DIR="./backups"
export OPENAI_API_KEY="your-key-here"
export OPENAI_MODEL="gpt-4o"
export LOG_LEVEL="debug"

# Run development server
uvicorn src.main:app --reload --port 8099
```

### Testing
```bash
# Health check
curl http://localhost:8099/health

# Chat (requires API key)
curl -X POST http://localhost:8099/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What configuration files do you see?"}'
```

### Home Assistant Add-on Installation
1. Copy repo to `/addons/ha-config-ai-agent`
2. Settings → Add-ons → ⋮ → Repositories
3. Add local repository: `/addons`
4. Install "AI Configuration Agent"
5. Configure API key and model
6. Start add-on
7. Access via sidebar panel "Config Agent"

---

## Security Considerations

### Current Security Measures
1. **Ingress Authentication:** All requests authenticated by Home Assistant
2. **AppArmor Profile:** Container isolation with restricted system access
3. **Path Traversal Protection:** All file paths validated against config_dir
4. **Atomic Operations:** Changes written to temp file first
5. **Validation:** HA validates config before applying
6. **Rollback:** Automatic restore from backup on failure
7. **Supervisor Token:** Used for WebSocket API authentication

### Phase 7 Security Enhancements (In Progress)
- [ ] Enhanced YAML injection prevention
- [ ] Rate limiting on API endpoints
- [ ] Audit logging for all changes
- [ ] Input sanitization for AI-generated content
- [ ] Security testing and vulnerability assessment
- [ ] Comprehensive error handling
- [ ] Token exposure prevention in logs

### Known Limitations
- No multi-user isolation (single add-on instance)
- Changesets stored in memory (lost on restart)
- 1-hour changeset expiration not configurable
- No undo beyond manual backup restore
- AI-generated configs not deeply validated (relies on HA validation)

---

## Troubleshooting

### Common Issues

**1. "Agent system not initialized"**
- Check OPENAI_API_KEY is set in add-on configuration
- Verify API URL is correct
- Check logs for API connection errors

**2. "Validation failed"**
- Review the proposed changes for syntax errors
- Check Home Assistant logs for validation details
- Restore from backup if needed

**3. "SUPERVISOR_TOKEN not available"**
- This should be auto-set by Home Assistant
- Check add-on has `hassio_api: true` in config.yaml
- Restart add-on if needed

**4. "WebSocket connection failed"**
- Verify Home Assistant is running
- Check network connectivity
- Review WebSocket URL (should be `ws://supervisor/core/websocket`)

**5. "Lovelace config not available"**
- Ensure Lovelace is in storage mode (not YAML mode)
- Check WebSocket authentication
- Verify user has admin privileges

### Logs
```bash
# View add-on logs
docker logs addon_ai-config-agent

# View Home Assistant logs
tail -f /config/home-assistant.log
```

---

## Roadmap

### Phase 7 (Current) - Security & Safety
- Enhanced input validation
- Rate limiting
- Audit logging
- Security testing

### Phase 8 (Planned) - Testing & Documentation
- Unit tests with pytest
- Integration tests
- CI/CD pipeline
- Comprehensive user guide
- Developer documentation
- Video tutorials

### Future Enhancements
- Multi-user support with isolated sessions
- Persistent changeset storage
- Undo/redo functionality
- Configuration templates library
- Integration with HA blueprints
- Natural language queries for entity states
- Automated configuration optimization suggestions
- Support for packages and includes
- Git integration for version control
- Scheduled configuration reviews

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

## Support

- **GitHub Issues:** https://github.com/yinzara/ha-config-ai-agent/issues
- **Home Assistant Community:** Discussion and help
- **Documentation:** README.md, QUICKSTART.md, INSTALLATION.md

---

## License

MIT License - See LICENSE file for details

---

## Technical Notes for Claude

### When Working on This Project

**Phase 7 Focus:** Currently implementing security enhancements
- Review all input validation
- Add rate limiting to endpoints
- Implement audit logging
- Test for YAML injection vulnerabilities
- Improve error handling

**Code Style:**
- Python 3.11+ with type hints
- Async/await for all I/O
- Descriptive variable names
- Comprehensive docstrings
- Logging at INFO level for user actions, DEBUG for details

**Testing:**
- Manual testing via UI required
- Health check should return `agent_system_ready: true`
- Test with small config changes first
- Always verify backups are created

**Common Commands:**
```bash
# Activate venv
source .venv/bin/activate

# Run dev server
uvicorn src.main:app --reload --port 8099

# Check health
curl http://localhost:8099/health | jq

# View logs
tail -f logs/app.log
```

---

**Last Updated:** January 26, 2025
**Project Phase:** 7 of 8
**Lines of Code:** ~3000+ (Python: ~2000, JavaScript: ~500, HTML/CSS: ~500)
