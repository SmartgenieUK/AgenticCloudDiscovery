"""Policy enforcement engine for MCP Server."""
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from models import PolicyDocument, ToolSchema, ExecuteToolRequest, ErrorResponse

logger = logging.getLogger(__name__)


class PolicyEnforcement:
    """Policy enforcement logic - validates requests before execution."""

    def __init__(self, policy: Dict):
        """Initialize with a policy document."""
        self.policy = policy
        self.allowed_domains = set(policy.get("allowed_domains", []))
        self.allowed_methods = set(policy.get("allowed_methods", []))
        self.max_payload_bytes = policy.get("max_payload_bytes", 10485760)
        self.max_retries = policy.get("max_retries", 3)
        self.approval_required = policy.get("approval_required", True)

    def validate_tool_approved(self, tool: Dict) -> Tuple[bool, Optional[ErrorResponse]]:
        """Validate that tool status is 'approved'."""
        status = tool.get("status", "pending")

        if status != "approved":
            logger.warning(f"Tool {tool.get('tool_id')} is not approved (status: {status})")
            return False, ErrorResponse(
                code="POLICY_VIOLATION",
                message=f"Tool {tool.get('tool_id')} is not approved for execution (status: {status})",
                details={"tool_id": tool.get("tool_id"), "status": status},
                retryable=False,
                policy_violation=True
            )

        return True, None

    def validate_domain(self, tool: Dict) -> Tuple[bool, Optional[ErrorResponse]]:
        """Validate that tool's allowed domains match policy."""
        tool_domains = set(tool.get("allowed_domains", []))

        # Check if any tool domain is in policy allowed domains
        if not tool_domains.issubset(self.allowed_domains):
            disallowed = tool_domains - self.allowed_domains
            logger.warning(f"Tool {tool.get('tool_id')} has disallowed domains: {disallowed}")
            return False, ErrorResponse(
                code="POLICY_VIOLATION",
                message=f"Tool uses disallowed domains: {disallowed}",
                details={"tool_id": tool.get("tool_id"), "disallowed_domains": list(disallowed)},
                retryable=False,
                policy_violation=True
            )

        return True, None

    def validate_method(self, tool: Dict) -> Tuple[bool, Optional[ErrorResponse]]:
        """Validate that tool's allowed methods match policy."""
        tool_methods = set(tool.get("allowed_methods", []))

        # Check if any tool method is in policy allowed methods
        if not tool_methods.issubset(self.allowed_methods):
            disallowed = tool_methods - self.allowed_methods
            logger.warning(f"Tool {tool.get('tool_id')} has disallowed methods: {disallowed}")
            return False, ErrorResponse(
                code="POLICY_VIOLATION",
                message=f"Tool uses disallowed HTTP methods: {disallowed}",
                details={"tool_id": tool.get("tool_id"), "disallowed_methods": list(disallowed)},
                retryable=False,
                policy_violation=True
            )

        return True, None

    def validate_payload_size(self, request: ExecuteToolRequest) -> Tuple[bool, Optional[ErrorResponse]]:
        """Validate that request payload size is within limits."""
        import json
        payload_size = len(json.dumps(request.args).encode('utf-8'))

        if payload_size > self.max_payload_bytes:
            logger.warning(f"Payload size {payload_size} exceeds max {self.max_payload_bytes}")
            return False, ErrorResponse(
                code="POLICY_VIOLATION",
                message=f"Payload size {payload_size} bytes exceeds maximum {self.max_payload_bytes} bytes",
                details={"payload_size": payload_size, "max_payload_bytes": self.max_payload_bytes},
                retryable=False,
                policy_violation=True
            )

        return True, None

    def validate_retry_budget(self, attempt: int) -> Tuple[bool, Optional[ErrorResponse]]:
        """Validate that retry attempt is within budget."""
        if attempt > self.max_retries:
            logger.warning(f"Attempt {attempt} exceeds max retries {self.max_retries}")
            return False, ErrorResponse(
                code="POLICY_VIOLATION",
                message=f"Retry attempt {attempt} exceeds maximum {self.max_retries}",
                details={"attempt": attempt, "max_retries": self.max_retries},
                retryable=False,
                policy_violation=True
            )

        return True, None

    def enforce(self, request: ExecuteToolRequest, tool: Dict) -> Tuple[bool, Optional[ErrorResponse]]:
        """
        Enforce all policy rules on a tool execution request.

        Returns:
            (is_valid, error_response)
            - (True, None) if all checks pass
            - (False, ErrorResponse) if any check fails
        """
        # Check 1: Tool must be approved
        valid, error = self.validate_tool_approved(tool)
        if not valid:
            return valid, error

        # Check 2: Domain allowlist
        valid, error = self.validate_domain(tool)
        if not valid:
            return valid, error

        # Check 3: Method allowlist
        valid, error = self.validate_method(tool)
        if not valid:
            return valid, error

        # Check 4: Payload size limit
        valid, error = self.validate_payload_size(request)
        if not valid:
            return valid, error

        # Check 5: Retry budget
        valid, error = self.validate_retry_budget(request.attempt)
        if not valid:
            return valid, error

        logger.info(f"Policy enforcement passed for tool {tool.get('tool_id')} (attempt {request.attempt})")
        return True, None


def create_policy_enforcer(policy: Dict) -> PolicyEnforcement:
    """Factory function to create a policy enforcer."""
    return PolicyEnforcement(policy)
