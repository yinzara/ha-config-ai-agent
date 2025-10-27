from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os
import logging
from datetime import datetime

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
    version="0.1.0",
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
        "version": "0.1.0",
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
        "version": "0.1.0"
    })

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat with the AI configuration assistant.

    This is the main endpoint for interacting with the AI agent system.
    The agent can read configuration, propose changes, and answer questions.

    Args:
        request: ChatRequest with user message and optional conversation history

    Returns:
        Dict with:
            - success: bool
            - response: str (agent's final text response)
            - messages: List[Dict] (new messages generated during this request in OpenAI format)

    Raises:
        HTTPException: 500 if agent system not initialized or error occurs
    """
    if not agent_system:
        raise HTTPException(
            status_code=500,
            detail="Agent system not initialized. Please configure OPENAI_API_KEY."
        )

    try:
        result = await agent_system.chat(
            user_message=request.message,
            conversation_history=request.conversation_history
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Unknown error")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


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
