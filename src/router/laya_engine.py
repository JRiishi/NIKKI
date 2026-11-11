from typing import Dict, Any, Tuple
from src.service.model_service import LocalModelService
from src.memory.working_memory import TaskNode

class LayaRouterEngine:
    """
    Specialized System 1 Router powered by Convai Innovations Laya (typed-decisions).
    Evaluates each TaskNode in a single ~29ms forward pass to determine:
    1. Worker & Model Assignment (deterministic, Qwen 2B, Qwen 9B)
    2. Operational Risk Tier (safe, write, dangerous)
    3. Confidence Gating
    """

    def __init__(self, model_service: LocalModelService):
        self.service = model_service

    def route_task(self, task: TaskNode) -> Dict[str, Any]:
        """
        Evaluate task and assign worker, permission tier, and confidence rating
        purely through Laya System 1 Decision Head in a single fast GPU forward pass (~29ms).
        """
        state = f"Task: {task.title}\nDetails: {task.description}"
        questions = {
            "worker_assignment": {
                "type": "choice",
                "instructions": "Which worker engine is best suited for this task?",
                "criteria": {
                    "coder_worker_9b": "Writing code, creating files, implementing algorithms, scaffolding directories, modifying existing files",
                    "fast_worker_2b": "Lightweight text extraction, JSON formatting, simple classification, short summaries",
                    "deterministic_worker": "Executing test suites (running pytest/unittest), static syntax linting, git status or commit"
                }
            },
            "risk_assessment": {
                "type": "score",
                "instructions": "Assess the risk level of executing this task:",
                "criteria": ["Low: Read only", "Medium: Workspace write", "High: Execution of arbitrary commands"]
            },
            "confidence_check": {
                "type": "noul",
                "instructions": "Is the routing decision confident and straightforward?",
                "criteria": {"true": "High confidence", "false": "Ambiguous or needs escalation"}
            }
        }

        try:
            res = self.service.decide(state=state, questions=questions, model_key="laya_decision")
            answers = res.get("answers", {})

            worker_choice = answers.get("worker_assignment", {}).get("choice", "coder_worker_9b")
            worker_conf = answers.get("worker_assignment", {}).get("answer_confidence", 0.5)

            confidence_noul = answers.get("confidence_check", {}).get("noul", 0.5)

            # Confidence Gating: if Laya is uncertain, default to Coder 9B for safety
            if confidence_noul < 0.35 and worker_choice == "fast_worker_2b":
                worker_choice = "coder_worker_9b"

            risk_score = answers.get("risk_assessment", {}).get("score", 1.0)
            risk_tier = "SAFE_READ" if risk_score < 0.8 else ("WORKSPACE_WRITE" if risk_score < 1.8 else "DANGEROUS_SYSTEM")

            return {
                "assigned_to": worker_choice,
                "risk_tier": risk_tier,
                "confidence": round(worker_conf, 3),
                "latency_ms": res.get("latency_ms", 0.0),
                "reasoning": f"Laya single-pass decision (confidence: {worker_conf:.2f})"
            }

        except Exception as e:
            # Safe Fallback
            return {
                "assigned_to": "coder_worker_9b",
                "risk_tier": "WORKSPACE_WRITE",
                "confidence": 0.5,
                "reasoning": f"Router fallback due to exception: {e}"
            }
