"""AI Configuration Agent custom component for Home Assistant."""
from __future__ import annotations

import logging
import os
import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_API_URL,
    CONF_MODEL,
    CONF_LOG_LEVEL,
    CONF_TEMPERATURE,
    CONF_SYSTEM_PROMPT_FILE,
    CONF_ENABLE_CACHE_CONTROL,
    CONF_USAGE_TRACKING,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the AI Configuration Agent component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Configuration Agent from a config entry."""
    _LOGGER.info("Setting up AI Configuration Agent")

    # Store configuration
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "server_task": None,
        "port": None
    }

    # Start the FastAPI server in background
    await _start_server(hass, entry)

    # Register services
    await _register_services(hass, entry)

    # Register frontend panel
    await _register_panel(hass, entry)

    return True


async def _start_server(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Start the FastAPI server."""
    import uvicorn
    from pathlib import Path
    import sys

    # Get the component directory (where __init__.py is located)
    component_dir = Path(__file__).parent

    # Add src directory to path (it's in the component directory)
    src_dir = component_dir / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    # Change to component directory so FastAPI can find static/templates
    try:
        os.chdir(str(component_dir))
    except (FileNotFoundError, OSError) as err:
        _LOGGER.warning("Could not change to component directory, continuing anyway: %s", err)

    # Set environment variables from config
    config = entry.data
    os.environ["OPENAI_API_KEY"] = config.get(CONF_API_KEY, "")
    os.environ["OPENAI_API_URL"] = config.get(CONF_API_URL, "https://api.openai.com/v1")
    os.environ["OPENAI_MODEL"] = config.get(CONF_MODEL, "gpt-4o")
    os.environ["HA_CONFIG_DIR"] = hass.config.config_dir
    os.environ["BACKUP_DIR"] = os.path.join(hass.config.config_dir, ".ai_agent_backups")
    os.environ["LOG_LEVEL"] = config.get(CONF_LOG_LEVEL, "info")

    if config.get(CONF_TEMPERATURE):
        os.environ["TEMPERATURE"] = str(config.get(CONF_TEMPERATURE))

    if config.get(CONF_SYSTEM_PROMPT_FILE):
        os.environ["SYSTEM_PROMPT_FILE"] = config.get(CONF_SYSTEM_PROMPT_FILE)

    os.environ["ENABLE_CACHE_CONTROL"] = str(config.get(CONF_ENABLE_CACHE_CONTROL, False)).lower()
    os.environ["USAGE_TRACKING"] = config.get(CONF_USAGE_TRACKING, "stream_options")

    # Create backup directory if it doesn't exist
    os.makedirs(os.environ["BACKUP_DIR"], exist_ok=True)

    # Find available port
    import socket
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()

    hass.data[DOMAIN][entry.entry_id]["port"] = port

    # Import and configure the FastAPI app
    try:
        from .src.main import app, set_hass_instance
        _LOGGER.info("FastAPI app imported successfully")
    except Exception as err:
        _LOGGER.error("Failed to import FastAPI app: %s", err, exc_info=True)
        raise

    # Create uvicorn config
    config_uvicorn = uvicorn.Config(
        app=app,
        host="127.0.0.1",  # Only bind to localhost for security
        port=port,
        log_level=config.get(CONF_LOG_LEVEL, "info").lower(),
        access_log=False
    )

    server = uvicorn.Server(config_uvicorn)

    # Start server in background task
    async def run_server():
        try:
            _LOGGER.info("Starting FastAPI server on 127.0.0.1:%s", port)
            await server.serve()
        except Exception as err:
            _LOGGER.error("Failed to start AI Config Agent server: %s", err, exc_info=True)

    hass.data[DOMAIN][entry.entry_id]["server_task"] = hass.async_create_task(run_server())
    hass.data[DOMAIN][entry.entry_id]["server"] = server

    # Wait a moment for server to start
    await asyncio.sleep(0.5)

    # Set the hass instance on the config manager for validation
    set_hass_instance(hass)

    _LOGGER.info("AI Configuration Agent server task created on port %s", port)


