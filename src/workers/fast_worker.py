import json
import re
from typing import Dict, Any
from src.workers.base import BaseWorker, WorkerResult
from src.memory.working_memory import TaskNode
from src.tools.registry import ToolRegistry
from src.service.model_service import LocalModelService

FAST_WORKER_SYSTEM = """You are a high-speed Structured Data & Extraction Worker.
Your duty is to perform fast classification, information extraction, and JSON schema formatting.
Be concise, strictly factual, and output valid structured data."""

class FastWorker(BaseWorker):
    """
    Lightweight Generative Worker powered by Qwen 3.5 2B (~128 tok/s).
    Excels at fast structured extraction, JSON synthesis, and quick metadata analysis.
    """

    def __init__(self, tool_registry: ToolRegistry, model_service: LocalModelService):
        super().__init__(name="fast_worker_2b", tool_registry=tool_registry)
        self.service = model_service

    def execute(self, task: TaskNode, context: str) -> WorkerResult:
        prompt = f"""Task: {task.title}
Details: {task.description}

Context:
{context}

Execute this extraction / analysis task concisely."""

        try:
            resp = self.service.generate_text(
                model_key="qwen_lightweight",
                prompt=prompt,
                system=FAST_WORKER_SYSTEM,
                temperature=0.1
            )
            output_text = resp.get("response", "").strip()

            return WorkerResult(
                success=True,
                output={"summary": output_text, "tokens": resp.get("eval_tokens", 0)},
                tool_calls_made=0,
                worker_name=self.name
            )
        except Exception as e:
            return WorkerResult(
                success=False,
                error=str(e),
                worker_name=self.name
            )
