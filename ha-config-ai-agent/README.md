# AI Configuration Agent

![Project Maintenance][maintenance-shield]

_An AI-powered assistant that helps you manage your Home Assistant configuration using natural language._

![AI Configuration Agent](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5?logo=homeassistant&logoColor=white)

---

## About

AI Configuration Agent brings conversational AI to your Home Assistant configuration management. Simply describe what you want to change, review the proposed modifications, and approve them with confidence.

**Chat with your configuration:**
- "Enable debug logging for the MQTT integration"
- "Show me all my automations that involve lights"
- "Rename my 'Office Button' device to 'Desk Button'"
- "Create an automation that turns on the porch light at sunset"

## Features

* 🤖 **Natural Language Interface** - No YAML expertise required
* ✅ **Approval Workflow** - Review visual diffs before applying changes
* 🔒 **Safe Operations** - Automatic backups, validation, and rollback
* 📊 **Visual Diffs** - See exactly what will change
* 🔌 **Flexible AI Providers** - OpenAI, OpenRouter, Ollama, Azure, or any OpenAI-compatible API
* 📝 **Configuration Management** - Automations, scripts, Lovelace, devices, entities, and areas
* 🔄 **Auto-Reload** - Home Assistant configuration reloads automatically after changes
* 📈 **Token Usage Tracking** - Real-time display of cumulative input/output/cached tokens in the footer

## Configuration

After installation, configure the add-on with your AI provider credentials:

**Minimal Configuration (OpenAI):**
```yaml
openai_api_key: "sk-your-openai-key-here"
```

**Full Configuration:**
```yaml
openai_api_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
openai_api_key: "your-google-api-key-here"
openai_model: "gemini-2.5-flash"
log_level: "info"
system_prompt_file: ""  # Optional: Custom system prompt file path
temperature: ""  # Optional: Model temperature (0.0-2.0, empty=default)
enable_cache_control: false  # Enable prompt caching (Anthropic Claude only)
usage_tracking: "stream_options"  # Token usage method: stream_options, usage, or disabled
```

### Alternative AI Providers

<details>
<summary><b>OpenAI</b> (GPT-5, GPT-4o)</summary>

```yaml
openai_api_url: "https://api.openai.com/v1"
openai_api_key: "sk-proj-your-key-here"
openai_model: "gpt-4o"
usage_tracking: "stream_options"
```
</details>

<details>
<summary><b>Anthropic</b> (Claude)</summary>

```yaml
openai_api_url: "https://api.anthropic.com/v1/"
openai_api_key: "sk-ant-your-key"
openai_model: "claude-4-5-haiku
enable_cache_control: true
usage_tracking: "usage"
```
</details>

<details>
<summary><b>OpenRouter</b> (100+ models)</summary>

```yaml
openai_api_url: "https://openrouter.ai/api/v1"
openai_api_key: "sk-or-v1-your-key"
openai_model: "anthropic/claude-3.5-sonnet"
usage_tracking: "usage"
```
</details>
<details>
<summary><b>Local Ollama</b> (Privacy-first)</summary>

```yaml
openai_api_url: "http://ollama:11434/v1"
openai_api_key: "ollama"
openai_model: "llama3.2"
```
</details>

<details>
<summary><b>Azure OpenAI</b></summary>

```yaml
openai_api_url: "https://your-resource.openai.azure.com/openai/deployments/your-deployment"
openai_api_key: "your-azure-key"
```
</details>

### Custom System Prompt

You can customize the AI agent's behavior by providing a custom system prompt file:

1. Create a text file in your Home Assistant `/config` directory (e.g., `ai_agent_prompt.txt`)
2. Write your custom system prompt instructions
3. Set the configuration option:
   ```yaml
   system_prompt_file: "ai_agent_prompt.txt"
   ```

The file path must be relative to `/config` (e.g., `prompts/custom.txt` for `/config/prompts/custom.txt`).

If not specified or if the file is not found, the built-in default system prompt is used.

See [DOCS.md](DOCS.md) for detailed configuration options and setup instructions.

## Quick Start

1. **Install and configure** the add-on with your API key
2. **Start** the add-on
3. **Open** the "Config Agent" panel from your Home Assistant sidebar
4. **Chat** with the AI about your configuration needs
5. **Review** proposed changes with visual diffs
6. **Approve** changes to apply them safely

## Usage Examples

### Configuration Changes
```
You: Enable debug logging for homeassistant.core
AI: I'll help you enable debug logging. [Proposes changes to logger config]
You: [Reviews diff and approves]
AI: ✅ Successfully applied changes and reloaded configuration
```

### Device Management
```
You: Rename all my call button devices to include "Ludell"
AI: I found 3 call button devices. [Proposes renaming them]
You: [Approves changes]
AI: ✅ Renamed 3 devices successfully
```

### Information Queries
```
You: Show me all automations that trigger at sunset
AI: [Lists and explains relevant automations - no changes]
```

## Documentation

- **[DOCS.md](DOCS.md)** - Detailed installation, configuration, and usage guide
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and updates
- **[CLAUDE.md](../CLAUDE.md)** - Technical architecture and development guide

## Safety & Security

- ✅ All changes require explicit approval (unless `auto_approve` is enabled)
- ✅ Automatic backups created before every change (kept for 10 versions)
- ✅ Home Assistant validates configuration before applying
- ✅ Automatic rollback if validation fails
- ✅ AppArmor container isolation
- ✅ Path traversal protection
- ✅ Ingress authentication via Home Assistant

⚠️ **Important**: While this add-on includes comprehensive safety features, always maintain external backups of your Home Assistant configuration.

## Support

- **[GitHub Issues](https://github.com/yinzara/ha-config-ai-agent/issues)** - Bug reports and feature requests
- **[Home Assistant Community](https://community.home-assistant.io/)** - Discussion and help

## Contributing

Contributions are welcome! Please see [DOCS.md](DOCS.md) for development setup instructions.

## License

MIT License - See [LICENSE](../LICENSE) for details

---

**Made with ❤️ for the Home Assistant community**

[releases-shield]: https://img.shields.io/github/release/yinzara/ha-config-ai-agent.svg
[releases]: https://github.com/yinzara/ha-config-ai-agent/releases
[license-shield]: https://img.shields.io/github/license/yinzara/ha-config-ai-agent.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2025.svg
