"""Configuration settings for MCP Server."""
import os
from typing import Optional
from pydantic import BaseSettings


class Settings(BaseSettings):
    """MCP Server configuration settings."""

    # Server Configuration
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 9000

    # Cosmos DB Configuration
    cosmos_endpoint: Optional[str] = os.getenv("COSMOS_ENDPOINT")
    cosmos_key: Optional[str] = os.getenv("COSMOS_KEY")
    cosmos_database: str = os.getenv("COSMOS_DATABASE", "AgenticCloudDiscovery")
    cosmos_container_connections: str = "connections"
    cosmos_container_tools: str = "tools"
    cosmos_container_policies: str = "policies"

    # APIM Configuration
    apim_base_url: Optional[str] = os.getenv("APIM_BASE_URL")
    apim_stub_mode: bool = os.getenv("APIM_STUB_MODE", "false").lower() == "true"
    apim_timeout_seconds: float = float(os.getenv("APIM_TIMEOUT_SECONDS", "30"))

    # Policy Defaults
    default_max_payload_bytes: int = 10485760  # 10MB
    default_max_retries: int = 3
    default_approval_required: bool = True

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
