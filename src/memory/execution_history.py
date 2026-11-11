from typing import Dict, Any, List, Optional
from src.memory.state_db import StateDatabase

class ExecutionHistory:
    """
    Structured execution tracing for tools, commands, test outputs, and errors.
    Allows agents to inspect past tool runs, errors, and diffs to prevent duplicate work or infinite retry loops.
    """

    def __init__(self, db: StateDatabase, session_id: str):
        self.db = db
        self.session_id = session_id

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        status: str,
        execution_time_ms: float,
        task_id: Optional[str] = None
    ) -> None:
        self.db.log_tool_execution(
            session_id=self.session_id,
            task_id=task_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            status=status,
            execution_time_ms=execution_time_ms
        )

    def get_recent_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.db.get_recent_history(self.session_id, limit=limit)

    def get_recent_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        traces = self.get_recent_traces(limit=25)
        errors = [t for t in traces if t.get("status") == "ERROR"]
        return errors[-limit:]

    def get_summary_context(self, limit: int = 5) -> str:
        traces = self.get_recent_traces(limit=limit)
        if not traces:
            return "No tool execution history yet."
        lines = ["### Recent Tool Traces:"]
        for t in traces:
            status_icon = "✓" if t["status"] == "SUCCESS" else "✗"
            lines.append(f"- [{status_icon}] {t['tool_name']} ({t['execution_time_ms']:.1f}ms): {str(t['tool_output'])[:180]}...")
        return "\n".join(lines)

