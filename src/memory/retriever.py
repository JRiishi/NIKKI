from typing import Dict, Any, List, Optional
from src.memory.working_memory import WorkingMemory
from src.memory.project_memory import ProjectMemory
from src.memory.execution_history import ExecutionHistory

class ContextRetriever:
    """
    Context Assembly Engine.
    Aggregates active working memory, relevant project memory, and recent execution traces
    while enforcing strict token budget bounds to prevent context blowout and VRAM degradation.
    """

    def __init__(
        self,
        working_memory: WorkingMemory,
        project_memory: ProjectMemory,
        execution_history: ExecutionHistory
    ):
        self.wm = working_memory
        self.pm = project_memory
        self.eh = execution_history

    def get_task_context(
        self,
        task_id: str,
        max_chars: int = 6000
    ) -> str:
        """
        Assemble relevant context for an agent working on a specific task node.
        """
        task = self.wm.tasks.get(task_id)
        if not task:
            return ""

        sections = []

        # 1. Goal & Active Task
        sections.append("## HIGH-LEVEL GOAL:")
        sections.append(self.wm.goal)
        sections.append(f"\n## ACTIVE TASK [{task.id}]: {task.title}")
        if task.description:
            sections.append(f"Description: {task.description}")
        if task.dependencies:
            sections.append(f"Dependencies: {', '.join(task.dependencies)}")

        # 2. Dependency Outputs
        dep_outputs = []
        for dep_id in task.dependencies:
            dep_task = self.wm.tasks.get(dep_id)
            if dep_task and dep_task.outputs:
                dep_outputs.append(f"From Task [{dep_id}] ({dep_task.title}):\n{dep_task.outputs}")
        if dep_outputs:
            sections.append("\n## OUTPUTS FROM COMPLETED DEPENDENCY TASKS:")
            sections.append("\n".join(dep_outputs))

        # 3. Project Memory (Conventions & Decisions)
        pm_summary = self.pm.get_summary_context()
        if pm_summary and "No project memory" not in pm_summary:
            sections.append("\n## PROJECT CONVENTIONS & ARCHITECTURE:")
            sections.append(pm_summary)

        # 4. Recent Execution Traces & Errors
        recent_traces = self.eh.get_summary_context(limit=4)
        if recent_traces:
            sections.append("\n## EXECUTION HISTORY:")
            sections.append(recent_traces)

        full_context = "\n".join(sections)
        if len(full_context) > max_chars:
            # Bound context to preserve prompt budget
            return full_context[:max_chars] + "\n... [context truncated to stay within token budget]"
        return full_context
