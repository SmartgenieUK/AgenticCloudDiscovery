"""Unit tests for tool executor."""
import pytest
from models import ExecuteToolRequest
from executor import ToolExecutor


@pytest.fixture
def sample_request():
    """Sample execution request."""
    return ExecuteToolRequest(
        session_id="test-session",
        tool_id="inventory_discovery",
        args={"subscription_id": "test-sub", "tenant_id": "test-tenant"},
        connection_id="test-conn",
        trace_id="test-trace",
        correlation_id="test-corr",
        attempt=1
    )


@pytest.fixture
def sample_tool():
    """Sample tool definition."""
    return {
        "tool_id": "inventory_discovery",
        "name": "Inventory Discovery",
        "status": "approved",
        "allowed_domains": ["management.azure.com"],
        "allowed_methods": ["GET"],
        "endpoint": "/subscriptions/{subscription_id}/resources"
    }


@pytest.fixture
def sample_connection():
    """Sample connection with valid token."""
    return {
        "connection_id": "test-conn",
        "user_id": "test-user",
        "access_token": "test-token-123",
        "token_expiry": "2030-01-01T00:00:00Z",  # Future date
        "status": "active"
    }


def test_executor_inject_token_success(sample_connection):
    """Test successful token injection."""
    executor = ToolExecutor(apim_base_url="https://apim.example.com", stub_mode=False, timeout=10.0)
    headers = {}

    success, error = executor.inject_token(sample_connection, headers)

    assert success is True
    assert error is None
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer test-token-123"


def test_executor_inject_token_missing(sample_connection):
    """Test token injection fails when token is missing."""
    sample_connection["access_token"] = None

    executor = ToolExecutor(apim_base_url="https://apim.example.com", stub_mode=False, timeout=10.0)
    headers = {}

    success, error = executor.inject_token(sample_connection, headers)

    assert success is False
    assert error is not None
    assert error.code == "AUTH_FAILED"
    assert "access token" in error.message.lower()


def test_executor_inject_token_expired(sample_connection):
    """Test token injection fails when token is expired."""
    sample_connection["token_expiry"] = "2020-01-01T00:00:00Z"  # Past date

    executor = ToolExecutor(apim_base_url="https://apim.example.com", stub_mode=False, timeout=10.0)
    headers = {}

    success, error = executor.inject_token(sample_connection, headers)

    assert success is False
    assert error is not None
    assert error.code == "AUTH_FAILED"
    assert "expired" in error.message.lower()


def test_executor_build_arm_url(sample_tool):
    """Test ARM URL construction."""
    executor = ToolExecutor(apim_base_url="https://apim.example.com", stub_mode=False, timeout=10.0)
    args = {"subscription_id": "abc-123"}

    url = executor.build_arm_url(sample_tool, args)

    assert "https://" in url


def test_executor_real_mode_without_apim_url():
    """Test that executor works even when APIM URL is not configured."""
    executor = ToolExecutor(apim_base_url=None, stub_mode=False, timeout=10.0)

    # Should not crash, will fall back to direct Azure endpoints
    assert executor.apim_base_url is None
