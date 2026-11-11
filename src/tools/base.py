from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class PermissionTier(str, Enum):
    SAFE_READ = "SAFE_READ"              # Inspecting files, searching, git status (Autonomous)
    WORKSPACE_WRITE = "WORKSPACE_WRITE"  # Editing workspace files, git commits (Autonomous or Approval)
    DANGEROUS_SYSTEM = "DANGEROUS_SYSTEM"# Running terminal commands, deletes (Gated)

class ToolResult(BaseModel):
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    diff: Optional[str] = None

class BaseTool(ABC):
    """
    Abstract Base Class for all Autonomous Agent Tools.
    Provides schema definitions, parameter validation, and permission checks.
    """

    name: str
    description: str
    permission_tier: PermissionTier = PermissionTier.SAFE_READ

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON-schema compatible parameter specification."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool deterministically."""
        pass

