# Niiki: Autonomous AI Coding Agent

Niiki is an autonomous, fully local, offline AI software engineering agent powered by Alibaba's **Qwen 3.5** (`qwen3.5:9b`, `qwen3.5:2b`) and Convai's **Laya** (`laya-typed-decisions`). It is engineered to plan, execute, tool-call, verify, and self-correct software engineering workflows on an NVIDIA RTX 5060 Ti GPU with 100% data privacy and zero cloud dependencies.

---

## Architecture Overview

```
                           DEVELOPER / CLI / IDE
                                     │
                                     ▼
                              REQUEST GATEWAY
                   (Input validation, session management)
                                     │
                                     ▼
                             AGENT ORCHESTRATOR
                   (Goal loop, state machine, execution tracing)
                                     │
                                     ▼
                            SMART PLANNER — QWEN 9B
                   (Decomposes objectives into dependency DAGs)
                                     │
                                     ▼
                                LAYA ENGINE
                   (Fast ~29ms System 1 triage & worker routing)
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
 DETERMINISTIC WORKER            FAST WORKER                CODER WORKER
   (Zero-LLM execution)          (Qwen 3.5 2B)             (Qwen 3.5 9B)
 Tests, Git, AST, Syntax     Fast JSON & extraction     Architecture & Code gen
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                                     ▼
                      TOOL REGISTRY & PERMISSION GATE
                       (READ_ONLY / WRITE / SYSTEM)
                                     │
                                     ▼
                             LOCAL EXECUTION
                File read/write/patch │ Terminal │ Tests │ Git
                                     │
                                     ▼
                            VERIFICATION LAYER
                 Tier 1: Deterministic AST & Unit Tests
                 Tier 2: Qwen 9B Semantic Review & Diff Analysis
                                     │
                                     ▼
                              COMPLETION CHECK
                                ╱         ╲
                              FAIL        PASS
                               │            │
                         Retry/Replan   Final Result
                               │            │
                               └────────────┴──► ORCHESTRATOR
```

---

## Key Subsystems

### 1. Request Gateway (`src/gateway/`)
- Sanitizes user input and validates non-empty payloads.
- Maintains multi-session isolation using UUID4 session identifiers.
- Classifies user intent (coding, debugging, testing, question, refactor) before orchestration.

### 2. Smart Planner (`src/planner/`)
- Powered by `qwen3.5:9b` (Q4_K_M).
- Decomposes high-level software goals into a directed acyclic graph (DAG) of atomic subtasks.
- Identifies task dependencies, assigns tool categories, and generates strict acceptance criteria.
- Features automatic JSON schema repair and fallback DAG creation.

### 3. Laya System 1 Decision Engine (`src/router/`)
- Powered by `convaiinnovations/laya-typed-decisions` (~850 MB, ModernBERT-large backbone on `cuda:0`).
- Executes non-autoregressive decision inference in **~29 ms**.
- Routes subtasks to the most efficient worker:
  - `deterministic`: git actions, running test suites, checking syntax, reading raw files (zero LLM overhead).
  - `fast_worker`: fast extraction, simple classification, short schemas.
  - `coder_worker`: code synthesis, multi-turn reasoning, architecture refactoring.
- Enforces confidence gating: if confidence is below 0.60, falls back safely to Qwen 9B.

### 4. Specialized Workers (`src/workers/`)
- **DeterministicWorker**: Directly invokes local tools without consuming LLM tokens. Provides 100x speedup for mechanical tasks.
- **FastWorker**: Leverages `qwen3.5:2b` for lightweight language operations and parameter structuring.
- **CoderWorker**: Leverages `qwen3.5:9b` with an autonomous ReAct tool-calling loop. Observes tool execution outputs, diagnoses traceback errors, and iteratively fixes code.

### 5. Tool Registry & Permission Gate (`src/tools/`)
- Multi-tier permission model:
  - `READ_ONLY`: File reading, directory listing, regex search, AST symbol search.
  - `WORKSPACE_WRITE`: File writing, atomic line patching.
  - `SYSTEM_EXEC`: Subprocess execution, test runner, git operations.
