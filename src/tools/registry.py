import time
from typing import Dict, Any, List, Optional, Callable
from src.tools.base import BaseTool, ToolResult, PermissionTier
from src.tools.file_tools import ReadFileTool, WriteFileTool, PatchFileTool, ListDirTool
from src.tools.terminal_tools import RunCommandTool
from src.tools.test_tools import RunTestsTool, RunLintTool
from src.tools.git_tools import GitStatusTool, GitDiffTool, GitCommitTool
from src.tools.code_search_tools import RegexSearchTool, SymbolSearchTool
from src.memory.execution_history import ExecutionHistory

class AutonomyMode:
    FULL_AUTONOMOUS = "FULL_AUTONOMOUS"   # Can execute SAFE_READ and WORKSPACE_WRITE automatically; gates DANGEROUS_SYSTEM
    SUPERVISED = "SUPERVISED"             # Gates WORKSPACE_WRITE and DANGEROUS_SYSTEM

class PermissionGate:
    """
    Enforces architectural safety rules.
    Verifies tool execution permissions based on tool tier and system autonomy level.
    """

    def __init__(self, mode: str = AutonomyMode.FULL_AUTONOMOUS):
        self.mode = mode
        self.approvals_given: int = 0
        self.approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None

    def check_permission(self, tool: BaseTool, kwargs: Dict[str, Any]) -> bool:
        if tool.permission_tier == PermissionTier.SAFE_READ:
            return True

        if self.mode == AutonomyMode.FULL_AUTONOMOUS:
            if tool.permission_tier == PermissionTier.WORKSPACE_WRITE:
                return True
            # DANGEROUS_SYSTEM (arbitrary terminal execution) requires validation/callback
            if self.approval_callback:
                return self.approval_callback(tool.name, kwargs)
            return True

        if self.mode == AutonomyMode.SUPERVISED:
            if self.approval_callback:
                return self.approval_callback(tool.name, kwargs)
            return False

        return False

class ToolRegistry:
    """
    Central repository of available agent tools.
    Manages schemas, permission checks, execution profiling, and history logging.
    """

    def __init__(self, execution_history: Optional[ExecutionHistory] = None, permission_gate: Optional[PermissionGate] = None):
        self.tools: Dict[str, BaseTool] = {}
        self.history = execution_history
        self.gate = permission_gate or PermissionGate()
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        defaults = [
            ReadFileTool(),
            WriteFileTool(),
            PatchFileTool(),
            ListDirTool(),
            RunCommandTool(),
            RunTestsTool(),
            RunLintTool(),
            GitStatusTool(),
            GitDiffTool(),
            GitCommitTool(),
            RegexSearchTool(),
            SymbolSearchTool()
        ]
        for t in defaults:
            self.register(t)

    def register(self, tool: BaseTool) -> None:
        self.tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "permission_tier": t.permission_tier.value,
                "schema": t.get_schema()
            }
            for t in self.tools.values()
        ]

    def get_schemas_prompt(self) -> str:
        """Render JSON schemas for LLM system prompt."""
        lines = ["Available Tools:"]
        for t in self.tools.values():
            lines.append(f"- {t.name}: {t.description}")
            lines.append(f"  Schema: {t.get_schema().get('properties', {})}")
        return "\n".join(lines)

    def execute(self, tool_name: str, task_id: Optional[str] = None, **kwargs) -> ToolResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found.")

        # Permission verification
        if not self.gate.check_permission(tool, kwargs):
            err = f"Permission denied for tool '{tool_name}' under tier '{tool.permission_tier.value}'."
            if self.history:
                self.history.record_tool_call(tool_name, kwargs, None, "ERROR", 0.0, task_id)
            return ToolResult(success=False, error=err)

        t0 = time.perf_counter()
        result = tool.execute(**kwargs)
        elapsed = (time.perf_counter() - t0) * 1000

        # Log into execution history
        if self.history:
            status = "SUCCESS" if result.success else "ERROR"
            output_or_error = result.output if result.success else result.error
            self.history.record_tool_call(tool_name, kwargs, output_or_error, status, elapsed, task_id)

        return result
