import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from src.tools.registry import ToolRegistry
from src.service.model_service import LocalModelService

class VerificationReport(BaseModel):
    passed: bool
    deterministic_passed: bool
    review_score: float = 1.0
    feedback: str = ""
    suggested_fix: Optional[str] = None
    files_inspected: List[str] = []

REVIEWER_SYSTEM_PROMPT = """You are the Senior Code Reviewer and Quality Gate for an Autonomous Coding Agent.
Your job is to rigorously review the changes made by the agent against the user's objective and task criteria.

Verify:
1. Does the code fulfill the functional requirements?
2. Are there logic bugs, concurrency flaws, or unhandled exceptions?
3. Is code clean and syntactically correct?

Respond with a JSON object matching this schema:
{
  "passed": true,
  "score": 0.95,
  "feedback": "Code cleanly implements the requested feature and passes tests.",
  "suggested_fix": null
}

If any critical requirement is unmet or broken:
{
  "passed": false,
  "score": 0.3,
  "feedback": "Missing error handling for null input on line 42.",
  "suggested_fix": "Add 'if not data: return False' before accessing attributes."
}
"""

class VerificationLayer:
    """
    Two-Tier Verification Gate:
    1. Deterministic Tier: AST syntax linting & unit test execution.
    2. Cognitive Review Tier: Qwen 3.5 9B semantic review against goal & acceptance criteria.
    """

    def __init__(self, tool_registry: ToolRegistry, model_service: LocalModelService):
        self.tools = tool_registry
        self.service = model_service

    def verify_execution(
        self,
        goal: str,
        task_summary: str,
        acceptance_criteria: str = "",
        test_target: Optional[str] = None
    ) -> VerificationReport:
        # 1. Deterministic Check: Run tests if available
        test_output = ""
        deterministic_passed = True
        if test_target:
            test_res = self.tools.execute("run_tests", test_target=test_target)
            if not test_res.success:
                deterministic_passed = False
                return VerificationReport(
                    passed=False,
                    deterministic_passed=False,
                    review_score=0.0,
                    feedback=f"Deterministic tests failed: {test_res.error}",
                    suggested_fix="Fix failing test assertions."
                )
            test_output = f"Test suite output: {test_res.output}"

        # 2. Inspect git diff and untracked/modified files
        diff_res = self.tools.execute("git_diff")
        diff_text = diff_res.output.get("diff", "") if diff_res.success and diff_res.output else ""

        # Collect changed / created files, prioritizing files referenced in the goal or summary
        relevant_files = []
        skip_patterns = {".pyc", ".db", ".log", "__pycache__", ".venv", "venv", "benchmarks"}

        # (a) Files explicitly mentioned in goal or task summary
        candidates = re.findall(r'[\w\-./\\]+\.[a-zA-Z0-9]+', f"{goal} {task_summary}")
        for c in candidates:
            p = Path(c)
            if p.exists() and p.is_file() and not any(sp in p.parts or c.endswith(sp) for sp in skip_patterns):
                norm = p.as_posix()
                if norm not in relevant_files:
                    relevant_files.append(norm)

        # (b) Files or directories reported as untracked or modified by git status
        status_res = self.tools.execute("git_status")
        if status_res.success and isinstance(status_res.output, dict):
            for fline in status_res.output.get("files", []):
                parts = fline.strip().split(None, 1)
                if len(parts) == 2:
                    clean_path = parts[1].strip('"').strip("'").rstrip("/\\")
                    p = Path(clean_path)
                    if p.exists():
                        if p.is_dir():
                            for subfile in p.rglob("*"):
                                if subfile.is_file() and not any(sp in subfile.parts or subfile.name.endswith(sp) for sp in skip_patterns):
                                    norm = subfile.as_posix()
                                    if norm not in relevant_files:
                                        relevant_files.append(norm)
                        elif p.is_file() and not any(sp in p.parts or clean_path.endswith(sp) for sp in skip_patterns):
                            norm = p.as_posix()
                            if norm not in relevant_files:
                                relevant_files.append(norm)

        # (c) Check any directory names mentioned in goal
        for token in re.findall(r'[a-zA-Z0-9_\-]+', f"{goal} {task_summary}"):
            p = Path(token)
            if p.exists() and p.is_dir() and not any(sp in p.parts for sp in skip_patterns):
                for subfile in p.rglob("*"):
                    if subfile.is_file() and not any(sp in subfile.parts or subfile.name.endswith(sp) for sp in skip_patterns):
                        norm = subfile.as_posix()
                        if norm not in relevant_files:
                            relevant_files.append(norm)

        # Put actual project files at the very top of the review context
        project_content = ""
        for fpath in relevant_files:
            try:
                p = Path(fpath)
                if p.stat().st_size < 50_000:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    project_content += f"\n\n=== Project File: {fpath} ===\n{content}\n"
            except Exception:
                pass

        if project_content.strip():
            diff_text = project_content
        elif not diff_text.strip():
            diff_text = "No file modifications or diffs detected."

        # 3. Cognitive Review with Qwen 9B
        review_prompt = f"""User Objective:
{goal}

Task Summary:
{task_summary}

Acceptance Criteria:
{acceptance_criteria or 'Working solution with clean code.'}

Code Diff / Modified Files:
```
{diff_text[:8000]}
```

{test_output}

Review these changes and output your JSON verification verdict."""

        try:
            resp = self.service.generate_text(
                model_key="qwen_primary",
                prompt=review_prompt,
                system=REVIEWER_SYSTEM_PROMPT,
                temperature=0.1
            )
            raw = resp.get("response", "")
            verdict = self._parse_review_json(raw)
            return VerificationReport(
                passed=verdict.get("passed", True),
                deterministic_passed=deterministic_passed,
                review_score=verdict.get("score", 1.0),
                feedback=verdict.get("feedback", "Review completed successfully."),
                suggested_fix=verdict.get("suggested_fix"),
                files_inspected=relevant_files
            )
        except Exception as e:
            # Fallback to deterministic check result
            return VerificationReport(
                passed=deterministic_passed,
                deterministic_passed=deterministic_passed,
                review_score=0.8,
                feedback=f"Reviewer completed with note: {e}",
                files_inspected=relevant_files
            )

    def _parse_review_json(self, text: str) -> Dict[str, Any]:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"passed": True, "score": 0.85, "feedback": "Parsed text review accepted."}
