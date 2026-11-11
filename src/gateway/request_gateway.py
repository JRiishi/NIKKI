import re
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class ValidatedRequest(BaseModel):
    session_id: str
    raw_prompt: str
    sanitized_prompt: str
    inferred_category: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RequestGateway:
    """
    Validates and sanitizes developer input, initializes sessions,
    and performs fast deterministic intent detection before engaging AI engines.
    """

    def validate_and_route(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ValidatedRequest:
        cleaned = prompt.strip()
        if not cleaned:
            raise ValueError("User prompt cannot be empty or whitespace only.")

        sid = session_id or f"session_{uuid.uuid4().hex[:8]}"

        # Fast deterministic intent detection
        category = "general_coding"
        lower = cleaned.lower()
        if any(w in lower for w in ["bug", "error", "fix", "crash", "traceback", "exception", "failed"]):
            category = "bugfix"
        elif any(w in lower for w in ["refactor", "clean up", "optimize", "restructure", "simplify"]):
            category = "refactoring"
        elif any(w in lower for w in ["test", "unit test", "pytest", "coverage", "benchmark"]):
            category = "testing"
        elif any(w in lower for w in ["feature", "implement", "add support", "create", "build"]):
            category = "feature"
        elif any(w in lower for w in ["review", "audit", "check", "inspect", "analyze"]):
            category = "code_review"

        return ValidatedRequest(
            session_id=sid,
            raw_prompt=prompt,
            sanitized_prompt=cleaned,
            inferred_category=category,
            metadata=metadata or {}
        )

