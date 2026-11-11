# Niiki Changelog & Development Record

All notable changes, fixes, refactorings, and test records for the Niiki project.

---

## [1.0.0] - 2026-11-11

### Features Implemented
- **100% Offline Local Inference:** Configured Ollama with `qwen3.5:9b` (Q4_K_M) and `qwen3.5:2b` (Q8_0) on `D:\AI_Models\Ollama`, and Convai Laya on `D:\AI_Models\Laya\typed-decisions` on `cuda:0`.
- **System 1 Neural Router (Laya Engine):** Replaced all Python keyword heuristics with 100% neural decision embeddings evaluated in ~29ms latency.
- **Interactive Discovery Studio (CLI REPL):** Implemented `InteractiveSession` with multi-turn requirements discussion, architectural consensus, structured `PROJECT BLUEPRINT` proposals, and one-approval execution gate.
- **Autonomous Lifecycle Orchestrator:** Implemented `AgentOrchestrator` managing the FSM DAG lifecycle, task execution, tool dispatch, memory updates, retry escalation, and two-tier verification.
- **Two-Tier Verification Gate:** Implemented deterministic AST linting and unit test execution (Tier 1) alongside cognitive semantic code review via Qwen 9B (Tier 2).
- **Persistent ACID SQLite Memory:** Unified `WorkingMemory`, `ProjectMemory`, `ExecutionHistory`, and `ContextRetriever` backed by `.agent_state.db`.
- **Automatic Headless Daemon Management:** Added `ensure_ollama_running()` to automatically resurrect the background Ollama daemon process if stopped.
- **Cross-Platform Tool Suite:** Enhanced `RunCommandTool` to natively handle Windows directory creation (`mkdir` / `mkdir -p`) via `os.makedirs`, and updated `GitDiffTool` pathspec quoting for Windows.

---

### Files Created, Modified, and Deleted

#### Created
- `config/settings.py` — Application configuration, VRAM limits, and model specifications.
- `src/adapters/base.py` — Base adapter interface.
- `src/adapters/ollama_adapter.py` — Ollama REST client with automatic headless daemon startup.
- `src/adapters/laya_adapter.py` — PyTorch CUDA Laya typed-decisions adapter.
- `src/service/model_service.py` — Central model manager and VRAM monitor.
- `src/memory/state_db.py` — SQLite backing store with composite PKs and upsert support.
- `src/memory/working_memory.py` — Task DAG state machine.
- `src/memory/project_memory.py` — Workspace file tree scanner with SHA-256 staleness tracking.
- `src/memory/execution_history.py` — Tool execution tracing and audit logging.
- `src/memory/retriever.py` — Context window assembler for subtasks.
- `src/gateway/request_gateway.py` — Prompt validation, sanitization, and category inference.
- `src/gateway/interactive_session.py` — Discovery REPL assistant with approval gating.
- `src/planner/smart_planner.py` — Qwen 9B DAG task planner.
- `src/router/laya_engine.py` — Convai Laya neural decision engine.
- `src/workers/base.py` — Worker base class and result schema.
- `src/workers/deterministic_worker.py` — Zero-LLM deterministic worker (Ponytail Principle).
- `src/workers/fast_worker.py` — Lightweight Qwen 2B worker.
- `src/workers/coder_worker.py` — Qwen 9B ReAct coding worker with tool-calling protocol.
- `src/verifier/verification_layer.py` — Two-tier verification gate with targeted diff isolation.
- `src/tools/base.py`, `registry.py`, `file_tools.py`, `terminal_tools.py`, `test_tools.py`, `git_tools.py`, `code_search_tools.py` — Tool suite and permission gate.
- `cli.py` — Interactive discovery REPL and autonomous one-shot CLI.
- `tests/` — 18 unit and integration tests.
- `docs/ARCHITECTURE.md` — Full system architecture documentation.
- `docs/DATA_FLOW.md` — End-to-end data flow and sequence diagrams.
- `docs/MODULE_GUIDE.md` — Comprehensive module and file guide.
- `docs/DECISIONS.md` — Architectural Decision Records (ADRs) and tradeoffs.
- `docs/CHANGELOG.md` — Change log and test verification records.

