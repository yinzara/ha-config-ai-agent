from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os
import logging
from datetime import datetime
import json as json_lib

from .config import ConfigurationManager, ConfigurationError, ValidationError
from .agents import AgentSystem

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'info').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Phase 2: Global configuration manager instance
config_manager: Optional[ConfigurationManager] = None

# Phase 3: Global agent system instance
agent_system: Optional[AgentSystem] = None

# Phase 2: Pydantic models for API requests
class RestoreBackupRequest(BaseModel):
    backup_name: str
    validate: bool = True

# Phase 3: Pydantic models for agent chat
class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, Any]]] = None

class ApprovalRequest(BaseModel):
    change_id: str
    approved: bool
    validate: bool = True

# Startup/shutdown event handler
@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize application on startup."""
    global config_manager, agent_system

    logger.info("=== AI Configuration Agent Starting ===")
    logger.info(f"OpenAI API URL: {os.getenv('OPENAI_API_URL', 'Not configured')}")
    logger.info(f"OpenAI Model: {os.getenv('OPENAI_MODEL', 'Not configured')}")
    logger.info(f"HA Config Dir: {os.getenv('HA_CONFIG_DIR', 'Not configured')}")
    logger.info(f"Log Level: {log_level}")

    # Phase 2: Initialize configuration manager
    try:
        config_manager = ConfigurationManager(
            config_dir=os.getenv('HA_CONFIG_DIR', '/config'),
            backup_dir=os.getenv('BACKUP_DIR', '/backup')
        )
        logger.info("Configuration manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize configuration manager: {e}")

    # Phase 3: Initialize agent system
    try:
        if config_manager:
            agent_system = AgentSystem(config_manager)
            logger.info("Agent system initialized")
        else:
            logger.warning("Agent system not initialized - config manager unavailable")
    except Exception as e:
        logger.error(f"Failed to initialize agent system: {e}")

    yield

    # Shutdown
    logger.info("=== AI Configuration Agent Shutting Down ===")

# Initialize FastAPI application with lifespan
app = FastAPI(
    title="AI Configuration Agent",
    description="AI-powered Home Assistant configuration management",
    version="0.1.2",
    lifespan=lifespan
)


@app.middleware("http")
async def strip_double_slash_middleware(request: Request, call_next):
    """
    Middleware to remove a leading double slash from the request URL path.
    """
    path = request.scope.get("path")
    if path and path.startswith("//"):
        # Modify the path in the request scope
        request.scope["path"] = path[1:]

    response = await call_next(request)
    return response

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.2",
        "config_manager_ready": config_manager is not None,
        "agent_system_ready": agent_system is not None,
        "openai_configured": bool(os.getenv('OPENAI_API_KEY'))
    }

# Root endpoint - will serve the UI
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve main interface."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": "0.1.2"
    })

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat with the AI configuration assistant using Server-Sent Events (SSE).

    This endpoint streams responses from the AI agent system in real-time.
    The agent can read configuration, propose changes, and answer questions.

    Args:
        request: ChatRequest with user message and optional conversation history

    Returns:
        EventSourceResponse streaming JSON events with:
            - type: "token" | "tool_call" | "tool_result" | "complete" | "error"
            - data: event-specific data

    Raises:
        HTTPException: 500 if agent system not initialized
    """
    if not agent_system:
        raise HTTPException(
            status_code=500,
            detail="Agent system not initialized. Please configure OPENAI_API_KEY."
        )

    async def event_generator():
        """Generate SSE events from the agent system."""
        import json

        def summarize_event(ev: Dict[str, Any]) -> str:
            ev_type = ev.get("event")
            data_raw = ev.get("data")
            summary = ""
            try:
                data = json.loads(data_raw) if isinstance(data_raw, str) else data_raw
            except Exception:
                data = None
            if ev_type == "token":
                content = (data or {}).get("content", "")
                summary = f"len={len(content)}, preview={content[:80]!r}"
            elif ev_type == "tool_call":
                tcs = (data or {}).get("tool_calls") or []
                names = [(tc.get('function') or {}).get('name') for tc in tcs]
                summary = f"count={len(tcs)}, functions={', '.join([n for n in names if n])}"
            elif ev_type == "tool_start":
                summary = f"function={(data or {}).get('function')}, iteration={(data or {}).get('iteration')}"
            elif ev_type == "tool_result":
                res = (data or {}).get("result") or {}
                success = res.get("success")
                summary = f"function={(data or {}).get('function')}, success={success}"
            elif ev_type == "message_complete":
                msg = (data or {}).get("message") or {}
                content = msg.get("content") or ""
                summary = f"len={len(content)}, iteration={(data or {}).get('iteration')}"
            elif ev_type == "complete":
                iterations = (data or {}).get("iterations")
                msgs = (data or {}).get("messages") or []
                summary = f"iterations={iterations}, new_messages={len(msgs)}"
            elif ev_type == "error":
                summary = f"error={(data or {}).get('error')}"
            else:
                # generic summary, truncate data
                raw = data_raw if isinstance(data_raw, str) else (json.dumps(data) if data is not None else "")
                if raw and len(raw) > 120:
                    raw = raw[:120] + '...'
                summary = f"data_preview={raw}"
            return f"{ev_type} | {summary}"

        try:
            async for event in agent_system.chat_stream(
                user_message=request.message,
                conversation_history=request.conversation_history
            ):
                logger.info(f"SSE send -> {summarize_event(event)}")
                yield event
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            err_event = {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
            logger.info(f"SSE send -> {summarize_event(err_event)}")
            yield err_event

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx/proxy
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "Pragma": "no-cache"
        },
        ping=10  # Send ping every 10 seconds to keep connection alive
    )


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    Chat with the AI configuration assistant using WebSocket.

    This is an alternative to the SSE endpoint that avoids buffering issues
    with Home Assistant Ingress proxy.

    The client sends:
        {
            "type": "chat",
            "message": "user message",
            "conversation_history": [...]
        }

    The server sends:
        {
            "event": "token" | "tool_call" | "tool_start" | "tool_result" | "message_complete" | "complete" | "error",
            "data": {...}
        }
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            logger.info(f"WebSocket received: type={data.get('type')}, message_len={len(data.get('message', ''))}")

            if data.get("type") != "chat":
                await websocket.send_json({
                    "event": "error",
                    "data": {"error": "Invalid message type"}
                })
                continue

            if not agent_system:
                await websocket.send_json({
                    "event": "error",
                    "data": {"error": "Agent system not initialized. Please configure OPENAI_API_KEY."}
                })
                continue

            # Stream responses
            try:
                async for event in agent_system.chat_stream(
                    user_message=data.get("message", ""),
                    conversation_history=data.get("conversation_history")
                ):
                    # Parse the JSON data if it's a string
                    event_data = event.get("data", "{}")
                    if isinstance(event_data, str):
                        event_data = json_lib.loads(event_data)

                    # Send each event immediately
                    message = {
                        "event": event.get("event"),
                        "data": event_data
                    }
                    await websocket.send_json(message)
                    logger.debug(f"WebSocket sent: {event.get('event')}")

            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                await websocket.send_json({
                    "event": "error",
                    "data": {"error": str(e)}
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


@app.post("/api/approve")
async def approve_changes(request: ApprovalRequest):
    """
    Approve or reject proposed configuration changes.

    Args:
        request: ApprovalRequest with change_id, approval status, and validation flag

    Returns:
        Dict with:
            - success: bool
            - applied: bool
            - message: str
            - error: Optional[str]

    Raises:
        HTTPException: 500 if agent system not initialized or error occurs

    Note: Full approval workflow will be implemented in Phase 4.
    """
    if not agent_system:
        raise HTTPException(
            status_code=500,
            detail="Agent system not initialized"
        )

    try:
        result = await agent_system.process_approval(
            change_id=request.change_id,
            approved=request.approved,
            validate=request.validate
        )

        return result

    except Exception as e:
        logger.error(f"Approval error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