async def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register component services."""

    async def handle_chat(call: ServiceCall) -> dict[str, Any]:
        """Handle chat service call."""
        import aiohttp

        port = hass.data[DOMAIN][entry.entry_id]["port"]
        message = call.data.get("message")
        conversation_history = call.data.get("conversation_history", [])

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:{port}/api/chat",
                json={
                    "message": message,
                    "conversation_history": conversation_history
                }
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result
                else:
                    _LOGGER.error("Chat request failed: %s", await resp.text())
                    return {"success": False, "error": "Request failed"}

    async def handle_approve(call: ServiceCall) -> dict[str, Any]:
        """Handle approve service call."""
        import aiohttp

        port = hass.data[DOMAIN][entry.entry_id]["port"]
        change_id = call.data.get("change_id")
        approved = call.data.get("approved", True)
        validate = call.data.get("validate", True)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://localhost:{port}/api/approve",
                json={
                    "change_id": change_id,
                    "approved": approved,
                    "validate": validate
                }
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result
                else:
                    _LOGGER.error("Approve request failed: %s", await resp.text())
                    return {"success": False, "error": "Request failed"}

    # Register services
    hass.services.async_register(
        DOMAIN,
        "chat",
        handle_chat,
        schema=vol.Schema({
            vol.Required("message"): cv.string,
            vol.Optional("conversation_history"): list,
        })
    )

    hass.services.async_register(
        DOMAIN,
        "approve",
        handle_approve,
        schema=vol.Schema({
            vol.Required("change_id"): cv.string,
            vol.Optional("approved", default=True): cv.boolean,
            vol.Optional("validate", default=True): cv.boolean,
        })
    )


async def _register_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the frontend panel."""
    from homeassistant.components.http import HomeAssistantView
    from aiohttp import web
    import aiohttp

    port = hass.data[DOMAIN][entry.entry_id]["port"]

    class AIConfigAgentView(HomeAssistantView):
        """Proxy view for AI Config Agent."""

        requires_auth = False  # Auth handled by panel iframe
        url = "/api/ai_config_agent/{path:.*}"
        name = "api:ai_config_agent"

        async def get(self, request, path=""):
            """Proxy GET requests."""
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:{port}/{path}"
                if request.query_string:
                    url += f"?{request.query_string}"

                # Copy relevant headers
                headers = {}
                for header in ['Accept', 'Accept-Encoding', 'Accept-Language']:
                    if header in request.headers:
                        headers[header] = request.headers[header]

                try:
                    async with session.get(url, headers=headers) as resp:
                        body = await resp.read()

                        # Create response and set Content-Type header directly to preserve charset
                        response = web.Response(body=body, status=resp.status)

                        # Copy all relevant headers from upstream response
                        for header in ['Content-Type', 'Cache-Control', 'ETag', 'Last-Modified']:
                            if header in resp.headers:
                                response.headers[header] = resp.headers[header]

                        return response
                except Exception as err:
                    _LOGGER.error(f"Proxy GET error for {url}: {err}")
                    return web.Response(text=f"Proxy error: {err}", status=502)

        async def post(self, request, path=""):
            """Proxy POST requests."""
            data = await request.read()
            async with aiohttp.ClientSession() as session:
                url = f"http://localhost:{port}/{path}"
                headers = {"Content-Type": request.content_type or "application/json"}

                try:
                    async with session.post(url, data=data, headers=headers) as resp:
                        body = await resp.read()

                        # Create response and copy headers
                        response = web.Response(body=body, status=resp.status)

                        # Copy Content-Type header to preserve charset
                        if 'Content-Type' in resp.headers:
                            response.headers['Content-Type'] = resp.headers['Content-Type']

                        return response
                except Exception as err:
                    _LOGGER.error(f"Proxy POST error for {url}: {err}")
                    return web.Response(text=f"Proxy error: {err}", status=502)

    hass.http.register_view(AIConfigAgentView())

    # Register WebSocket proxy handler
    async def websocket_proxy(request):
        """Proxy WebSocket connections to the FastAPI server."""
        import aiohttp

        _LOGGER.info(f"WebSocket proxy request received for path: {request.match_info.get('path', '')}")

        ws_server = web.WebSocketResponse()
        await ws_server.prepare(request)

        # Extract path from request
        # The path from match_info will be like "chat" when URL is /api/ai_config_agent/ws/chat
        # We need to prepend "ws/" to match FastAPI's route
        path = request.match_info.get('path', '')
        ws_url = f"ws://localhost:{port}/ws/{path}"

        _LOGGER.info(f"Connecting to upstream WebSocket: {ws_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws_client:
                    _LOGGER.info("WebSocket connection established to upstream server")

                    # Create bidirectional proxy
                    async def forward_to_client():
                        """Forward messages from FastAPI to client."""
                        try:
                            async for msg in ws_client:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    _LOGGER.debug(f"Forwarding text to client: {msg.data[:100]}")
                                    await ws_server.send_str(msg.data)
                                elif msg.type == aiohttp.WSMsgType.BINARY:
                                    await ws_server.send_bytes(msg.data)
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    _LOGGER.error(f"WebSocket error from upstream: {ws_client.exception()}")
                                    break
                                elif msg.type == aiohttp.WSMsgType.CLOSE:
                                    _LOGGER.info("Upstream WebSocket closed")
                                    await ws_server.close()
                                    break
                        except Exception as err:
                            _LOGGER.error(f"Error forwarding to client: {err}", exc_info=True)

                    async def forward_to_server():
                        """Forward messages from client to FastAPI."""
                        try:
                            async for msg in ws_server:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    _LOGGER.debug(f"Forwarding text to server: {msg.data[:100]}")
                                    await ws_client.send_str(msg.data)
                                elif msg.type == aiohttp.WSMsgType.BINARY:
                                    await ws_client.send_bytes(msg.data)
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    _LOGGER.error(f"WebSocket error from client")
                                    break
                                elif msg.type == aiohttp.WSMsgType.CLOSE:
                                    _LOGGER.info("Client WebSocket closed")
                                    await ws_client.close()
                                    break
                        except Exception as err:
                            _LOGGER.error(f"Error forwarding to server: {err}", exc_info=True)

                    # Run both directions concurrently
                    await asyncio.gather(
                        forward_to_client(),
                        forward_to_server(),
                        return_exceptions=True
                    )
        except aiohttp.ClientError as err:
            _LOGGER.error(f"WebSocket client error: {err}", exc_info=True)
        except Exception as err:
            _LOGGER.error(f"WebSocket proxy error: {err}", exc_info=True)
        finally:
            if not ws_server.closed:
                await ws_server.close()
            _LOGGER.info("WebSocket proxy connection closed")

        return ws_server

    # Register WebSocket route
    hass.http.app.router.add_get('/api/ai_config_agent/ws/{path:.*}', websocket_proxy)

    # Register iframe panel that points to our proxy
    from homeassistant.components.frontend import async_register_built_in_panel

    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="Config Agent",
        sidebar_icon="mdi:robot-outline",
        frontend_url_path="ai_config_agent",
        config={"url": "/api/ai_config_agent/"},
        require_admin=True
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading AI Configuration Agent")

    # Stop the server
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    if entry_data:
        server = entry_data.get("server")
        if server:
            server.should_exit = True
            await asyncio.sleep(0.1)

        server_task = entry_data.get("server_task")
        if server_task and not server_task.done():
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    # Remove services
    hass.services.async_remove(DOMAIN, "chat")
    hass.services.async_remove(DOMAIN, "approve")

    # Remove panel
    from homeassistant.components.frontend import async_remove_panel
    async_remove_panel(hass, "ai_config_agent")

    # Clean up stored data
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
