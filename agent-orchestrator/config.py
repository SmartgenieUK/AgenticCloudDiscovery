"""Configuration settings for Agent Orchestrator."""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Orchestrator configuration settings loaded from environment variables."""

    def __init__(self) -> None:
        # Authentication settings
        self.secret_key = os.getenv("AUTH_SECRET_KEY", "dev-secret-change-me")
        self.algorithm = "HS256"
        self.access_token_minutes = int(os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "30"))
        self.refresh_token_days = int(os.getenv("AUTH_REFRESH_TOKEN_DAYS", "7"))

        # Cosmos DB settings
        self.cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
        self.cosmos_key = os.getenv("COSMOS_KEY")
        self.cosmos_db = os.getenv("COSMOS_DATABASE", "agenticcloud")
        self.cosmos_users_container = os.getenv("COSMOS_USERS_CONTAINER", "users")
        self.cosmos_connections_container = os.getenv("COSMOS_CONNECTIONS_CONTAINER", "connections")
        self.cosmos_discoveries_container = os.getenv("COSMOS_DISCOVERIES_CONTAINER", "discoveries")

        # CORS settings
        origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173")
        self.cors_allow_origins: List[str] = [origin.strip() for origin in origins.split(",") if origin.strip()]

        # Cookie settings
        self.cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
        self.cookie_samesite = os.getenv("COOKIE_SAMESITE", "lax").lower()

        # UI settings
        self.ui_base_url = os.getenv("UI_BASE_URL", "http://localhost:5173")

        # OAuth settings - Google
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.getenv(
            "GOOGLE_REDIRECT_URI",
            "http://localhost:8000/auth/oauth/google/callback"
        )

        # OAuth settings - Microsoft
        self.microsoft_client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.microsoft_client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.microsoft_redirect_uri = os.getenv(
            "MICROSOFT_REDIRECT_URI",
            "http://localhost:8000/auth/oauth/microsoft/callback"
        )

        # MCP Server settings
        self.mcp_base_url = os.getenv("MCP_BASE_URL")
        self.mcp_execute_path = os.getenv("MCP_EXECUTE_PATH", "/execute")
        self.mcp_list_tools_path = os.getenv("MCP_LIST_TOOLS_PATH", "/tools")
        self.mcp_stub_mode = os.getenv("MCP_STUB_MODE", "false").lower() == "true"
        self.mcp_timeout_seconds = float(os.getenv("MCP_TIMEOUT_SECONDS", "10"))

        # Orchestrator execution limits
        self.max_plan_steps = int(os.getenv("ORCH_MAX_PLAN_STEPS", "10"))
        self.max_tool_calls = int(os.getenv("ORCH_MAX_TOOL_CALLS", "8"))
        self.max_total_retries = int(os.getenv("ORCH_MAX_TOTAL_RETRIES", "2"))


# Global settings instance
settings = Settings()
