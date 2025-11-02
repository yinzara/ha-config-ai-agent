"""
Home Assistant WebSocket API Client

Handles WebSocket connections to Home Assistant for operations
that require the WebSocket API, such as:
- Retrieving Lovelace UI configuration
- Saving Lovelace UI configuration
"""
import logging
from typing import Any, Dict, Optional, List
import aiohttp

logger = logging.getLogger(__name__)


class HomeAssistantWebSocket:
    """Client for Home Assistant WebSocket API."""

    def __init__(self, url: str, token: str):
        """
        Initialize WebSocket client.

        Args:
            url: Home Assistant WebSocket URL (e.g., ws://supervisor/core/websocket)
            token: Long-lived access token or supervisor token
        """
        self.url = url
        self.token = token
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.message_id = 1
        self.authenticated = False

    async def connect(self) -> None:
        """Establish WebSocket connection and authenticate."""
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(self.url)
            logger.info("WebSocket connection established")

            # Wait for auth_required message
            msg = await self.ws.receive_json()
            if msg.get("type") != "auth_required":
                raise Exception(f"Unexpected message type: {msg.get('type')}")

            # Send authentication
            await self.ws.send_json({
                "type": "auth",
                "access_token": self.token
            })

            # Wait for auth response
            auth_response = await self.ws.receive_json()
            if auth_response.get("type") == "auth_ok":
                self.authenticated = True
                logger.info("WebSocket authentication successful")
            else:
                raise Exception(f"Authentication failed: {auth_response}")

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await self.close()
            raise

    async def close(self) -> None:
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        self.authenticated = False
        logger.info("WebSocket connection closed")

    async def call(self, message_type: str, **kwargs) -> Dict[str, Any]:
        """
        Send a WebSocket command and wait for response.

        Args:
            message_type: Type of message (e.g., "lovelace/config")
            **kwargs: Additional message parameters

        Returns:
            Response data

        Raises:
            Exception: If call fails or connection not authenticated
        """
        if not self.authenticated or not self.ws:
            raise Exception("WebSocket not authenticated")

        msg_id = self.message_id
        self.message_id += 1

        # Send message
        message = {
            "id": msg_id,
            "type": message_type,
            **kwargs
        }
        await self.ws.send_json(message)
        logger.debug(f"Sent WebSocket message: {message}")

        # Wait for response with matching ID
        while True:
            response = await self.ws.receive_json()
            logger.debug(f"Received WebSocket message: {response}")

            if response.get("id") == msg_id:
                if response.get("type") == "result":
                    if response.get("success", True):
                        return response.get("result", {})
                    else:
                        error = response.get("error", {})
                        raise Exception(f"WebSocket call failed: {error}")
                else:
                    raise Exception(f"Unexpected response type: {response.get('type')}")

    async def get_lovelace_config(self) -> Dict[str, Any]:
        """
        Retrieve Lovelace UI configuration.

        Returns:
            Lovelace configuration as dictionary

        Raises:
            Exception: If retrieval fails
        """
        logger.info("Retrieving Lovelace configuration via WebSocket")
        try:
            config = await self.call("lovelace/config", force=False)
            logger.info("Successfully retrieved Lovelace configuration")
            return config
        except Exception as e:
            logger.error(f"Failed to retrieve Lovelace config: {e}")
            raise

    async def save_lovelace_config(self, config: Dict[str, Any]) -> None:
        """
        Save Lovelace UI configuration.

        Args:
            config: Lovelace configuration dictionary

        Raises:
            Exception: If save fails
        """
        logger.info("Saving Lovelace configuration via WebSocket")
        try:
            await self.call("lovelace/config/save", config=config)
            logger.info("Successfully saved Lovelace configuration")
        except Exception as e:
            logger.error(f"Failed to save Lovelace config: {e}")
            raise

    async def reload_config(self) -> None:
        """
        Reload Home Assistant configuration (calls homeassistant.reload_all service).

        This reloads all reloadable components without requiring a full restart.

        Raises:
            Exception: If reload fails
        """
        logger.info("Reloading Home Assistant configuration via WebSocket")
        try:
            await self.call(
                "call_service",
                domain="homeassistant",
                service="reload_all",
                return_response=False,
                service_data={}
            )
            logger.info("Successfully triggered Home Assistant configuration reload")
        except Exception as e:
            logger.error(f"Failed to reload Home Assistant config: {e}")
            raise

    async def list_devices(self) -> List[Dict[str, Any]]:
        """
        Get list of all devices from device registry.

        Returns:
            List of device dictionaries with device information

        Raises:
            Exception: If request fails
        """
        logger.info("Retrieving device registry via WebSocket")
        try:
            devices = await self.call("config/device_registry/list")
            logger.info(f"Successfully retrieved {len(devices)} devices")
            return devices
        except Exception as e:
            logger.error(f"Failed to retrieve device registry: {e}")
            raise

    async def update_device(
        self,
        device_id: str,
        name_by_user: Optional[str] = None,
        area_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
        disabled_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a device in the device registry.

        Args:
            device_id: ID of the device to update
            name_by_user: User-defined name for the device
            area_id: Area ID to assign device to
            labels: List of label IDs
            disabled_by: How device is disabled (None to enable)

        Returns:
            Updated device information

        Raises:
            Exception: If update fails
        """
        logger.info(f"Updating device {device_id}")
        try:
            params = {"device_id": device_id}
            if name_by_user is not None:
                params["name_by_user"] = name_by_user
            if area_id is not None:
                params["area_id"] = area_id
            if labels is not None:
                params["labels"] = labels
            if disabled_by is not None:
                params["disabled_by"] = disabled_by

            result = await self.call("config/device_registry/update", **params)
            logger.info(f"Successfully updated device {device_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update device: {e}")
            raise

    async def list_entities(self) -> List[Dict[str, Any]]:
        """
        Get list of all entities from entity registry.

        Returns:
            List of entity dictionaries with entity information

        Raises:
            Exception: If request fails
        """
        logger.info("Retrieving entity registry via WebSocket")
        try:
            entities = await self.call("config/entity_registry/list")
            logger.info(f"Successfully retrieved {len(entities)} entities")
            return entities
        except Exception as e:
            logger.error(f"Failed to retrieve entity registry: {e}")
            raise

    async def list_entities_for_display(self) -> List[Dict[str, Any]]:
        """
        Get list of entities optimized for display (includes state info).

        Returns:
            List of entity dictionaries with display information

        Raises:
            Exception: If request fails
        """
        logger.info("Retrieving entity registry for display via WebSocket")
        try:
            entities = await self.call("config/entity_registry/list_for_display")
            logger.info(f"Successfully retrieved {len(entities)} entities for display")
            return entities
        except Exception as e:
            logger.error(f"Failed to retrieve entity registry for display: {e}")
            raise

    async def update_entity(
        self,
        entity_id: str,
        name: Optional[str] = None,
        icon: Optional[str] = None,
        area_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
        new_entity_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an entity in the entity registry.

        Args:
            entity_id: ID of the entity to update
            name: Friendly name for the entity (null to use default)
            icon: Icon for the entity
            area_id: Area ID to assign entity to
            labels: List of label IDs
            new_entity_id: New entity ID (for renaming entity ID itself)

        Returns:
            Updated entity information

        Raises:
            Exception: If update fails
        """
        logger.info(f"Updating entity {entity_id}")
        try:
            params = {"entity_id": entity_id}
            if name is not None:
                params["name"] = name
            if icon is not None:
                params["icon"] = icon
            if area_id is not None:
                params["area_id"] = area_id
            if labels is not None:
                params["labels"] = labels
            if new_entity_id is not None:
                params["new_entity_id"] = new_entity_id

            result = await self.call("config/entity_registry/update", **params)
            logger.info(f"Successfully updated entity {entity_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            raise

    async def list_areas(self) -> List[Dict[str, Any]]:
        """Get list of all areas from area registry."""
        logger.info("Retrieving area registry via WebSocket")
        try:
            result = await self.call("config/area_registry/list")
            areas = result if isinstance(result, list) else []
            logger.info(f"Successfully retrieved {len(areas)} areas")
            return areas
        except Exception as e:
            logger.error(f"Failed to retrieve area registry: {e}")
            raise

    async def create_area(
        self,
        name: str,
        picture: Optional[str] = None,
        icon: Optional[str] = None,
        aliases: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new area in the area registry.

        Args:
            name: Name of the area (required)
            picture: Optional picture URL
            icon: Optional icon name
            aliases: Optional list of aliases

        Returns:
            Created area information including generated area_id
        """
        logger.info(f"Creating new area: {name}")
        try:
            params = {"name": name}
            if picture is not None:
                params["picture"] = picture
            if icon is not None:
                params["icon"] = icon
            if aliases is not None:
                params["aliases"] = aliases

            result = await self.call("config/area_registry/create", **params)
            logger.info(f"Successfully created area {name} with ID {result.get('area_id')}")
            return result
        except Exception as e:
            logger.error(f"Failed to create area: {e}")
            raise

    async def update_area(
        self,
        area_id: str,
        name: Optional[str] = None,
        picture: Optional[str] = None,
        icon: Optional[str] = None,
        aliases: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update an area in the area registry."""
        logger.info(f"Updating area {area_id}")
        try:
            params = {"area_id": area_id}
            if name is not None:
                params["name"] = name
            if picture is not None:
                params["picture"] = picture
            if icon is not None:
                params["icon"] = icon
            if aliases is not None:
                params["aliases"] = aliases

            result = await self.call("config/area_registry/update", **params)
            logger.info(f"Successfully updated area {area_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to update area: {e}")
            raise


async def get_lovelace_config_as_yaml(url: str, token: str) -> Optional[str]:
    """
    Helper function to retrieve Lovelace config as YAML string.

    Args:
        url: WebSocket URL
        token: Access token

    Returns:
        YAML string of Lovelace config, or None if retrieval fails
    """
    ws_client = HomeAssistantWebSocket(url, token)
    try:
        await ws_client.connect()
        config = await ws_client.get_lovelace_config()

        # Convert to YAML string
        from ruamel.yaml import YAML
        from io import StringIO

        yaml = YAML()
        yaml.default_flow_style = False
        yaml.preserve_quotes = True
        yaml.width = 4096

        stream = StringIO()
        yaml.dump(config, stream)
        return stream.getvalue()

    except Exception as e:
        logger.error(f"Failed to get Lovelace config: {e}")
        return None
    finally:
        await ws_client.close()


async def save_lovelace_config_from_yaml(url: str, token: str, yaml_content: str) -> None:
    """
    Helper function to save Lovelace config from YAML string.

    Args:
        url: WebSocket URL
        token: Access token
        yaml_content: YAML string to parse and save

    Raises:
        Exception: If save fails
    """
    ws_client = HomeAssistantWebSocket(url, token)
    try:
        await ws_client.connect()

        # Parse YAML to dict
        from ruamel.yaml import YAML
        from io import StringIO

        yaml = YAML()
        config = yaml.load(StringIO(yaml_content))

        await ws_client.save_lovelace_config(config)

    finally:
        await ws_client.close()


async def reload_homeassistant_config(url: str, token: str) -> None:
    """
    Helper function to reload Home Assistant configuration.

    Args:
        url: WebSocket URL
        token: Access token

    Raises:
        Exception: If reload fails
    """
    ws_client = HomeAssistantWebSocket(url, token)
    try:
        await ws_client.connect()
        await ws_client.reload_config()
    finally:
        await ws_client.close()