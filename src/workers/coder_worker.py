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
5. Use standard imports compatible with direct script execution (e.g. 'from board import Board' or 'import sys, os; sys.path.insert(0, ...)') rather than relative package imports ('from .board import ...') so files can be run directly with python.
6. Once changes are made, respond with "action": "finish".
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
                # Do not abort immediately; feed parse error back to model so it can fix JSON
                conversation_history.append(
                    f"Action taken: Invalid format\n"
                    f"Observation: Your response could not be parsed as valid JSON. "
                    f"Please respond with strictly valid JSON matching the schema, escaping quotes inside content."
                )
                final_summary = raw_response
                continue

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

        if tool_calls_count == 0:
            return WorkerResult(
                success=False,
                error=f"CoderWorker completed {self.max_iterations} iterations without executing any tool calls.",
                tool_calls_made=0,
                worker_name=self.name
            )

        return WorkerResult(
            success=True,
            output={"summary": final_summary or "Iteration limit reached.", "iterations": self.max_iterations},
            tool_calls_made=tool_calls_count,
            worker_name=self.name
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        # Match ```json ... ``` or first { ... }
        match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text)
        candidate = match.group(1) if match else None
        if not candidate:
            m = re.search(r"(\{[\s\S]*\})", text)
            if m:
                candidate = m.group(1)

        if not candidate:
            return None

        # Pass 1: standard json.loads with strict=False
        try:
            return json.loads(candidate, strict=False)
        except Exception:
            pass

        # Pass 2: repair common raw unescaped newlines inside strings
        try:
            cleaned = re.sub(r'[\r\n]+', r'\\n', candidate)
            return json.loads(cleaned, strict=False)
        except Exception:
            pass

        # Pass 3: Regex fallback specifically for write_file tool call
        if '"tool_name"' in candidate and '"write_file"' in candidate:
            path_m = re.search(r'"path"\s*:\s*"([^"]+)"', candidate)
            content_m = re.search(r'"content"\s*:\s*"(.*)"\s*\}', candidate, re.DOTALL)
            if path_m and content_m:
                raw_c = content_m.group(1)
                try:
                    clean_c = raw_c.encode().decode('unicode_escape', errors='replace')
                except Exception:
                    clean_c = raw_c
                return {
                    "action": "call_tool",
                    "tool_name": "write_file",
                    "arguments": {
                        "path": path_m.group(1),
                        "content": clean_c
                    }
                }

        return None
