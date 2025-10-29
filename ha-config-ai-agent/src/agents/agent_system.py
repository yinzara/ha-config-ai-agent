import logging
import os
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
from ..agents.tools import AgentTools
from ..config import ConfigurationManager
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class Changeset:
    """Represents a proposed set of configuration changes."""
    changeset_id: str
    file_changes: List[Dict[str, str]]  # List of {file_path, new_content}
    created_at: str
    expires_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentSystem:
    """
    Multi-agent system for Home Assistant configuration management.

    Uses OpenAI's GPT models to provide intelligent configuration assistance:
    - Understanding user requests
    - Reading and analyzing configuration
    - Proposing safe changes
    - Explaining configuration decisions
    """

    def __init__(self, config_manager: ConfigurationManager, system_prompt: Optional[str] = None):
        """
        Initialize the agent system.

        Args:
            config_manager: ConfigurationManager for file operations
            system_prompt: Optional custom system prompt. If not provided, uses default.
        """
        self.config_manager = config_manager
        self.tools = AgentTools(config_manager, agent_system=self)

        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("No OpenAI API key configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=os.getenv('OPENAI_API_URL', 'https://api.openai.com/v1')
            )

        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')

        # Get temperature from environment variable, use None if not specified
        temperature_str = os.getenv('TEMPERATURE')
        self.temperature = float(temperature_str) if temperature_str else None

        logger.info(f"AgentSystem initialized with model: {self.model}")
        if self.temperature is not None:
            logger.info(f"Temperature: {self.temperature}")

        # In-memory storage for pending changesets
        self.pending_changesets: Dict[str, Changeset] = {}

        # System prompt for the configuration agent
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        if system_prompt:
            logger.info(f"Using custom system prompt ({len(system_prompt)} characters)")
        else:
            logger.info("Using default system prompt")

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for the configuration agent."""
        return """You are a Home Assistant Configuration Assistant.

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
- NEVER suggest changes directly - always use propose_config_changes
- Always read the current configuration before proposing changes
- Explain your reasoning in your response when calling propose_config_changes
- The user can accept or reject your proposed config changes through their own UI
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

