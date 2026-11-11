# Architectural Decision Records (ADRs) & Technical Tradeoffs

This document details the core architectural decisions made in Niiki, the justification for each design choice, alternative approaches considered, and current technical debt or known limitations.

---

## 1. Architectural Decisions

### ADR-001: 100% Local Offline Inference (No External Cloud APIs)
- **Decision:** All inference must run locally on the user's workstation using NVIDIA CUDA (`cuda:0`) and local Ollama (`127.0.0.1:11434`). Under no circumstances may cloud APIs (OpenAI, Anthropic, Gemini, AWS) be invoked.
- **Rationale:** Complete privacy, zero data egress, deterministic offline reproducibility, and zero recurring token costs. Enables air-gapped development.
- **Alternatives Considered:** Hybrid routing with cloud LLM fallback. Rejected by strict architectural constraint.

---

### ADR-002: System 1 Neural Routing via Convai Laya (Zero Python Keyword Shortcuts)
- **Decision:** Every engineering subtask is routed to a worker exclusively through `convaiinnovations/laya` (typed-decisions FP16 on PyTorch CUDA). All Python string matching (`if "pytest" in title...`) was removed.
- **Rationale:** True autonomous agents should rely on semantic understanding of tasks rather than brittle, hardcoded keyword heuristics. Laya provides sub-30ms neural classification directly on GPU.
- **Tradeoff:** Laya confidence calibration has a slight offset on certain categories due to checkpoint temperature scaling (emitting ~0.45–0.57 confidence), which is handled via a low-confidence escalation fallback.

---

### ADR-003: The Ponytail Principle (Zero-LLM Deterministic Execution)
- **Decision:** Never invoke generative LLMs for mechanical, deterministic operations that standard software tools execute faster, cheaper, and with 100% precision.
- **Implementation:** `DeterministicWorker` runs `pytest`, `unittest`, Python AST syntax checks, and `git` queries directly without spending LLM tokens.
- **Benefit:** Saves GPU VRAM and eliminates hallucinated syntax errors or false-positive test outputs.

---

### ADR-004: Tiered Model Topology (Qwen 3.5 9B & Qwen 3.5 2B)
- **Decision:** Deploy a two-model tiered topology:
  1. `qwen3.5:9b` (Q4_K_M quantization, ~6.6GB VRAM): Complex multi-turn ReAct code synthesis, architectural DAG planning, and semantic verification.
  2. `qwen3.5:2b` (Q8_0 quantization, ~2.7GB VRAM): Rapid summaries, fast transforms, and lightweight edits (~128 tokens/sec).
- **VRAM Budget:** Combined models + Laya (~850MB) consume ~10.2GB VRAM, comfortably fitting within the 16.28GB physical VRAM of the RTX 5060 Ti with ~6GB headroom for KV caches and PyTorch workspaces.

---

### ADR-005: ACID SQLite for Unified Working Memory & Traces
- **Decision:** Use an embedded SQLite database (`.agent_state.db`) for all session state, task DAGs, project memory, and tool execution traces.
- **Rationale:** Zero external server dependencies (unlike Redis, PostgreSQL, or standalone vector DBs). Single-file persistence, full ACID transactions, and sub-millisecond query performance.
- **Design Pattern:** Composite primary keys `(session_id, id)` for tasks and upsert semantics (`INSERT ... ON CONFLICT DO UPDATE`) to prevent collision across interactive launches.

---

### ADR-006: Two-Tier Verification Gate
- **Decision:** Code produced by workers must pass a two-tier verification gate before a session is marked `COMPLETED`:
  1. **Deterministic Tier:** AST syntax parsing (`compile(code, ..., 'exec')`) and automated unit test execution.
  2. **Cognitive Tier:** `qwen3.5:9b` semantic code review of actual project files against the user objective.
- **Targeted Diff Isolation:** The verification layer prioritizes created project files and ignores unrelated uncommitted changes to internal framework files, preventing false review rejections.

---

### ADR-007: Conversational Discovery REPL with Single User Approval Gate
- **Decision:** Require a conversational discovery phase (`InteractiveSession`) before triggering autonomous code generation. The user must explicitly approve the plan (`approve` / `start`).
- **Rationale:** Software engineering failures stem predominantly from mismatched requirements. Interactive discovery ensures alignment on architecture, file structure, and acceptance criteria before writing code.

---

### ADR-008: Automatic Worker Escalation on Failure
- **Decision:** If a task assigned to `deterministic_worker` or `fast_worker_2b` fails, the orchestrator preserves the retry counter and escalates the retry directly to `coder_worker_9b`.
- **Rationale:** Ensures simple tasks attempt zero-LLM or fast paths first, but immediately escalate to full generative power if edge cases arise.

---

## 2. Known Limitations & Technical Debt

1. **Laya Checkpoint Temperature Warning:**
   - **Symptom:** `RuntimeWarning: laya: this checkpoint ships invalid temperatures or values outside [0.5, 5]; using choice:11+=... -> 0.5. Treat confidence from the affected entries as uncalibrated.`
   - **Status:** Upstream model artifact property in `convaiinnovations/laya`. Handled by treating confidence scores as relative ranks rather than calibrated probabilities.
2. **Subtask Iteration Limit:**
   - In `CoderWorker`, `max_iterations` is set to 8. For massive monolithic multi-file projects, subtasks must be broken down into granular tasks (e.g., separate task for frontend and backend) to avoid hitting the iteration ceiling.
3. **Cross-Platform Shell Nuances:**
   - Windows PowerShell vs Command Prompt path separators and chained command differences (`&&`) require using `write_file` directly rather than shell chaining.
