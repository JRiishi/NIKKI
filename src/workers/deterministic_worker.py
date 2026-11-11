from typing import Dict, Any
from src.workers.base import BaseWorker, WorkerResult
from src.memory.working_memory import TaskNode
from src.tools.registry import ToolRegistry

class DeterministicWorker(BaseWorker):
    """
    Zero-LLM Worker (Ponytail Principle).
    Directly executes deterministic engineering operations without spending model inference cycles.
    Ideal for running test suites, static syntax validation, file enumeration, and git actions.
    """

    def __init__(self, tool_registry: ToolRegistry):
        super().__init__(name="deterministic_worker", tool_registry=tool_registry)

    def execute(self, task: TaskNode, context: str) -> WorkerResult:
        lower = (task.title + " " + task.description).lower()
        tool_calls = 0

        # Case 1: Run tests
        if "run test" in lower or "pytest" in lower or "unittest" in lower:
            tool_calls += 1
            res = self.tools.execute("run_tests", task_id=task.id)
            if res.success:
                return WorkerResult(success=True, output=res.output, tool_calls_made=tool_calls, worker_name=self.name)
            else:
                return WorkerResult(success=False, error=res.error or "Test run failed.", tool_calls_made=tool_calls, worker_name=self.name)

        # Case 2: Run syntax / lint check
        if "lint" in lower or "syntax" in lower or "ast" in lower:
            # find file target from inputs or description
            file_target = task.inputs.get("file_path") or "."
            tool_calls += 1
            res = self.tools.execute("run_lint", task_id=task.id, file_path=file_target)
            return WorkerResult(success=res.success, output=res.output, error=res.error, tool_calls_made=tool_calls, worker_name=self.name)

        # Case 3: Git Status / Diff
        if "git status" in lower or "git diff" in lower:
            tool_calls += 1
            res = self.tools.execute("git_status", task_id=task.id)
            return WorkerResult(success=res.success, output=res.output, error=res.error, tool_calls_made=tool_calls, worker_name=self.name)

        # Default fallback: file listing
        tool_calls += 1
        res = self.tools.execute("list_dir", task_id=task.id, path=".")
        return WorkerResult(success=res.success, output=res.output, error=res.error, tool_calls_made=tool_calls, worker_name=self.name)
