import uuid
from typing import Dict, Any, List, Optional
from src.memory.state_db import StateDatabase

class TaskNode:
    def __init__(
        self,
        id: str,
        title: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        assigned_to: str = "unassigned",
        status: str = "PENDING",
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.id = id
        self.title = title
        self.description = description
        self.dependencies = dependencies or []
        self.assigned_to = assigned_to
        self.status = status
        self.inputs = inputs or {}
        self.outputs = outputs or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "dependencies": self.dependencies,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "error": self.error
        }

class WorkingMemory:
    """
    In-memory representation of the active session state, current goal,
    DAG of subtasks, active worker assignments, and inter-agent messages.
    Syncs changes to StateDatabase.
    """

    def __init__(self, db: StateDatabase, session_id: Optional[str] = None):
        self.db = db
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.goal: str = ""
        self.tasks: Dict[str, TaskNode] = {}
        self.active_task_id: Optional[str] = None

    def initialize_session(self, goal: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.goal = goal
        self.db.create_session(self.session_id, goal, metadata)

    def load_existing_session(self, session_id: str) -> bool:
        session = self.db.get_session(session_id)
        if not session:
            return False
        self.session_id = session_id
        self.goal = session["goal"]
        raw_tasks = self.db.get_tasks_for_session(session_id)
        self.tasks.clear()
        for t in raw_tasks:
            node = TaskNode(
                id=t["id"],
                title=t["title"],
                description=t.get("description", ""),
                dependencies=t.get("dependencies", []),
                assigned_to=t.get("assigned_to", "unassigned"),
                status=t.get("status", "PENDING"),
                inputs=t.get("inputs", {}),
                outputs=t.get("outputs", {}),
                error=t.get("error")
            )
            self.tasks[node.id] = node
        return True

    def set_task_graph(self, task_nodes: List[TaskNode]) -> None:
        self.tasks.clear()
        for node in task_nodes:
            self.tasks[node.id] = node
            self.db.add_task(
                task_id=node.id,
                session_id=self.session_id,
                title=node.title,
                description=node.description,
                dependencies=node.dependencies,
                assigned_to=node.assigned_to,
                status=node.status,
                inputs=node.inputs
            )

    def get_next_runnable_task(self) -> Optional[TaskNode]:
        """Find the next task whose dependencies have all COMPLETED."""
        completed_ids = {t.id for t in self.tasks.values() if t.status == "COMPLETED"}
        for task in self.tasks.values():
            if task.status == "PENDING":
                if all(dep in completed_ids for dep in task.dependencies):
                    return task
        return None

    def update_task_status(
        self,
        task_id: str,
        status: str,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = status
            if outputs:
                task.outputs.update(outputs)
            if error:
                task.error = error
            self.db.update_task_status(task_id, status, task.outputs, task.error)

    def send_agent_message(self, sender: str, receiver: str, message_type: str, content: str) -> None:
        self.db.log_message(self.session_id, sender, receiver, message_type, content)

    def get_agent_messages(self) -> List[Dict[str, Any]]:
        return self.db.get_messages(self.session_id)

    def is_goal_complete(self) -> bool:
        if not self.tasks:
            return False
        return all(t.status == "COMPLETED" for t in self.tasks.values())

    def has_fatal_failures(self) -> bool:
        return any(t.status == "FAILED" for t in self.tasks.values())

    def get_summary_context(self) -> str:
        lines = [f"Goal: {self.goal}", "Tasks:"]
        for t in self.tasks.values():
            lines.append(f" - [{t.status}] {t.id}: {t.title} (Assigned: {t.assigned_to})")
        return "\n".join(lines)
