import subprocess
import time
from typing import Dict, Any, Optional
from src.tools.base import BaseTool, ToolResult, PermissionTier

BLOCKED_COMMANDS = [
    "format ",
    "rmdir /s /q c:\\",
    "del /s /q c:\\",
    "rm -rf /",
    "mkfs",
    "dd if="
]

class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Execute a shell command locally in the workspace with timeout control."
    permission_tier = PermissionTier.DANGEROUS_SYSTEM

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The exact shell command to execute."},
                "cwd": {"type": "string", "description": "Working directory (defaults to current workspace)."},
                "timeout_seconds": {"type": "integer", "description": "Maximum seconds before terminating (default 60)."}
            },
            "required": ["command"]
        }

    def execute(self, command: str, cwd: Optional[str] = None, timeout_seconds: int = 60, **kwargs) -> ToolResult:
        t0 = time.perf_counter()

        cmd_lower = command.lower()
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                return ToolResult(
                    success=False,
                    error=f"Command rejected by safety gate: prohibited dangerous substring '{blocked}' detected.",
                    execution_time_ms=(time.perf_counter() - t0)*1000
                )

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            elapsed = (time.perf_counter() - t0)*1000
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            success = (proc.returncode == 0)
            return ToolResult(
                success=success,
                output={
                    "command": command,
                    "returncode": proc.returncode,
                    "stdout": stdout,
                    "stderr": stderr
                },
                error=stderr if not success else None,
                execution_time_ms=elapsed
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout_seconds} seconds.",
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.perf_counter() - t0)*1000
            )

