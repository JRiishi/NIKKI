from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel
from src.tools.registry import ToolRegistry
from src.memory.working_memory import TaskNode

class WorkerResult(BaseModel):
    success: bool
    output: Any = None
    error: Optional[str] = None
    tool_calls_made: int = 0
    worker_name: str = "base"

class BaseWorker(ABC):
    """
    Abstract Worker Agent.
    Executes an assigned TaskNode given relevant context and access to local tools.
    """

    def __init__(self, name: str, tool_registry: ToolRegistry):
        self.name = name
        self.tools = tool_registry

    @abstractmethod
    def execute(self, task: TaskNode, context: str) -> WorkerResult:
        """Execute the assigned task node."""
        pass