#### Modified
- `src/orchestrator/orchestrator.py` — Added worker escalation preservation on retries (`task.assigned_to = "coder_worker_9b"`).
- `src/verifier/verification_layer.py` — Replaced recursive workspace file dump with targeted project file discovery (handling untracked directories and filenames in goal).
- `src/gateway/interactive_session.py` — Standardized approval reply to `"✓ Plan approved!..."` and prevented premature blueprint triggering while asking clarifying questions.
- `src/tools/git_tools.py` — Fixed Windows pathspec quoting in `git diff`.
- `src/tools/terminal_tools.py` — Added cross-platform `mkdir` / `mkdir -p` interception.
- `src/workers/coder_worker.py` — Increased `max_iterations` to 8 and enhanced system prompt instructions regarding directory creation.
- `cli.py` — Fixed `AttributeError: 'OrchestrationResult' object has no attribute 'total_tasks'` by summing `tasks_completed + tasks_failed`.
- `.gitignore` — Untracked `.vscode/` and temporary test files.

#### Deleted / Cleaned Up
- Removed stray `tictactoe/` folder created in root during early pipeline iterations.
- Untracked stray `.pyc` and `__pycache__` artifacts from git index.

---

### Dependencies Introduced
- `pydantic>=2.0.0` — Strict data validation and schema serialization.
- `requests>=2.31.0` — HTTP communication with local Ollama daemon.
- `torch>=2.4.0` — CUDA runtime for local Laya decision model.
- `transformers>=4.40.0` — Offline tokenizer and model weights loader.
- `laya>=0.1.0` — Typed-decisions model inference.
- `rich>=13.0.0` — Rich terminal rendering for CLI tables, panels, and syntax highlighting.
- `pytest>=7.4.0` — Local test runner.

---

### Test Suite Execution & Results

```text
Ran 18 tests in 224.302s

OK (18 passed, 0 failed)
```

| Test File | Test Case | Target Tested | Status |
|---|---|---|---|
| `test_config_and_service.py` | `test_01_settings_load` | Configuration loading & defaults | PASSED |
| `test_config_and_service.py` | `test_02_model_service_health` | Model health & Ollama ping | PASSED |
| `test_config_and_service.py` | `test_03_vram_limit_enforcement` | VRAM tracking & limits | PASSED |
| `test_database_and_memory.py` | `test_01_db_schema_and_session` | SQLite schema & session creation | PASSED |
| `test_database_and_memory.py` | `test_02_working_memory_dag` | Task DAG state machine & FSM | PASSED |
| `test_database_and_memory.py` | `test_03_project_memory_and_hashes` | File hashing & staleness | PASSED |
| `test_database_and_memory.py` | `test_04_execution_history_logging` | Tool execution audit logging | PASSED |
| `test_interactive_session.py` | `test_01_greeting_does_not_trigger_execution` | Greeting non-execution | PASSED |
| `test_interactive_session.py` | `test_02_approval_without_discussion_is_rejected` | Empty session approval rejection | PASSED |
| `test_interactive_session.py` | `test_03_discussion_and_approval_flow` | Conversational discovery & approval | PASSED |
| `test_routing_and_planner.py` | `test_01_smart_planner_dag_generation` | Qwen 9B DAG generation | PASSED |
| `test_routing_and_planner.py` | `test_02_laya_router_decision_on_test_task` | Laya routing on test tasks | PASSED |
| `test_routing_and_planner.py` | `test_03_laya_router_decision_head` | Laya criteria selection | PASSED |
| `test_tools_and_permissions.py` | `test_01_file_tools` | Read, write, patch, list tools | PASSED |
| `test_tools_and_permissions.py` | `test_02_permission_gate_tiers` | Safety tiers & permission modes | PASSED |
| `test_workers_and_verification.py`| `test_01_deterministic_worker_execution` | Zero-LLM deterministic execution | PASSED |
| `test_workers_and_verification.py`| `test_02_verification_layer_pipeline` | Two-tier verification pipeline | PASSED |
| `test_end_to_end_agent.py` | `test_01_orchestrator_execution_lifecycle` | End-to-end autonomous lifecycle | PASSED |