Remember: You're helping manage a production Home Assistant system. Safety and clarity are paramount."""

    async def chat_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Process a user message and stream response events in real-time.

        Args:
            user_message: The user's message/request
            conversation_history: Optional list of previous messages
                                Format: [{"role": "user"|"assistant", "content": "..."}]

        Yields:
            Dict events with:
                - event: "token" | "tool_call" | "tool_result" | "message_complete" | "complete" | "error"
                - data: JSON string with event-specific data

        Example:
            >>> async for event in agent_system.chat_stream("Enable debug logging"):
            ...     print(event)
        """
        import json

        if not self.client:
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": "OpenAI API not configured. Please set OPENAI_API_KEY environment variable."
                })
            }
            return

        try:
            logger.info(f"Agent streaming user message: {user_message[:100]}...")

            # Build messages list with prompt caching support
            # System prompt with cache control (marks the system prompt for caching)
            messages = [{
                "role": "system",
                "content": self.system_prompt,
                "cache_control": {"type": "ephemeral"}
            }]

            # Track the starting point for new messages (after history)
            history_length = 1  # system message
            if conversation_history:
                # Add conversation history
                # Mark the last message in history for caching if there's substantial history
                for idx, msg in enumerate(conversation_history):
                    is_last_history_msg = (idx == len(conversation_history) - 1)
                    if is_last_history_msg and len(conversation_history) >= 3:
                        # Cache the conversation history at this breakpoint
                        msg_with_cache = dict(msg)
                        msg_with_cache["cache_control"] = {"type": "ephemeral"}
                        messages.append(msg_with_cache)
                    else:
                        messages.append(msg)
                history_length += len(conversation_history)

            # Add current user message
            messages.append({"role": "user", "content": user_message})

            # Define available tools for function calling with cache control
            # Mark tools for caching to reduce repeated processing
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_config_files",
                        "description": "Search configuration files (all YAML files + lovelace.yaml, plus individual device/entity/area files if search_pattern matches). Returns individual files like devices/{id}.json, entities/{entity_id}.json, and areas/{area_id}.json for matching items. Devices/entities/areas are ONLY included when search_pattern is provided.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "search_pattern": {
                                    "type": "string",
                                    "description": "Optional text to search for in file contents (case-insensitive). Only files containing this text will be returned. Omit to return all files."
                                }
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "propose_config_changes",
                        "description": "Propose changes to one or more configuration files for user approval. Use this to batch multiple file changes together. First use search_config_files to read files, then provide complete new content for each as YAML strings.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "changes": {
                                    "type": "array",
                                    "description": "Array of file changes. Each change must include file_path and new_content.",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "file_path": {
                                                "type": "string",
                                                "description": "Relative path to config file (e.g., 'configuration.yaml', 'switches.yaml'). New areas can be specified with 'areas/{area_id}.json' and must include the 'name'"
                                            },
                                            "new_content": {
                                                "type": "string",
                                                "description": "The complete new content of the file as a valid YAML string. Include all lines - both changed and unchanged."
                                            }
                                        },
                                        "required": ["file_path", "new_content"]
                                    }
                                },
                            },
                            "required": ["changes"]
                        }
                    },
                    "cache_control": {"type": "ephemeral"}
                }
            ]

            # Track tool calls and results
            new_messages = []

            # Loop to handle multiple rounds of tool calls
            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"[ITERATION {iteration}] Calling OpenAI streaming API")

                # Call OpenAI API with streaming
                api_params = {
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": True
                }

                # Add temperature if specified
                if self.temperature is not None:
                    api_params["temperature"] = self.temperature

                stream = await self.client.chat.completions.create(**api_params)

                # Accumulate the streaming response
                accumulated_content = ""
                accumulated_tool_calls = []
                current_tool_call = None
                tool_calls_announced = False
                tool_calls_pending_announced = False

                async for chunk in stream:
                    delta = chunk.choices[0].delta

                    # Stream content tokens
                    if delta.content:
                        accumulated_content += delta.content
                        logger.debug(f"[STREAM] Yielding token: {delta.content[:50]}")
                        yield {
                            "event": "token",
                            "data": json.dumps({
                                "content": delta.content,
                                "iteration": iteration
                            })
                        }

                    # Handle tool calls
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            # Initialize new tool call
                            if tool_call_delta.index is not None:
                                while len(accumulated_tool_calls) <= tool_call_delta.index:
                                    accumulated_tool_calls.append({
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""}
                                    })
                                current_tool_call = accumulated_tool_calls[tool_call_delta.index]

                            # Update tool call details
                            if tool_call_delta.id:
                                current_tool_call["id"] = tool_call_delta.id
                            if tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    current_tool_call["function"]["name"] = tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    current_tool_call["function"]["arguments"] += tool_call_delta.function.arguments

                        # Announce tool calls to UI as soon as we know them (may have partial arguments)
                        if not tool_calls_announced and any(tc.get("function", {}).get("name") for tc in accumulated_tool_calls):
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "tool_calls": accumulated_tool_calls,
                                    "iteration": iteration
                                })
                            }
                            tool_calls_announced = True

                    # Check for finish reason
                    if chunk.choices[0].finish_reason:
                        break

                # Check if we have tool calls
                if not accumulated_tool_calls:
                    # No tool calls - final response
                    logger.info(f"[ITERATION {iteration}] No tool calls, final response received")

                    # Send message complete event with full message data
                    assistant_message = {
                        "role": "assistant",
                        "content": accumulated_content
                    }
                    new_messages.append(assistant_message)

                    yield {
                        "event": "message_complete",
                        "data": json.dumps({
                            "message": assistant_message,
                            "iteration": iteration
                        })
                    }
                    break

                # We have tool calls - add assistant message to history
                logger.info(f"[ITERATION {iteration}] Processing {len(accumulated_tool_calls)} tool call(s)")

                assistant_message = {
                    "role": "assistant",
                    "content": accumulated_content,
                    "tool_calls": accumulated_tool_calls
                }
                messages.append(assistant_message)
                new_messages.append(assistant_message)

                # Notify about ALL tool calls upfront before executing any (only if not already announced)
                if not tool_calls_announced:
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({
                            "tool_calls": accumulated_tool_calls,
                            "iteration": iteration
                        })
                    }
                    tool_calls_announced = True

                # Execute each tool call and stream results immediately
                for tool_idx, tool_call in enumerate(accumulated_tool_calls):
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])

                    logger.info(f"[ITERATION {iteration}] Calling tool: {function_name}")

                    # Send individual tool execution start event
                    yield {
                        "event": "tool_start",
                        "data": json.dumps({
                            "tool_call_id": tool_call["id"],
                            "function": function_name,
                            "arguments": function_args,
                            "iteration": iteration
                        })
                    }

                    # Execute the tool function
                    if function_name == "search_config_files":
                        result = await self.tools.search_config_files(**function_args)
                        logger.info(f"[ITERATION {iteration}] Tool result: success={result.get('success')}, file_count={result.get('count')}")
                    elif function_name == "propose_config_changes":
                        if "changes" not in function_args or not isinstance(function_args["changes"], list):
                            error_msg = (
                                "ERROR: propose_config_changes requires a 'changes' parameter with a list of file changes. "
                                "Each change must have 'file_path' and 'new_content'. "
                                "You MUST first read files with search_config_files, then provide all modified content. "
                                f"Received args: {function_args}"
                            )
                            logger.error(error_msg)
                            result = {"success": False, "error": error_msg}
                        else:
                            result = await self.tools.propose_config_changes(**function_args)
                            logger.info(f"[ITERATION {iteration}] Tool result: success={result.get('success')}, changeset_id={result.get('changeset_id')}")
                    else:
                        result = {"success": False, "error": f"Unknown tool: {function_name}"}
                        logger.error(f"[ITERATION {iteration}] Unknown tool requested: {function_name}")

                    # Add tool result to messages with cache control on the last tool result
                    is_last_tool = (tool_idx == len(accumulated_tool_calls) - 1)
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result)
                    }
                    # Mark the last tool result for caching to preserve full context
                    if is_last_tool:
                        tool_message["cache_control"] = {"type": "ephemeral"}

                    messages.append(tool_message)
                    new_messages.append(tool_message)

                    # Notify about tool result immediately after execution
                    yield {
                        "event": "tool_result",
                        "data": json.dumps({
                            "tool_call_id": tool_call["id"],
                            "function": function_name,
                            "result": result,
                            "iteration": iteration
                        })
                    }

            # Send completion event with all new messages
            if iteration >= max_iterations:
                logger.warning(f"Hit max iterations ({max_iterations}), stopping")
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "error": "Maximum iteration limit reached. Please try breaking down your request."
                    })
                }

            logger.info(f"Agent completed after {iteration} iteration(s)")

            yield {
                "event": "complete",
                "data": json.dumps({
                    "messages": new_messages,
                    "iterations": iteration
                })
            }

        except Exception as e:
            logger.error(f"Agent streaming error: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    def store_changeset(self, changeset_data: Dict[str, Any]) -> str:
        """
        Store a changeset for later approval.

        Args:
            changeset_data: Dictionary with file_changes and changeset_id

        Returns:
            changeset_id
        """
        import uuid
        changeset_id = changeset_data.get('changeset_id') or str(uuid.uuid4())[:8]

        now = datetime.now()
        changeset = Changeset(
            changeset_id=changeset_id,
            file_changes=changeset_data['file_changes'],
            created_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat()
        )

        self.pending_changesets[changeset_id] = changeset
        logger.info(f"Stored changeset {changeset_id} with {len(changeset.file_changes)} file(s)")
        return changeset_id

    async def process_approval(
        self,
        change_id: str,
        approved: bool,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Process user's approval/rejection of proposed changes.

        Args:
            change_id: Unique identifier for the proposed change
            approved: Whether user approved the changes
            validate: Whether to validate after applying changes

        Returns:
            Dict with:
                - success: bool
                - applied: bool
                - message: str
                - error: Optional[str]
        """
        logger.info(f"Processing approval for change {change_id}: {'approved' if approved else 'rejected'}")

        # Check if changeset exists
        changeset = self.pending_changesets.get(change_id)
        if not changeset:
            return {
                "success": False,
                "applied": False,
                "message": f"Changeset {change_id} not found or has expired"
            }

        # If rejected, just remove and return
        if not approved:
            del self.pending_changesets[change_id]
            return {
                "success": True,
                "applied": False,
                "message": "Changes rejected by user"
            }

        # Check if expired
        expires_at = datetime.fromisoformat(changeset.expires_at)
        if datetime.now() > expires_at:
            del self.pending_changesets[change_id]
            return {
                "success": False,
                "applied": False,
                "message": "Changeset has expired. Please re-propose the changes."
            }

        # Apply changes
        try:
            applied_files = []
            failed_files = []

            # Step 1: Write all files first (without validation)
            for file_change in changeset.file_changes:
                file_path = file_change['file_path']
                new_content = file_change['new_content']

                try:
                    await self.config_manager.write_file_raw(
                        file_path=file_path,
                        content=new_content,
                        create_backup=True
                    )
                    applied_files.append(file_path)
                    logger.info(f"Applied changes to {file_path}")
                except Exception as e:
                    logger.error(f"Failed to apply changes to {file_path}: {e}")
                    failed_files.append({"file_path": file_path, "error": str(e)})

            # Step 2: If validation requested and files were written, validate all at once
            validation_failed = False
            if validate and applied_files:
                try:
                    logger.info("Validating configuration after writing all files...")
                    await self.config_manager.validate_config()
                    logger.info("Configuration validation passed")
                except Exception as e:
                    logger.error(f"Configuration validation failed: {e}")
                    validation_failed = True
                    # Note: We don't rollback here because backups were created
                    # Users can manually restore from backups if needed
                    failed_files.append({
                        "file_path": "validation",
                        "error": f"Configuration validation failed: {str(e)}"
                    })

            # Remove changeset from pending
            del self.pending_changesets[change_id]

            # Reload Home Assistant configuration after successful changes (only if validation passed)
            reload_success = False
            if applied_files and not validation_failed:
                try:
                    from ..ha.ha_websocket import reload_homeassistant_config

                    supervisor_token = os.getenv('SUPERVISOR_TOKEN')
                    if supervisor_token:
                        ws_url = "ws://supervisor/core/websocket"
                        await reload_homeassistant_config(ws_url, supervisor_token)
                        reload_success = True
                        logger.info("Home Assistant configuration reloaded successfully")
                    else:
                        logger.warning("SUPERVISOR_TOKEN not available, skipping config reload")
                except Exception as e:
                    logger.warning(f"Failed to reload Home Assistant config: {e}")

            if failed_files:
                return {
                    "success": True,
                    "applied": True,
                    "message": f"Partially applied: {len(applied_files)} succeeded, {len(failed_files)} failed",
                    "applied_files": applied_files,
                    "failed_files": failed_files,
                    "config_reloaded": reload_success
                }
            else:
                message = f"Successfully applied changes to {len(applied_files)} file(s)"
                if reload_success:
                    message += " and reloaded Home Assistant configuration"
                return {
                    "success": True,
                    "applied": True,
                    "message": message,
                    "applied_files": applied_files,
                    "config_reloaded": reload_success
                }

        except Exception as e:
            logger.error(f"Error applying changeset: {e}", exc_info=True)
            return {
                "success": False,
                "applied": False,
                "message": f"Error applying changes: {str(e)}"
            }
