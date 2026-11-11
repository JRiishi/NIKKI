import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from src.service.model_service import LocalModelService
from src.memory.state_db import StateDatabase
from src.memory.working_memory import WorkingMemory, TaskNode
from src.memory.project_memory import ProjectMemory
from src.memory.execution_history import ExecutionHistory
from src.memory.retriever import ContextRetriever
from src.tools.registry import ToolRegistry, PermissionGate, AutonomyMode
from src.gateway.request_gateway import RequestGateway, ValidatedRequest
from src.planner.smart_planner import SmartPlanner
from src.router.laya_engine import LayaRouterEngine
from src.workers.deterministic_worker import DeterministicWorker
from src.workers.fast_worker import FastWorker
from src.workers.coder_worker import CoderWorker
from src.verifier.verification_layer import VerificationLayer, VerificationReport

class OrchestrationResult(BaseModel):
    session_id: str
    goal: str
    status: str # COMPLETED, FAILED, REJECTED
    tasks_completed: int
    tasks_failed: int
    total_tool_calls: int
    verification: Optional[VerificationReport] = None
    final_response: str = ""
    elapsed_seconds: float = 0.0

class AgentOrchestrator:
    """
    Autonomous Software Engineering Agent Orchestrator.
    Owns the full execution lifecycle, task DAG state machine, model dispatch,
    memory synchronization, permission gating, and verification loops.
    """

    def __init__(
        self,
        model_service: Optional[LocalModelService] = None,
        db: Optional[StateDatabase] = None,
        autonomy_mode: str = AutonomyMode.FULL_AUTONOMOUS,
        max_task_retries: int = 2
    ):
        self.service = model_service or LocalModelService()
        self.db = db or StateDatabase()
        self.gateway = RequestGateway()
        self.planner = SmartPlanner(self.service)
        self.router = LayaRouterEngine(self.service)
        self.gate = PermissionGate(mode=autonomy_mode)
        self.max_retries = max_task_retries

    def run(self, user_request: str, session_id: Optional[str] = None) -> OrchestrationResult:
        t_start = time.perf_counter()

        # 1. Request Gateway: Validation & Sanitization
        validated: ValidatedRequest = self.gateway.validate_and_route(user_request, session_id=session_id)
        sid = validated.session_id

        # 2. Shared Memory Initialization
        wm = WorkingMemory(self.db, session_id=sid)
        wm.initialize_session(goal=validated.sanitized_prompt, metadata=validated.metadata)
        pm = ProjectMemory(self.db)
        eh = ExecutionHistory(self.db, session_id=sid)
        retriever = ContextRetriever(working_memory=wm, project_memory=pm, execution_history=eh)

        # 3. Tool Registry Setup
        tools = ToolRegistry(execution_history=eh, permission_gate=self.gate)

        # 4. Workers Pool
        workers = {
            "deterministic_worker": DeterministicWorker(tool_registry=tools),
            "fast_worker_2b": FastWorker(tool_registry=tools, model_service=self.service),
            "coder_worker_9b": CoderWorker(tool_registry=tools, model_service=self.service)
        }

        # 5. Smart Planner (Qwen 3.5 9B)
        project_context = pm.get_summary_context()
        task_nodes: List[TaskNode] = self.planner.create_plan(
            goal=validated.sanitized_prompt,
            project_context=project_context,
            category=validated.inferred_category
        )
        wm.set_task_graph(task_nodes)

        # 6. Execution Loop (FSM)
        total_tool_calls = 0
        task_retry_counts: Dict[str, int] = {}

        while True:
            task = wm.get_next_runnable_task()
            if not task:
                break

            wm.update_task_status(task.id, status="IN_PROGRESS")

            # Route task via Laya System 1 Decision Engine
            routing_decision = self.router.route_task(task)
            assigned_worker_key = routing_decision["assigned_to"]
            task.assigned_to = assigned_worker_key

            worker = workers.get(assigned_worker_key, workers["coder_worker_9b"])

            # Retrieve bounded task context
            task_context = retriever.get_task_context(task.id)

            # Worker Execution
            exec_result = worker.execute(task, task_context)
            total_tool_calls += exec_result.tool_calls_made

            if exec_result.success:
                wm.update_task_status(
                    task.id,
                    status="COMPLETED",
                    outputs={"result": exec_result.output, "worker": assigned_worker_key}
                )
            else:
                retries = task_retry_counts.get(task.id, 0)
                if retries < self.max_retries:
                    task_retry_counts[task.id] = retries + 1
                    wm.update_task_status(task.id, status="PENDING", error=exec_result.error)
                else:
                    wm.update_task_status(task.id, status="FAILED", error=exec_result.error)
                    break

        # 7. Verification Layer
        verifier = VerificationLayer(tool_registry=tools, model_service=self.service)
        completed_tasks = [t for t in wm.tasks.values() if t.status == "COMPLETED"]
        failed_tasks = [t for t in wm.tasks.values() if t.status == "FAILED"]

        task_summary = f"{len(completed_tasks)}/{len(wm.tasks)} tasks completed."
        verif_report = verifier.verify_execution(
            goal=validated.sanitized_prompt,
            task_summary=task_summary,
            acceptance_criteria="Working implementation satisfying user prompt."
        )

        overall_status = "COMPLETED" if (len(failed_tasks) == 0 and verif_report.passed) else "FAILED"
        self.db.update_session_status(sid, overall_status)

        elapsed = time.perf_counter() - t_start

        final_response = (
            f"### Execution Summary for Session [{sid}]\n"
            f"- **Status:** {overall_status}\n"
            f"- **Goal:** {validated.sanitized_prompt}\n"
            f"- **Tasks Completed:** {len(completed_tasks)}/{len(wm.tasks)}\n"
            f"- **Tool Invocations:** {total_tool_calls}\n"
            f"- **Verification Score:** {verif_report.review_score:.2f} ({'PASSED' if verif_report.passed else 'FAILED'})\n"
            f"- **Feedback:** {verif_report.feedback}\n"
            f"- **Execution Duration:** {elapsed:.2f}s\n"
        )

        return OrchestrationResult(
            session_id=sid,
            goal=validated.sanitized_prompt,
            status=overall_status,
            tasks_completed=len(completed_tasks),
            tasks_failed=len(failed_tasks),
            total_tool_calls=total_tool_calls,
            verification=verif_report,
            final_response=final_response,
            elapsed_seconds=round(elapsed, 2)
        )