- Path isolation prevents traversal outside the project workspace.
- Blocks dangerous destructive commands (`rmdir /s /q C:\`, `del /f /s /q *`, `format`).

### 6. Two-Tier Verification Layer (`src/verifier/`)
- **Tier 1 (Deterministic)**: AST syntax validation across all modified files, followed by automated test execution. Fails immediately if syntax is broken or tests fail.
- **Tier 2 (Semantic)**: Uses `qwen3.5:9b` to inspect git diffs against acceptance criteria, ensuring no hallucinated or partial implementations pass through.

### 7. Shared Persistent Memory (`src/memory/`)
- Backed by an offline SQLite database (`.agent_state.db`) using composite primary keys `(session_id, id)` to prevent constraint collisions.
- **Working Memory**: Tracks current goals, subtasks, DAG execution states, and agent messages.
- **Project Memory**: Stores project architecture, conventions, and file summaries with **SHA-256 staleness detection** to automatically re-index modified files.
- **Execution History**: Immutable audit log of every tool call, arguments, exit codes, and durations.
- **Context Retriever**: Retrieves pertinent history and architectural context for planner and workers.

---

## Hardware Specifications & VRAM Budget

Tested and verified on host system:
- **GPU**: NVIDIA GeForce RTX 5060 Ti (16 GB GDDR6/GDDR7 VRAM, Blackwell architecture, Driver 617.14, CUDA 13.4).
- **CPU**: Intel Core i7-14700K (20 cores, 28 threads).
- **RAM**: 32 GB DDR5.
- **Model Storage**: Dedicated fixed drive `D:\AI_Models`.

### Co-Residency VRAM Allocation
| Model | Parameters | Precision / Quant | VRAM Footprint | Location |
|---|---|---|---|---|
| `qwen3.5:9b` | 9 Billion | Q4_K_M (Ollama) | ~5.3 GB | Ollama (`D:\AI_Models\Ollama`) |
| `qwen3.5:2b` | 2 Billion | Q4_K_M (Ollama) | ~2.1 GB | Ollama (`D:\AI_Models\Ollama`) |
| `laya` | 421 Million | FP16 (PyTorch CUDA) | ~1.6 GB | PyTorch (`D:\AI_Models\Laya`) |
| **Total Co-Residency** | — | — | **~9.0 GB** | **Leaves ~7.0 GB VRAM free** |

---

## Getting Started

### 1. Prerequisites
Ensure Ollama is running and configured to use the local models on drive `D:`:
```powershell
$env:OLLAMA_MODELS = "D:\AI_Models\Ollama"
ollama serve
```

### 2. Environment Setup
The `.env` file enforces completely offline execution:
```ini
OFFLINE_MODE=true
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_DATASETS_OFFLINE=1
OLLAMA_BASE_URL=http://127.0.0.1:11434
MODEL_STORAGE_DIR=D:\AI_Models
QWEN_PRIMARY_MODEL=qwen3.5:9b
QWEN_FAST_MODEL=qwen3.5:2b
LAYA_MODEL_PATH=D:\AI_Models\Laya\typed-decisions
```

### 3. Check System Health
Run the diagnostic dashboard to verify all models and GPU acceleration:
```powershell
python cli.py --health
```

### 4. Run an Autonomous Goal
You can provide tasks directly to the CLI or enter interactive mode:

```powershell
# Single goal execution
python cli.py "Create a function in src/math_utils.py that calculates fibonacci numbers and verify it with a unit test."

# Interactive mode
python cli.py
```

### 5. Running the Test Suite
Niiki features a comprehensive test suite covering all layers:
```powershell
$env:PYTHONPATH = "."
python -m unittest discover tests
```

Tests include:
- `tests/test_offline_and_adapters.py`: Validates offline constraints, Ollama connection, and Laya inference.
- `tests/test_memory.py`: Tests SQLite persistence, composite keys, SHA-256 staleness, and context retrieval.
- `tests/test_tools.py`: Validates PermissionGate tiers, file editing, AST linting, test runners, and regex search.
- `tests/test_routing_and_planner.py`: Tests Laya System 1 routing, confidence gating, and Qwen 9B DAG planning.
- `tests/test_end_to_end_agent.py`: Full autonomous execution cycle (planning -> routing -> tool execution -> verification -> completion).

---

## Architectural Rules Enforced
1. **Orchestrator owns the lifecycle**: State transitions are strictly controlled via FSM.
2. **Planner decides WHAT**: Qwen 9B generates explicit DAG subtasks with acceptance criteria.
3. **Laya decides WHICH**: Laya routes tasks in ~29 ms based on task semantics and tool affinity.
4. **Deterministic offload**: Never invoke an LLM when deterministic code can do the job (git, AST, test running).
5. **Gated execution**: Every tool call is screened for security, path containment, and argument validity.
6. **Unified shared memory**: All workers read and write to the centralized SQLite state engine.
7. **Two-tier verification**: No task is marked complete without syntax checks, test passing, and semantic diff review.
8. **Controlled retries**: Verification failures trigger targeted worker retry loops or replanning.
