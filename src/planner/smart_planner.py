import json
import re
from typing import Dict, Any, List, Optional
from src.service.model_service import LocalModelService
from src.memory.working_memory import TaskNode

PLANNER_SYSTEM_PROMPT = """You are the Senior Software Architecture Planner for an Autonomous Coding Agent.
Given a developer's objective and codebase context, decompose the goal into a minimal, logical Directed Acyclic Graph (DAG) of actionable engineering tasks.

RULES:
1. Keep the number of tasks focused and minimal (typically 2 to 5 tasks).
2. Each task must specify:
   - id: short identifier (e.g. "task_1", "task_2")
   - title: clear, imperative action phrase
   - description: exact work to be done and expected deliverables
   - dependencies: list of task IDs that must complete before this task can start
   - acceptance_criteria: how to verify this task succeeded
3. Return ONLY a valid JSON object matching this schema:
{
  "tasks": [
    {
      "id": "task_1",
      "title": "Analyze existing code",
      "description": "Locate relevant files and inspect data structures.",
      "dependencies": [],
      "acceptance_criteria": "Key files and variables identified."
    },
    {
      "id": "task_2",
      "title": "Implement core logic",
      "description": "Write or patch the target module.",
      "dependencies": ["task_1"],
      "acceptance_criteria": "Module compiles with no syntax errors."
    }
  ]
}
Do not include any conversational filler outside the JSON object.
"""

class SmartPlanner:
    """
    Decomposes user objectives into structured Task DAGs using Qwen 3.5 9B.
    Includes deterministic fallback extraction for reliable execution.
    """

    def __init__(self, model_service: LocalModelService):
        self.service = model_service

    def create_plan(
        self,
        goal: str,
        project_context: str = "",
        category: str = "general"
    ) -> List[TaskNode]:
        prompt = f"""Developer Objective:
{goal}

Category: {category}

Project Context:
{project_context or 'No prior project memory.'}

Decompose this into a minimal task DAG now."""

        response = self.service.generate_text(
            model_key="qwen_primary",
            prompt=prompt,
            system=PLANNER_SYSTEM_PROMPT,
            temperature=0.1
        )

        raw_text = response.get("response", "")
        tasks = self._parse_tasks(raw_text, goal)
        return tasks

    def _parse_tasks(self, text: str, goal: str) -> List[TaskNode]:
        """Robustly extract and validate task nodes from LLM output."""
        # 1. Try direct JSON parsing or regex extraction
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                raw_tasks = data.get("tasks", [])
                if raw_tasks:
                    nodes = []
                    for t in raw_tasks:
                        nodes.append(TaskNode(
                            id=t.get("id", f"task_{len(nodes)+1}"),
                            title=t.get("title", "Engineering subtask"),
                            description=t.get("description", ""),
                            dependencies=t.get("dependencies", []),
                            inputs={"criteria": t.get("acceptance_criteria", "")}
                        ))
                    return nodes
            except Exception:
                pass

        # 2. Deterministic Fallback DAG
        return [
            TaskNode(
                id="task_1",
                title="Inspect codebase and locate relevant files",
                description=f"Search workspace for files relevant to: {goal}",
                dependencies=[]
            ),
            TaskNode(
                id="task_2",
                title="Execute code modifications or solution",
                description=f"Implement required changes for: {goal}",
                dependencies=["task_1"]
            ),
            TaskNode(
                id="task_3",
                title="Verify and run tests",
                description="Run linting and tests to ensure no regressions.",
                dependencies=["task_2"]
            )
        ]

