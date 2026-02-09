"""Unit tests for repositories."""
import pytest
from repositories import (
    InMemoryConnectionRepository,
    InMemoryToolRepository,
    InMemoryPolicyRepository
)
from config import settings


def test_in_memory_connection_repo():
    """Test in-memory connection repository."""
    repo = InMemoryConnectionRepository()

    # Initially empty
    assert repo.get_by_id("test-conn") is None

    # Add a connection
    repo.connections["test-conn"] = {
        "connection_id": "test-conn",
        "user_id": "test-user",
        "access_token": "token-123"
    }

    # Retrieve it
    conn = repo.get_by_id("test-conn")
    assert conn is not None
    assert conn["connection_id"] == "test-conn"


def test_in_memory_tool_repo():
    """Test in-memory tool repository."""
    repo = InMemoryToolRepository()

    # Initially empty
    assert len(repo.list_approved()) == 0

    # Add an approved tool
    repo.tools["tool1"] = {
        "tool_id": "tool1",
        "name": "Tool 1",
        "status": "approved"
    }

    # Add a pending tool
    repo.tools["tool2"] = {
        "tool_id": "tool2",
        "name": "Tool 2",
        "status": "pending"
    }

    # List approved should only return approved tools
    approved = repo.list_approved()
    assert len(approved) == 1
    assert approved[0]["tool_id"] == "tool1"

    # Get by ID should work for both
    assert repo.get_by_id("tool1") is not None
    assert repo.get_by_id("tool2") is not None


def test_in_memory_policy_repo():
    """Test in-memory policy repository."""
    repo = InMemoryPolicyRepository(settings)

    # Get default policy (should use hardcoded defaults)
    policy = repo.get_default()
    assert policy is not None
    assert policy["policy_id"] == "default"
    assert "allowed_domains" in policy
    assert "management.azure.com" in policy["allowed_domains"]

    # Add a custom default
    repo.policies["default"] = {
        "policy_id": "default",
        "allowed_domains": ["example.com"],
        "max_retries": 5
    }

    # Should return the custom one
    policy = repo.get_default()
    assert policy["allowed_domains"] == ["example.com"]
    assert policy["max_retries"] == 5
