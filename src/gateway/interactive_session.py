import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from src.service.model_service import LocalModelService

SYSTEM_PROMPT = """You are NIKKI, a unified Autonomous AI Software Engineer.
You are One complete AI built from specialized internal cognitive systems (neural routing for sub-30ms decisions, deep generative synthesis for code, deterministic verification gates, and filesystem tool executors).
To the user, you are ONE unified expert partner who owns all your capabilities end-to-end:
- You discover requirements, architect modular codebases, and formulate clear PROJECT BLUEPRINTS.
- You have REAL local filesystem execution capabilities: you create directories, write complete files to disk, run tests, and debug errors.
- You NEVER claim to be 'just a text AI assistant without filesystem access' or disclaim your execution abilities.
- When an execution run finishes, you take full ownership of the outcome: analyze the verification findings, explain what was created, and provide immediate guidance or fixes.

Interaction Rules:
1. Introduce yourself as NIKKI, greet the user warmly, and discuss what software or tool they want to build today.
2. When requirements are understood, present a structured 'PROJECT BLUEPRINT' with files, functions, acceptance criteria, and conclude with:
   "Do you approve this plan to begin autonomous execution? (Type 'approve' or 'start' to proceed, or let me know what you'd like to change!)"
3. If the user asks whether you made the files or asks about the project state, consult the system execution update in your context and answer with complete first-person ownership (e.g. 'Yes, I created ...').
4. Keep responses technical, concise, and focused. Do not output raw full code files in the chat; real files will be written to disk during execution."""

APPROVAL_KEYWORDS = {
    "approve", "approved", "start", "proceed", "go ahead", "looks good", 
    "lgtm", "yes", "do it", "build it", "start project", "let's do it", 
    "lets do it", "let's go", "lets go", "ok to proceed", "run it",
    "fix it", "fix this", "fix", "please fix", "repair it", "yes fix it"
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
            lower_text.startswith(kw) or kw in lower_text for kw in ["approve", "start", "proceed", "go ahead", "fix it", "fix this", "fix for me"]
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

        # 3. Add to chat history (with sliding window to protect context memory)
        self.messages.append({"role": "user", "content": clean_text})
        bounded_messages = [self.messages[0]] + self.messages[-8:] if len(self.messages) > 9 else self.messages

        # 4. Generate assistant response using Qwen 9B
        try:
            chat_result = self.service.chat(
                model_key="qwen_primary",
                messages=bounded_messages,
                temperature=0.3
            )
            reply = chat_result.get("content", "").strip()
            if not reply:
                reply = (
                    "I understand the issue. Type **'approve'** or **'start'** to start the "
                    "autonomous repair pipeline and patch the code files directly!"
                )
        except Exception as e:
            # Fallback if Ollama encounters issue
            reply = f"Error communicating with local AI model: {e}"

        # 5. Check if the assistant proposed an actual project blueprint
        lower_reply = reply.lower()
        is_clarification = any(p in lower_reply for p in ["i'll present", "i will present", "quick clarifications", "clarifying questions", "before we lock in"])
        is_actual_blueprint = (
            ("project blueprint" in lower_reply and ("do you approve" in lower_reply or "file structure" in lower_reply or "acceptance criteria" in lower_reply))
            or ("do you approve this plan" in lower_reply)
        )
        if is_actual_blueprint and not is_clarification:
            self.plan_proposed = True
            self.last_proposed_blueprint = reply

        self.messages.append({"role": "assistant", "content": reply})
        return reply, None

    def record_execution_result(
        self,
        status: str,
        tasks_completed: int,
        total_tasks: int,
        feedback: str = "",
        files: Optional[List[str]] = None
    ):
        """
        Record autonomous pipeline execution result into chat context so the assistant
        accurately explains the real execution state if the user asks.
        """
        file_list = ", ".join(files) if files else "None detected"
        summary = (
            f"[SYSTEM UPDATE - AUTONOMOUS EXECUTION OUTCOME:\n"
            f"You (NIKKI) just finished executing the pipeline for this project.\n"
            f"- Status: {status}\n"
            f"- Tasks completed: {tasks_completed}/{total_tasks}\n"
            f"- Files created/verified: {file_list}\n"
            f"- Verification Feedback: {feedback}\n"
            f"INSTRUCTION: Take full ownership of this outcome as NIKKI. If the user asks whether you made "
            f"the files or how to run them, confirm the exact files created ({file_list}) and give clear execution instructions. "
            f"NEVER say you cannot create files or that you lack filesystem access. If the run failed, explain the exact error "
            f"and offer to fix it autonomously once approved.]"
        )
        self.messages.append({"role": "system", "content": summary})

    def _synthesize_execution_goal(self) -> str:
        """
        Synthesizes a structured goal string from the blueprint and discussion history
        to pass into the SmartPlanner and Orchestrator.
        """
        user_reqs = " ".join(self.discussed_topics)
        if self.last_proposed_blueprint:
            return (
                f"User Goal:\n{user_reqs}\n\n"
                f"Approved Blueprint Specification:\n{self.last_proposed_blueprint}"
            )
        return user_reqs

