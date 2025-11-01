"""
AI Agent Tool Functions

Tool functions that agents can call to interact with configuration files.
These wrap the ConfigurationManager for safe AI operations.
"""
import logging
import os
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from ..config import ConfigurationManager, ConfigurationError
from ..ha.ha_websocket import get_lovelace_config_as_yaml

logger = logging.getLogger(__name__)


class AgentTools:
    """
    Tool functions for AI agents to interact with Home Assistant configuration.

    All tools are designed to be called by AI agents and provide:
    - Clear, structured responses
    - Error handling with user-friendly messages
    - Logging of all operations
    - Safety through ConfigurationManager
    """

    def __init__(
        self,
        config_manager: ConfigurationManager,
        workflow: Optional['ValidationWorkflow'] = None,
        agent_system: Optional[Any] = None
    ):
        """
        Initialize agent tools with a configuration manager.

        Args:
            config_manager: ConfigurationManager instance for file operations
            workflow: Optional ValidationWorkflow for approval management
            agent_system: Optional AgentSystem for changeset storage
        """
        self.config_manager = config_manager
        self.workflow = workflow
        self.agent_system = agent_system
        self._lovelace_cache = None  # Cache Lovelace config to avoid repeated API calls
        logger.info("AgentTools initialized")

    async def _get_lovelace_config(self) -> Optional[str]:
        """
        Internal helper to retrieve Lovelace config via WebSocket.

        Returns:
            YAML string of Lovelace config, or None if not available
        """
        # Check if we have supervisor token for WebSocket connection
        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            logger.debug("No SUPERVISOR_TOKEN available, skipping Lovelace config")
            return None

        # Return cached version if available
        if self._lovelace_cache:
            return self._lovelace_cache

        try:
            ws_url = "ws://supervisor/core/websocket"
            lovelace_yaml = await get_lovelace_config_as_yaml(ws_url, supervisor_token)
            if lovelace_yaml:
                self._lovelace_cache = lovelace_yaml
                logger.info("Successfully retrieved Lovelace config")
            return lovelace_yaml
        except Exception as e:
            logger.debug(f"Failed to get Lovelace config: {e}")
            return None

    async def _get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Internal helper to retrieve all devices from registry.

        Returns:
            List of device dictionaries
        """
        from ..ha.ha_websocket import HomeAssistantWebSocket

        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            logger.debug("No SUPERVISOR_TOKEN available, skipping devices")
            return []

        try:
            ws_url = "ws://supervisor/core/websocket"
            ws_client = HomeAssistantWebSocket(ws_url, supervisor_token)
            await ws_client.connect()
            devices = await ws_client.list_devices()
            await ws_client.close()
            return devices
        except Exception as e:
            logger.debug(f"Failed to get devices: {e}")
            return []

    async def _get_all_entities(self) -> List[Dict[str, Any]]:
        """
        Internal helper to retrieve all entities from registry.

        Returns:
            List of entity dictionaries
        """
        from ..ha.ha_websocket import HomeAssistantWebSocket

        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            logger.debug("No SUPERVISOR_TOKEN available, skipping entities")
            return []

        try:
            ws_url = "ws://supervisor/core/websocket"
            ws_client = HomeAssistantWebSocket(ws_url, supervisor_token)
            await ws_client.connect()
            entities = await ws_client.list_entities()
            await ws_client.close()
            return entities
        except Exception as e:
            logger.debug(f"Failed to get entities: {e}")
            return []

    async def _get_all_areas(self) -> List[Dict[str, Any]]:
        """
        Internal helper to retrieve all areas from registry.

        Returns:
            List of area dictionaries
        """
        from ..ha.ha_websocket import HomeAssistantWebSocket

        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        if not supervisor_token:
            logger.debug("No SUPERVISOR_TOKEN available, skipping areas")
            return []

        try:
            ws_url = "ws://supervisor/core/websocket"
            ws_client = HomeAssistantWebSocket(ws_url, supervisor_token)
            await ws_client.connect()
            areas = await ws_client.list_areas()
            await ws_client.close()
            return areas
        except Exception as e:
            logger.debug(f"Failed to get areas: {e}")
            return []

    async def search_config_files(
        self,
        search_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search ALL configuration files for a pattern and return matching files with full contents.

        This tool searches all YAML files, plus virtual files (lovelace.yaml, devices.json,
        entities.json). Returns files that contain the search pattern, or all files if no
        pattern is provided.

        Args:
            search_pattern: Optional text to search for in file contents.
                          Case-insensitive search.
                          If None, returns ALL configuration files.
                          If starts with "/", treats as file path pattern and only searches
                          actual files (skips virtual entities/devices/areas).

        Returns:
            Dict with:
                - success: bool
                - files: List[Dict] with keys:
                    - path: str (relative file path)
                    - content: str (file content as string)
                    - matches: Optional[int] (number of matches if search_pattern provided)
                - count: int (number of files found)
                - search_pattern: Optional[str]
                - error: Optional[str]

        Example:
            >>> await tools.search_config_files(search_pattern="mqtt")
            {
                "success": True,
                "files": [
                    {
                        "path": "configuration.yaml",
                        "content": "mqtt:\\n  broker: ...",
                        "matches": 3
                    }
                ],
                "count": 1,
                "search_pattern": "mqtt"
            }

            >>> await tools.search_config_files(search_pattern="/packages/*.yaml")
            {
                "success": True,
                "files": [
                    {
                        "path": "packages/mqtt.yaml",
                        "content": "...",
                        "matches": 1
                    }
                ],
                "count": 1,
                "search_pattern": "/packages/*.yaml"
            }
        """
        try:
            from pathlib import Path
            import re

            logger.info(f"Agent searching all files - pattern: '{search_pattern or 'none'}'")
            config_dir = self.config_manager.config_dir

            # Check if search_pattern is a file path pattern (starts with "/")
            is_file_path_pattern = search_pattern and search_pattern.startswith("/")

            if is_file_path_pattern:
                logger.info(f"Detected file path pattern: {search_pattern}")
                # Remove leading slash and use as glob pattern
                glob_pattern = search_pattern.lstrip("/")
                matched_paths = list(config_dir.glob(glob_pattern))
                logger.info(f"File path pattern matched {len(matched_paths)} files")
            else:
                # Find all YAML files
                matched_paths = list(config_dir.glob("**/*.yaml"))

            # Filter to only files (not directories) and exclude custom_components
            matched_paths = [
                p for p in matched_paths
                if p.is_file() and 'custom_components' not in p.parts and 'secrets.yaml' not in p.parts
            ]

            # Sort for consistent results
            matched_paths.sort()

            # Read files and optionally filter by content search
            files = []
            for path in matched_paths:
                relative_path = str(path.relative_to(config_dir))
                try:
                    content = await self.config_manager.read_file_raw(relative_path)

                    # If search pattern provided and NOT a file path pattern, check if file contains it or filename matches
                    if search_pattern and not is_file_path_pattern:
                        # Case-insensitive search in content
                        content_matches = len(re.findall(re.escape(search_pattern), content, re.IGNORECASE))
                        # Case-insensitive search in filename
                        filename_matches = len(re.findall(re.escape(search_pattern), relative_path, re.IGNORECASE))
                        total_matches = content_matches + filename_matches

                        if total_matches > 0:
                            files.append({
                                "path": relative_path,
                                "content": content,
                                "matches": total_matches
                            })
                    else:
                        # No search pattern OR file path pattern - include all matched files
                        files.append({
                            "path": relative_path,
                            "content": content,
                            "matches": 1 if is_file_path_pattern else None
                        })

                except Exception as e:
                    logger.warning(f"Could not read {relative_path}: {e}")
                    continue

            # Skip virtual file searches if using file path pattern
            if is_file_path_pattern:
                logger.info(f"Skipping virtual file searches for file path pattern")
                result = {
                    "success": True,
                    "files": files,
                    "count": len(files)
                }
                if search_pattern:
                    result["search_pattern"] = search_pattern
                return result

            # Include virtual files for devices and entities as individual files
            # Format: devices/{device_id}.json and entities/{entity_id}.json
            # Only include if search_pattern provided and matches
            import json

            # Handle individual device files
            if search_pattern:
                try:
                    devices = await self._get_all_devices()
                    device_count = 0
                    for device in devices:
                        device_id = device.get('id', 'unknown')
                        device_path = f"devices/{device_id}.json"
                        device_json = json.dumps(device, indent=2)

                        # Check both content and filename for matches
                        content_matches = len(re.findall(re.escape(search_pattern), device_json, re.IGNORECASE))
                        filename_matches = len(re.findall(re.escape(search_pattern), device_path, re.IGNORECASE))
                        total_matches = content_matches + filename_matches

                        if total_matches > 0:
                            files.append({
                                "path": device_path,
                                "content": device_json,
                                "matches": total_matches
                            })
                            device_count += 1
                    if device_count > 0:
                        logger.info(f"Found {device_count} device(s) matching search pattern")
                except Exception as e:
                    logger.debug(f"Could not retrieve devices (not critical): {e}")

            # Handle individual entity files
            if search_pattern:
                try:
                    entities = await self._get_all_entities()
                    entity_count = 0
                    for entity in entities:
                        entity_id = entity.get('entity_id', 'unknown')
                        entity_path = f"entities/{entity_id}.json"
                        entity_json = json.dumps(entity, indent=2)

                        # Check both content and filename for matches
                        content_matches = len(re.findall(re.escape(search_pattern), entity_json, re.IGNORECASE))
                        filename_matches = len(re.findall(re.escape(search_pattern), entity_path, re.IGNORECASE))
                        total_matches = content_matches + filename_matches

                        if total_matches > 0:
                            files.append({
                                "path": entity_path,
                                "content": entity_json,
                                "matches": total_matches
                            })
                            entity_count += 1
                    if entity_count > 0:
                        logger.info(f"Found {entity_count} entit(ies) matching search pattern")
                except Exception as e:
                    logger.debug(f"Could not retrieve entities (not critical): {e}")

            # Handle individual area files
            if search_pattern:
                try:
                    areas = await self._get_all_areas()
                    area_count = 0
                    for area in areas:
                        area_id = area.get('area_id', 'unknown')
                        area_path = f"areas/{area_id}.json"
                        area_json = json.dumps(area, indent=2)

                        # Check both content and filename for matches
                        content_matches = len(re.findall(re.escape(search_pattern), area_json, re.IGNORECASE))
                        filename_matches = len(re.findall(re.escape(search_pattern), area_path, re.IGNORECASE))
                        total_matches = content_matches + filename_matches

                        if total_matches > 0:
                            files.append({
                                "path": area_path,
                                "content": area_json,
                                "matches": total_matches
                            })
                            area_count += 1
                    if area_count > 0:
                        logger.info(f"Found {area_count} area(s) matching search pattern")
                except Exception as e:
                    logger.debug(f"Could not retrieve areas (not critical): {e}")

            # Handle lovelace.yaml
            try:
                lovelace_content = await self._get_lovelace_config()
                if lovelace_content:
                    if search_pattern:
                        lovelace_path = "lovelace.yaml"
                        # Check both content and filename for matches
                        content_matches = len(re.findall(re.escape(search_pattern), lovelace_content, re.IGNORECASE))
                        filename_matches = len(re.findall(re.escape(search_pattern), lovelace_path, re.IGNORECASE))
                        total_matches = content_matches + filename_matches

                        if total_matches > 0:
                            files.append({
                                "path": lovelace_path,
                                "content": lovelace_content,
                                "matches": total_matches
                            })
                            logger.info(f"lovelace.yaml matched search pattern ({total_matches} matches)")
                    else:
                        files.append({
                            "path": "lovelace.yaml",
                            "content": lovelace_content
                        })
                        logger.info("Included lovelace.yaml in results")
            except Exception as e:
                logger.debug(f"Could not retrieve lovelace.yaml (not critical): {e}")

            logger.info(f"Agent found {len(files)} files (searched {len(matched_paths)} YAML files + 3 virtual files)")

            result = {
                "success": True,
                "files": files,
                "count": len(files)
            }

            if search_pattern:
                result["search_pattern"] = search_pattern

            return result

        except Exception as e:
            logger.error(f"Agent error searching config files: {e}")
            return {
                "success": False,
                "error": f"Error searching files: {str(e)}",
                "search_pattern": search_pattern
            }

    async def propose_config_changes(
        self,
        changes: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Propose changes to one or more configuration files using new content.

        This tool stages changes for user approval. Changes are NOT applied
        immediately - they go through the approval workflow. Multiple files
        can be changed in a single operation.

        Args:
            changes: List of change objects, each with:
                - file_path: str - Relative path to config file (e.g., 'configuration.yaml')
                - new_content: str - The complete new content of the file as a YAML string

        Returns:
            Dict with:
                - success: bool
                - changes: List[Dict] - Details of each proposed change with change_id
                - total_files: int
                - error: Optional[str]

        Example:
            >>> await tools.propose_config_changes(
            ...     changes=[
            ...         {
            ...             "file_path": "configuration.yaml",
            ...             "new_content": "logger:\\n  default: debug\\n"
            ...         },
            ...         {
            ...             "file_path": "automations.yaml",
            ...             "new_content": "- alias: Test\\n  trigger: []\\n"
            ...         }
            ...     ]
            ... )

        Workflow:
            1. First, call search_config_files to get current content
            2. Modify the content as needed for each file
            3. Call this function with all changes in one batch
        """
        try:
            logger.info(f"Agent proposing changes to {len(changes)} file(s)")

            from ruamel.yaml import YAML
            from io import StringIO

            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.default_flow_style = False

            file_changes = []
            errors = []

            # Process and validate each file change
            for change in changes:
                file_path = change.get("file_path")
                new_content = change.get("new_content")

                if not file_path or not new_content:
                    errors.append({
                        "file_path": file_path or "unknown",
                        "error": "Missing file_path or new_content"
                    })
                    continue

                try:
                    logger.info(f"Validating change for: {file_path}")

                    # Special handling for virtual files
                    if file_path == "lovelace.yaml":
                        # Get current Lovelace config
                        current_content = await self._get_lovelace_config()
                        if not current_content:
                            errors.append({
                                "file_path": file_path,
                                "error": "Could not retrieve current Lovelace config"
                            })
                            continue
                    elif file_path.startswith("devices/"):
                        # Individual device file: devices/{device_id}.json
                        device_id = file_path.replace("devices/", "").replace(".json", "")
                        devices = await self._get_all_devices()
                        current_device = next((d for d in devices if d.get('id') == device_id), None)
                        if not current_device:
                            errors.append({
                                "file_path": file_path,
                                "error": f"Device {device_id} not found in registry"
                            })
                            continue
                        import json
                        current_content = json.dumps(current_device, indent=2)
                    elif file_path.startswith("entities/"):
                        # Individual entity file: entities/{entity_id}.json
                        entity_id = file_path.replace("entities/", "").replace(".json", "")
                        entities = await self._get_all_entities()
                        current_entity = next((e for e in entities if e.get('entity_id') == entity_id), None)
                        if not current_entity:
                            errors.append({
                                "file_path": file_path,
                                "error": f"Entity {entity_id} not found in registry"
                            })
                            continue
                        import json
                        current_content = json.dumps(current_entity, indent=2)
                    elif file_path.startswith("areas/"):
                        # Individual area file: areas/{area_id}.json
                        area_id = file_path.replace("areas/", "").replace(".json", "")
                        areas = await self._get_all_areas()
                        current_area = next((a for a in areas if a.get('area_id') == area_id), None)

                        # If area doesn't exist, it will be created - set empty current content
                        if current_area:
                            import json
                            current_content = json.dumps(current_area, indent=2)
                        else:
                            # New area - validate that required 'name' field is present
                            import json
                            proposed_area = json.loads(new_content)
                            if not proposed_area.get('name'):
                                errors.append({
                                    "file_path": file_path,
                                    "error": f"Cannot create area: 'name' field is required"
                                })
                                continue
                            current_content = "{}"  # Empty JSON for new area
                            logger.info(f"Area {area_id} will be created with name: {proposed_area.get('name')}")
                    else:
                        # Read current config as raw text for regular files
                        # Allow missing files (will be created as new files)
                        current_content = await self.config_manager.read_file_raw(file_path, allow_missing=True)
                        if current_content is None:
                            current_content = ""  # Empty content for new files
                            logger.info(f"File {file_path} will be created as a new file")

                    # Validate the new content based on file type
                    if file_path.endswith('.json'):
                        # Validate JSON files (devices.json, entities.json)
                        import json
                        try:
                            json.loads(new_content)
                        except Exception as e:
                            errors.append({
                                "file_path": file_path,
                                "error": f"Invalid JSON in new_content: {str(e)}"
                            })
                            continue
                    else:
                        # Validate YAML files
                        new_io = StringIO(new_content)
                        try:
                            new_config = yaml.load(new_io)
                        except Exception as e:
                            errors.append({
                                "file_path": file_path,
                                "error": f"Invalid YAML in new_content: {str(e)}"
                            })
                            continue

                    # Add to file changes list
                    file_changes.append({
                        "file_path": file_path,
                        "current_content": current_content,
                        "new_content": new_content
                    })

                except ConfigurationError as e:
                    logger.error(f"Agent config proposal error for {file_path}: {e}")
                    errors.append({
                        "file_path": file_path,
                        "error": str(e)
                    })
                except Exception as e:
                    import traceback
                    logger.error(f"Agent unexpected error proposing change for {file_path}: {e}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    errors.append({
                        "file_path": file_path,
                        "error": f"Unexpected error: {str(e)}"
                    })

            # If all files failed, return error
            if len(file_changes) == 0 and len(errors) > 0:
                return {
                    "success": False,
                    "error": f"All {len(errors)} file(s) failed to process",
                    "errors": errors
                }

            # Create a single changeset with all file changes
            import uuid
            from datetime import datetime, timedelta

            changeset_id = str(uuid.uuid4())[:8]
            now = datetime.now()
            expires_at = (now + timedelta(hours=1)).isoformat()

            # Prepare file changes for storage (only file_path and new_content)
            stored_changes = [
                {"file_path": fc["file_path"], "new_content": fc["new_content"]}
                for fc in file_changes
            ]

            # Store changeset in agent_system if available
            if self.agent_system:
                changeset_id = self.agent_system.store_changeset({
                    "changeset_id": changeset_id,
                    "file_changes": stored_changes
                })

            return {
                "success": True,
                "changeset_id": changeset_id,
                "files": [fc["file_path"] for fc in file_changes],
                "total_files": len(file_changes),
                "expires_at": expires_at,
                "errors": errors if errors else None,
                "message": f"Successfully proposed changeset with {len(file_changes)} file(s). Awaiting user approval."
            }

        except Exception as e:
            import traceback
            logger.error(f"Agent error in propose_config_changes: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": f"Error processing changes: {str(e)}"
            }

