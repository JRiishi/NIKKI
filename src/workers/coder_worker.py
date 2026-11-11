import json
import re
from typing import Dict, Any, List, Optional
from src.workers.base import BaseWorker, WorkerResult
from src.memory.working_memory import TaskNode
from src.tools.registry import ToolRegistry
from src.service.model_service import LocalModelService

CODER_SYSTEM_PROMPT = """You are the Senior Autonomous Coding Engineer (powered by Qwen 3.5 9B).
You are tasked with executing an engineering subtask. You have access to local workspace tools.

To call a tool, respond with ONLY a JSON tool-call block matching this schema:
```json
{
  "action": "call_tool",
  "tool_name": "write_file",
  "arguments": {
    "path": "src/utils.py",
    "content": "def calculate_total(items):\\n    return sum(item.price for item in items)\\n"
  }
}
```

Or when the subtask is fully complete:
```json
{
  "action": "finish",
  "summary": "Implemented calculate_total function and verified syntax."
}
```

Available Tools:
- read_file(path, start_line, end_line)
- write_file(path, content)
- patch_file(path, target, replacement)
- list_dir(path, pattern)
- run_command(command, cwd)
- run_lint(file_path)
- regex_search(pattern, directory)
- symbol_search(file_path)

RULES:
1. Prefer modifying existing files with patch_file or write_file.
2. Ensure correct Python syntax.
3. write_file automatically creates all parent directories; you never need to run mkdir.
4. Write complete files directly to their target relative paths (e.g. "tik_tak_toe/app.py").
5. Once changes are made, respond with "action": "finish".
"""

class CoderWorker(BaseWorker):
    """
    Primary Generative Coding Agent powered by Qwen 3.5 9B (~63 tok/s).
    Performs multi-turn code synthesis, file inspection, diff patching, and debugging.
    """

    def __init__(self, tool_registry: ToolRegistry, model_service: LocalModelService, max_iterations: int = 8):
        super().__init__(name="coder_worker_9b", tool_registry=tool_registry)
        self.service = model_service
        self.max_iterations = max_iterations

    def execute(self, task: TaskNode, context: str) -> WorkerResult:
        conversation_history = [
            f"Goal & Task Context:\n{context}",
            f"Active Task [{task.id}]: {task.title}\nDescription: {task.description}\nAcceptance Criteria: {task.inputs.get('criteria', 'Working code with no syntax errors.')}"
        ]

        tool_calls_count = 0
        final_summary = ""

        for iteration in range(self.max_iterations):
            current_prompt = "\n\n".join(conversation_history) + "\n\nWhat is your next action? Respond with a JSON action block."

            resp = self.service.generate_text(
                model_key="qwen_primary",
                prompt=current_prompt,
                system=CODER_SYSTEM_PROMPT,
                temperature=0.2
            )
            raw_response = resp.get("response", "").strip()

            # Parse JSON action block
            action_data = self._extract_json(raw_response)
            if not action_data:
                # If no valid JSON, break and record output
                final_summary = raw_response
                break

            action = action_data.get("action")
            if action == "finish":
                final_summary = action_data.get("summary", "Task marked as completed by CoderWorker.")
                return WorkerResult(
                    success=True,
                    output={"summary": final_summary, "iterations": iteration + 1},
                    tool_calls_made=tool_calls_count,
                    worker_name=self.name
                )

            elif action == "call_tool":
                tool_name = action_data.get("tool_name")
                arguments = action_data.get("arguments", {})
                tool_calls_count += 1

                tool_res = self.tools.execute(tool_name, task_id=task.id, **arguments)
                tool_feedback = f"Tool [{tool_name}] result: Success={tool_res.success}\nOutput: {tool_res.output or tool_res.error}"
                conversation_history.append(f"Action taken: {json.dumps(action_data)}\nObservation: {tool_feedback}")

            else:
                conversation_history.append(f"Model output: {raw_response}")

        return WorkerResult(
            success=True,
            output={"summary": final_summary or "Iteration limit reached.", "iterations": self.max_iterations},
            tool_calls_made=tool_calls_count,
            worker_name=self.name
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        # Match ```json ... ``` or first { ... }
        match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return None
