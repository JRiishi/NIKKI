# Niiki Data Flow & Request Lifecycle

## 1. End-to-End Request Lifecycle Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / User
    participant CLI as cli.py (Terminal REPL)
    participant IS as InteractiveSession
    participant AO as AgentOrchestrator
    participant GW as RequestGateway
    participant DB as StateDatabase (SQLite)
    participant SP as SmartPlanner (Qwen 9B)
    participant LR as LayaRouterEngine (Laya CUDA)
    participant WP as Worker Pool
    participant TR as ToolRegistry & PermissionGate
    participant VL as VerificationLayer (AST + Qwen 9B)

    Dev->>CLI: Input prompt / chat message
    CLI->>IS: handle_message(user_text)
    IS->>IS: Check approval keywords & blueprint state
    alt Discovery / Clarification Phase
        IS->>DB: Record user message
        IS->>CLI: Return clarifying questions / blueprint draft
        CLI->>Dev: Render response
    else Plan Approved by User
        IS-->>CLI: Return (approval_notice, approved_goal)
        CLI->>AO: run(approved_goal, session_id)
        
        Note over AO,GW: 1. Gateway & Validation
        AO->>GW: validate_and_route(user_request, session_id)
        GW-->>AO: ValidatedRequest(sanitized_prompt, category)
        
        Note over AO,DB: 2. State Initialization
        AO->>DB: create_session(session_id, goal)
        AO->>DB: set_task_graph(initial_tasks)
        
        Note over AO,SP: 3. Strategic Task Planning
        AO->>SP: create_plan(goal, project_context, category)
        SP-->>AO: List[TaskNode] (DAG with dependencies)
        AO->>DB: Persist Task DAG in tasks table
        
        Note over AO,WP: 4. FSM Execution Loop
        loop For each runnable task in DAG
            AO->>DB: get_next_runnable_task()
            AO->>DB: update_task_status(task.id, 'IN_PROGRESS')
            
            alt Is Retrying Failed Task?
                AO->>AO: Escalate directly to coder_worker_9b
            else Fresh Task
                AO->>LR: route_task(task)
                LR-->>AO: routing_decision (Laya neural pick: ~29ms)
            end
            
            AO->>WP: worker.execute(task, bounded_context)
            
            loop Tool Invocations (ReAct loop)
                WP->>TR: execute(tool_name, arguments)
                TR->>TR: PermissionGate tier check
                TR->>DB: log_tool_execution(tool_output, execution_time)
                TR-->>WP: ToolResult(success, output)
            end
            
            WP-->>AO: WorkerResult(success, output, error)
            
            alt Task Succeeded
                AO->>DB: update_task_status(task.id, 'COMPLETED')
            else Task Failed & Retries Remaining
                AO->>DB: update_task_status(task.id, 'PENDING', error)
            else Task Failed & No Retries
                AO->>DB: update_task_status(task.id, 'FAILED', error)
            end
        end
        
        Note over AO,VL: 5. Two-Tier Verification
        AO->>VL: verify_execution(goal, task_summary)
        VL->>TR: Optional: run_tests / run_lint (Tier 1 AST)
        VL->>VL: Gather targeted diff & created project files
        VL-->>AO: VerificationReport(passed, score, feedback)
        
        AO->>DB: update_session_status(session_id, final_status)
        AO-->>CLI: OrchestrationResult(status, completed, failed, report)
        CLI->>IS: record_execution_result(...)
        CLI->>Dev: Render rich execution summary & stats
    end
```

---

## 2. Detailed Data Transformations

### Phase 1: Developer Input → Validated Request
- **Input:** Raw text entered by developer in CLI REPL or CLI argument.
- **Transformation:** `RequestGateway.validate_and_route()`:
  - Validates minimum string length (>= 3 chars).
  - Sanitizes malicious shell injections (blocking dangerous commands like `rm -rf /`, `format`, `dd if=`).
  - Infers project category: `NEW_PROJECT`, `FEATURE_ADDITION`, `BUG_FIX`, `REFACTOR`, `TESTING`, or `GENERAL_SCRIPT`.
- **Output:** `ValidatedRequest` (Pydantic model containing `session_id`, `sanitized_prompt`, `inferred_category`, `metadata`).

### Phase 2: Goal → Task DAG (Planning)
- **Input:** Sanitized prompt + project context summary from `ProjectMemory`.
- **Transformation:** `SmartPlanner.create_plan()` prompts `qwen3.5:9b` with a structured system prompt requiring a strict JSON array.
- **Data Model:**
  ```json
  [
    {
      "id": "task_1",
      "title": "Scaffold project directory and modules",
      "description": "Create src/ and test/ folders with initial skeleton",
      "dependencies": [],
      "inputs": {"criteria": "Files exist on disk"}
    },
    {
      "id": "task_2",
      "title": "Implement core algorithm",
      "description": "Write implementation logic in src/module.py",
      "dependencies": ["task_1"],
      "inputs": {"criteria": "Syntax valid and passes linting"}
    }
  ]
  ```
- **Storage:** Persisted to SQLite `tasks` table with composite key `(session_id, id)`.

### Phase 3: Task → Worker Dispatch (Laya Neural Routing)
- **Input:** Active `TaskNode` object.
- **Transformation:** `LayaRouterEngine.route_task()` calls `convaiinnovations/laya` (typed-decisions FP16 on PyTorch CUDA).
  - Compares the task's semantic vector against three criteria:
    1. Deterministic operations (zero-LLM testing, linting, git).
    2. Lightweight generation (Qwen 2B summaries, simple transforms).
    3. Generative engineering (Qwen 9B code synthesis, multi-file editing).
  - Evaluates neural decision in ~29ms without any Python string pattern matching.
- **Fallback / Escalation:** If a worker returns `success=False` on its first execution, the orchestrator escalates the retry directly to `coder_worker_9b`.

### Phase 4: Worker ReAct Execution & Tool Operations
- **Input:** Bounded context assembled by `ContextRetriever` (task details + recent execution traces + project summary).
- **Execution:**
  - `CoderWorker` runs an autonomous ReAct loop for up to 8 iterations.
  - Generates JSON tool actions: `{"action": "call_tool", "tool_name": "...", "arguments": {...}}` or `{"action": "finish", "summary": "..."}`.
  - `ToolRegistry` evaluates the permission tier against `PermissionGate`.
  - Tool execution occurs locally; stdout/stderr and execution times are recorded in SQLite `execution_history`.

### Phase 5: Verification & Delivery
- **Input:** Goal, task completion ratio, created project files, and optional test outputs.
- **Transformation:** `VerificationLayer.verify_execution()`:
  - Scans created files using targeted discovery (prioritizing files and directories referenced in the goal and untracked in git status).
  - Inspects AST syntax validity and runs unit tests if available.
  - Sends the clean project files to `qwen3.5:9b` code reviewer with low temperature (`0.1`).
- **Output:** `VerificationReport` (`passed: bool`, `review_score: float`, `feedback: str`, `suggested_fix: str`).
- **Final Result:** `OrchestrationResult` returned to `cli.py` and displayed with Rich formatting.
