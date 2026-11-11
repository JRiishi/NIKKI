# NIKKI Module & Codebase Guide

This document is a comprehensive technical reference for engineers working on or extending the NIKKI codebase.

---

## 1. Directory Tree & Overview

```text
NIKKI/
├── cli.py                     # Primary user entry point: Rich terminal REPL & one-shot CLI
├── pytest.ini                 # Pytest configuration (excludes benchmarks, sets rootdir)
├── requirements.txt           # Python package dependencies
├── .env / .env.example        # Environment variable overrides
├── config/
│   ├── __init__.py
│   └── settings.py            # Global configuration, VRAM constraints, paths, model keys
├── src/
│   ├── adapters/
│   │   ├── base.py            # Abstract BaseAdapter interface
│   │   ├── ollama_adapter.py  # Local Ollama REST client & auto-daemon runner
│   │   └── laya_adapter.py    # Local PyTorch CUDA FP16 Laya Decision Agent adapter
│   ├── gateway/
│   │   ├── interactive_session.py # Qwen 9B discovery chat & approval gating
│   │   └── request_gateway.py     # Prompt validation, sanitization & categorization
│   ├── memory/
│   │   ├── state_db.py        # SQLite schema, composite PKs, transaction helpers
│   │   ├── working_memory.py  # In-memory DAG state machine (TaskNode lifecycle)
│   │   ├── project_memory.py  # Workspace file tree scanner & SHA-256 hash tracker
│   │   ├── execution_history.py# Tool execution logging & trace retrieval
│   │   └── retriever.py       # Bounded context window assembler
│   ├── orchestrator/
│   │   └── orchestrator.py    # Master lifecycle coordinator & execution loop FSM
│   ├── planner/
│   │   └── smart_planner.py   # Qwen 9B DAG task planner
│   ├── router/
│   │   └── laya_engine.py     # Laya neural decision engine for worker selection
│   ├── service/
│   │   └── model_service.py   # Central model service & VRAM safety coordinator
│   ├── tools/
│   │   ├── base.py            # BaseTool, ToolResult, PermissionTier definitions
│   │   ├── registry.py        # Central tool registry & PermissionGate
│   │   ├── file_tools.py      # ReadFileTool, WriteFileTool, PatchFileTool, ListDirTool
│   │   ├── terminal_tools.py  # RunCommandTool (cross-platform Windows/POSIX)
│   │   ├── test_tools.py      # RunTestsTool, RunLintTool (AST syntax check)
│   │   ├── git_tools.py       # GitStatusTool, GitDiffTool
│   │   └── code_search_tools.py # RegexSearchTool, SymbolSearchTool
│   ├── verifier/
│   │   └── verification_layer.py # Two-tier AST + Qwen 9B code reviewer
│   └── workers/
│       ├── base.py            # BaseWorker, WorkerResult definitions
│       ├── deterministic_worker.py # Zero-LLM worker for mechanical operations
│       ├── fast_worker.py     # Qwen 2B worker for quick transforms & edits
│       └── coder_worker.py    # Qwen 9B multi-turn ReAct coding agent
├── tests/                     # 18 Unit and Integration Tests
│   ├── test_config_and_service.py
│   ├── test_database_and_memory.py
│   ├── test_end_to_end_agent.py
│   ├── test_interactive_session.py
│   ├── test_routing_and_planner.py
│   ├── test_tools_and_permissions.py
│   └── test_workers_and_verification.py
└── docs/                      # Technical Documentation
    ├── ARCHITECTURE.md
    ├── DATA_FLOW.md
    ├── MODULE_GUIDE.md
    ├── DECISIONS.md
    └── CHANGELOG.md
```

---

## 2. Key Modules, Classes & Methods

### `config/settings.py`
- **`AgentSettings`**: Pydantic BaseSettings loading environment variables.
  - `OLLAMA_BASE_URL`: Default `http://127.0.0.1:11434`.
  - `LAYA_MODEL_PATH`: Default `D:\AI_Models\Laya\typed-decisions`.
  - `PRIMARY_MODEL`: `qwen3.5:9b`.
  - `LIGHTWEIGHT_MODEL`: `qwen3.5:2b`.
  - `MAX_TOTAL_VRAM_GB`: `14.5` (safety headroom below 16GB physical VRAM).

### `src/service/model_service.py`
- **`LocalModelService`**: Singleton manager coordinating model inference.
  - `generate_text(model_key, prompt, system, temperature)`: Calls Ollama generation endpoint.
  - `chat(model_key, messages, temperature)`: Calls Ollama chat endpoint with conversational history.
  - `laya_decide(context, choices, criteria)`: Invokes Laya PyTorch CUDA model and returns `(best_choice, confidence, decision_time_ms)`.
  - `get_vram_usage()`: Queries `torch.cuda.memory_allocated()` to prevent VRAM overflow.

