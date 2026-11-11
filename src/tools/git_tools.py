import subprocess
import time
from typing import Dict, Any, Optional
from src.tools.base import BaseTool, ToolResult, PermissionTier

class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Inspect workspace git status: staged, unstaged, untracked files, and current branch."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cwd": {"type": "string", "description": "Repository path (optional)."}
            }
        }

    def execute(self, cwd: Optional[str] = None, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        try:
            res = subprocess.run("git status --short --branch", shell=True, cwd=cwd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return ToolResult(success=False, error=res.stderr.strip() or "Not a git repository.", execution_time_ms=(time.perf_counter() - t0)*1000)

            lines = res.stdout.strip().split("\n")
            branch_info = lines[0] if lines else "unknown"
            modified_files = [l.strip() for l in lines[1:] if l.strip()]

            return ToolResult(
                success=True,
                output={"branch": branch_info, "modified_count": len(modified_files), "files": modified_files},
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "View uncommitted git diffs across the workspace or for a specific file."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Specific file to diff (optional)."},
                "staged": {"type": "boolean", "description": "Whether to check staged changes (default False)."}
            }
        }

    def execute(self, file_path: Optional[str] = None, staged: bool = False, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        try:
            cmd = "git diff --staged" if staged else "git diff"
            if file_path:
                cmd += f" -- {file_path}"
            else:
                cmd += " -- . ':(exclude)*.pyc' ':(exclude)*.db*'"

            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return ToolResult(success=False, error=res.stderr.strip(), execution_time_ms=(time.perf_counter() - t0)*1000)

            diff_text = res.stdout.strip()
            return ToolResult(
                success=True,
                output={"has_diff": bool(diff_text), "diff": diff_text[:5000]},
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "Stage modified files and create a clean git commit."
    permission_tier = PermissionTier.WORKSPACE_WRITE

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit message describing the changes."},
                "files": {"type": "array", "items": {"type": "string"}, "description": "Files to stage (optional, stages all if omitted)."}
            },
            "required": ["message"]
        }

    def execute(self, message: str, files: Optional[list] = None, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        try:
            stage_cmd = f"git add {' '.join(files)}" if files else "git add -A"
            subprocess.run(stage_cmd, shell=True, check=True, capture_output=True, text=True, timeout=15)

            safe_msg = message.replace('"', '\\"')
            res = subprocess.run(f'git commit -m "{safe_msg}"', shell=True, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return ToolResult(success=False, error=res.stderr.strip() or res.stdout.strip(), execution_time_ms=(time.perf_counter() - t0)*1000)

            return ToolResult(
                success=True,
                output={"committed": True, "message": message, "git_output": res.stdout.strip()},
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)
