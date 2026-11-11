import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from src.service.model_service import LocalModelService

SYSTEM_PROMPT = """You are Niiki, an expert Senior Software Engineer and Solutions Architect.
You are pairing with the user in an interactive discovery phase before writing any code.

Your role:
1. Greet the user warmly if they say hello or make casual remarks, and ask what software, feature, or tool they want to build today.
2. When the user proposes an idea:
   - Ask clarifying questions if requirements or edge cases are ambiguous.
   - Discuss architecture, file structure, libraries, and modular design.
   - Propose an explicit testing and verification strategy.
3. Once the requirements and design are formed, present a clear, structured "PROJECT BLUEPRINT":
   - **Goal & Core Requirements**
   - **Proposed Files & Modules**
   - **Key Functions / Classes**
   - **Acceptance Criteria & Tests**
   Then conclude with:
   "Do you approve this plan to begin autonomous execution? (Type 'approve' or 'start' to proceed, or let me know what you'd like to change!)"
4. If the user suggests modifications, update the plan accordingly.
5. You are an autonomous software engineering agent equipped with a local execution engine that can create directories, write files, run tests, and execute commands upon user approval.
   - You CAN and DO create real directories and files when the developer approves the plan.
   - NEVER tell the user that you cannot create directories or files, or that you are just a chat interface with no filesystem access.
   - If an execution attempt failed, explain the exact error or timeout that occurred, and offer to adjust the plan or retry.

Keep responses concise, technical, and collaborative. Do NOT write full code implementations in this chat—code generation will happen autonomously after the plan is approved."""

APPROVAL_KEYWORDS = {
    "approve", "approved", "start", "proceed", "go ahead", "looks good", 
    "lgtm", "yes", "do it", "build it", "start project", "let's do it", 
    "lets do it", "let's go", "lets go", "ok to proceed", "run it"
}

class InteractiveSession:
    """
    Manages conversational discovery, requirement refinement, architecture consensus,
    and user approval gating before triggering autonomous orchestrator execution.
    """

    def __init__(self, model_service: LocalModelService, session_id: Optional[str] = None):
        self.service = model_service
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.plan_proposed: bool = False
        self.last_proposed_blueprint: str = ""
        self.discussed_topics: List[str] = []

    def handle_message(self, user_text: str) -> Tuple[str, Optional[str]]:
        """
        Processes developer input.
        Returns:
            Tuple[assistant_response, approved_goal_to_execute]
            If approved_goal_to_execute is not None, the user has approved execution.
        """
        clean_text = user_text.strip()
        lower_text = clean_text.lower().rstrip(".!?,")

        # 1. Check if user is giving approval
        is_approval = lower_text in APPROVAL_KEYWORDS or any(
            lower_text.startswith(kw) for kw in ["approve", "start", "proceed", "go ahead"]
        )

        if is_approval:
            if self.plan_proposed and self.last_proposed_blueprint:
                # User approved the proposed plan
                goal = self._synthesize_execution_goal()
                reply = "✓ Plan approved! Initiating autonomous engineering pipeline..."
                return reply, goal
            elif len(self.messages) > 1 and len(self.discussed_topics) > 0:
                # Plan hasn't been explicitly formatted yet, but topics were discussed
                goal = f"Implement and verify: {' '.join(self.discussed_topics)}"
                reply = "✓ Plan approved! Initiating autonomous engineering pipeline..."
                return reply, goal
            else:
                return (
                    "We haven't discussed a project plan yet! Tell me what you'd like to build "
                    "or work on (e.g., 'Build a markdown-to-html converter' or 'Add JWT authentication').",
                    None
                )

        # 2. Track user topics
        if len(clean_text) > 5 and lower_text not in ("hello", "hi", "hey"):
            self.discussed_topics.append(clean_text)

        # 3. Add to chat history
        self.messages.append({"role": "user", "content": clean_text})

        # 4. Generate assistant response using Qwen 9B
        try:
            chat_result = self.service.chat(
                model_key="qwen_primary",
                messages=self.messages,
                temperature=0.3
            )
            reply = chat_result.get("content", "")
        except Exception as e:
            # Fallback if Ollama encounters issue
            reply = f"Error communicating with local AI model: {e}"

        # 5. Check if the assistant proposed a project blueprint
        if "project blueprint" in reply.lower() or "do you approve" in reply.lower() or "acceptance criteria" in reply.lower():
            self.plan_proposed = True
            self.last_proposed_blueprint = reply

        self.messages.append({"role": "assistant", "content": reply})
        return reply, None

    def record_execution_result(self, status: str, tasks_completed: int, total_tasks: int, feedback: str = ""):
        """
        Record autonomous pipeline execution result into chat context so the assistant
        accurately explains the real execution state if the user asks.
        """
        summary = (
            f"[Execution Pipeline Finished: Status={status}. "
            f"Tasks completed: {tasks_completed}/{total_tasks}. "
            f"Details: {feedback[:300]}]"
        )
        self.messages.append({"role": "system", "content": summary})

    def _synthesize_execution_goal(self) -> str:
        """
        Synthesizes a structured goal string from the blueprint and discussion history
        to pass into the SmartPlanner and Orchestrator.
        """
        if self.last_proposed_blueprint:
            return (
                f"Project Specification:\n{self.last_proposed_blueprint}\n\n"
                f"Context History:\n" + "\n".join(self.discussed_topics[-5:])
            )
        return " ".join(self.discussed_topics)