### `src/gateway/interactive_session.py`
- **`InteractiveSession`**: Manages developer discovery before code generation.
  - `handle_message(user_text) -> (reply, approved_goal)`: Returns `approved_goal` only when the user explicitly approves an actual blueprint. Prevents premature approval while asking clarifications.
  - `record_execution_result(...)`: Injects real pipeline completion stats into the chat context so Qwen can answer questions about the run.

### `src/planner/smart_planner.py`
- **`SmartPlanner`**: Generates a dependency DAG of engineering subtasks.
  - `create_plan(goal, project_context, category) -> List[TaskNode]`: Prompts Qwen 9B to return a JSON array of subtasks with unique IDs and explicit dependency links.

### `src/router/laya_engine.py`
- **`LayaRouterEngine`**: 100% Neural routing layer using Convai Laya.
  - `route_task(task: TaskNode) -> Dict[str, Any]`: Evaluates task title and description against semantic criteria for `deterministic_worker`, `fast_worker_2b`, and `coder_worker_9b`. Zero Python keyword shortcuts.
  - Confidence thresholding: If confidence is below 0.35 on `fast_worker_2b`, escalates to `coder_worker_9b`.

### `src/workers/`
- **`DeterministicWorker`** (`deterministic_worker.py`): Zero-LLM execution. Matches mechanical tasks: test suites (`run_tests`), AST linting (`run_lint`), and git status (`git_status`). If no handler matches, fails cleanly so the orchestrator escalates.
- **`FastWorker`** (`fast_worker.py`): Lightweight Qwen 2B (~128 tok/s) worker for simple summaries or formatting.
- **`CoderWorker`** (`coder_worker.py`): Senior Autonomous Coding Engineer powered by Qwen 9B. Multi-turn ReAct loop (up to 8 iterations). Emits JSON tool calls (`call_tool`) and marks completion (`finish`).

### `src/verifier/verification_layer.py`
- **`VerificationLayer`**:
  - `verify_execution(goal, task_summary, acceptance_criteria, test_target) -> VerificationReport`:
    1. Deterministic tier: Runs AST linter or unit tests if available.
    2. Gathers created project files (recursing into untracked directories like `tik_tak_toe/` and checking filenames mentioned in the goal).
    3. Prompts Qwen 9B with `REVIEWER_SYSTEM_PROMPT` to emit a JSON review (`passed`, `score`, `feedback`, `suggested_fix`).

### `src/orchestrator/orchestrator.py`
- **`AgentOrchestrator`**: Master Finite State Machine (FSM).
  - Coordinates `RequestGateway` → `SmartPlanner` → `LayaRouterEngine` → `Worker Pool` → `VerificationLayer`.
  - Manages worker retry escalation: if a task fails on a non-coder worker, retry 1 escalates directly to `coder_worker_9b`.

---

## 3. How to Implement Future Features

### How to Add a New Tool
1. Create a new subclass of `BaseTool` in `src/tools/` (e.g., `src/tools/docker_tools.py`):
   ```python
   from src.tools.base import BaseTool, ToolResult, PermissionTier

   class DockerBuildTool(BaseTool):
       name = "docker_build"
       description = "Build a local Docker image."
       permission_tier = PermissionTier.WORKSPACE_WRITE

       def get_schema(self):
           return {
               "type": "object",
               "properties": {"tag": {"type": "string"}},
               "required": ["tag"]
           }

       def execute(self, tag: str, **kwargs) -> ToolResult:
           # implementation ...
           return ToolResult(success=True, output=f"Built {tag}")
   ```
2. Register the tool in `src/tools/registry.py` under `ToolRegistry._register_default_tools()`:
   ```python
   self.register(DockerBuildTool())
   ```
3. Add the tool signature to `CODER_SYSTEM_PROMPT` in `src/workers/coder_worker.py`.

### How to Add a New Specialized Worker
1. Subclass `BaseWorker` in `src/workers/` (e.g., `SecurityWorker`):
   ```python
   class SecurityAuditWorker(BaseWorker):
       def execute(self, task: TaskNode, context: str) -> WorkerResult:
           # specialized audit logic ...
   ```
2. Add worker to the pool in `src/orchestrator/orchestrator.py`:
   ```python
   workers["security_audit_worker"] = SecurityAuditWorker(tools, self.service)
   ```
3. Update `LayaRouterEngine.CHOICE_CRITERIA` in `src/router/laya_engine.py` with semantic criteria for the new worker.

### How to Integrate a Vector Database / Long-Term Memory
1. Create an adapter in `src/memory/vector_memory.py` (e.g., using `sqlite-vec` or `lancedb`).
2. Integrate vector search in `ContextRetriever.get_task_context()` in `src/memory/retriever.py` to pull top-$k$ code embeddings alongside the existing SQLite project summary.
