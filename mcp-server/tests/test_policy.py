"""Unit tests for policy enforcement."""
import pytest
from models import ExecuteToolRequest, ErrorResponse
from policy import PolicyEnforcement


@pytest.fixture
def default_policy():
    """Default policy for testing."""
    return {
        "policy_id": "default",
        "allowed_domains": ["management.azure.com", "graph.microsoft.com"],
        "allowed_methods": ["GET", "POST", "PUT"],
        "max_payload_bytes": 1024,  # Small for testing
        "max_retries": 3,
        "approval_required": True
    }


@pytest.fixture
def approved_tool():
    """Approved tool for testing."""
    return {
        "tool_id": "test_tool",
        "name": "Test Tool",
        "status": "approved",
        "allowed_domains": ["management.azure.com"],
        "allowed_methods": ["GET"],
        "args_schema": {}
    }


@pytest.fixture
def sample_request():
    """Sample execution request."""
    return ExecuteToolRequest(
        session_id="test-session",
        tool_id="test_tool",
        args={"subscription_id": "test-sub"},
        connection_id="test-conn",
        attempt=1
    )


def test_policy_enforcement_pass(default_policy, approved_tool, sample_request):
    """Test that valid request passes all policy checks."""
    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is True
    assert error is None


def test_policy_denies_unapproved_tool(default_policy, approved_tool, sample_request):
    """Test that unapproved tool is denied."""
    approved_tool["status"] = "pending"

    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is False
    assert error.code == "POLICY_VIOLATION"
    assert error.policy_violation is True
    assert "not approved" in error.message.lower()


def test_policy_denies_disallowed_domain(default_policy, approved_tool, sample_request):
    """Test that disallowed domain is denied."""
    approved_tool["allowed_domains"] = ["evil.com"]

    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is False
    assert error.code == "POLICY_VIOLATION"
    assert error.policy_violation is True
    assert "disallowed domains" in error.message.lower()


def test_policy_denies_disallowed_method(default_policy, approved_tool, sample_request):
    """Test that disallowed HTTP method is denied."""
    approved_tool["allowed_methods"] = ["DELETE"]  # DELETE not in policy

    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is False
    assert error.code == "POLICY_VIOLATION"
    assert error.policy_violation is True
    assert "disallowed" in error.message.lower()


def test_policy_denies_oversized_payload(default_policy, approved_tool, sample_request):
    """Test that oversized payload is denied."""
    # Create large payload (> 1024 bytes from policy fixture)
    sample_request.args = {"data": "x" * 2000}

    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is False
    assert error.code == "POLICY_VIOLATION"
    assert error.policy_violation is True
    assert "payload size" in error.message.lower()


def test_policy_denies_exceeded_retries(default_policy, approved_tool, sample_request):
    """Test that retry budget is enforced."""
    sample_request.attempt = 5  # Exceeds max_retries=3

    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is False
    assert error.code == "POLICY_VIOLATION"
    assert error.policy_violation is True
    assert "retry" in error.message.lower()


def test_policy_allows_subset_domains(default_policy, approved_tool, sample_request):
    """Test that tool can use subset of policy domains."""
    # Tool uses only 1 domain, policy allows 2
    approved_tool["allowed_domains"] = ["management.azure.com"]

    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is True
    assert error is None


def test_policy_allows_subset_methods(default_policy, approved_tool, sample_request):
    """Test that tool can use subset of policy methods."""
    # Tool uses only GET, policy allows GET/POST/PUT
    approved_tool["allowed_methods"] = ["GET"]

    enforcer = PolicyEnforcement(default_policy)
    is_valid, error = enforcer.enforce(sample_request, approved_tool)

    assert is_valid is True
    assert error is None
