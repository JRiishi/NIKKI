import ast
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.tools.base import BaseTool, ToolResult, PermissionTier

class RunTestsTool(BaseTool):
    name = "run_tests"
    description = "Run pytest or unittest suite and extract passed/failed test cases and stack traces."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_target": {"type": "string", "description": "Path to test file, test folder, or test name."},
                "framework": {"type": "string", "enum": ["pytest", "unittest"], "default": "pytest"}
            }
        }

    def execute(self, test_target: Optional[str] = None, framework: str = "pytest", **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        if framework == "pytest":
            cmd = f"python -m pytest {test_target or ''} -v --no-header"
        else:
            cmd = f"python -m unittest {test_target or 'discover tests'}"

        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=90)
            elapsed = (time.perf_counter() - t0) * 1000

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            success = (proc.returncode == 0)

            return ToolResult(
                success=success,
                output={
                    "framework": framework,
                    "returncode": proc.returncode,
                    "passed": success,
                    "summary": stdout[-500:] if len(stdout) > 500 else stdout,
                    "full_output": stdout
                },
                error=stderr or (stdout if not success else None),
                execution_time_ms=elapsed
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Test suite timed out after 90 seconds.", execution_time_ms=(time.perf_counter() - t0)*1000)
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

class RunLintTool(BaseTool):
    name = "run_lint"
    description = "Perform syntax validation and static AST analysis on Python files without running code."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to python file to validate."}
            },
            "required": ["file_path"]
        }

    def execute(self, file_path: str, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        p = Path(file_path)
        if not p.is_file():
            return ToolResult(success=False, error=f"File not found: {file_path}", execution_time_ms=(time.perf_counter() - t0)*1000)

        try:
            with open(p, "r", encoding="utf-8") as f:
                source = f.read()

            ast.parse(source, filename=str(p))
            return ToolResult(
                success=True,
                output={"file": str(p), "syntax_valid": True, "message": "No syntax errors detected."},
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except SyntaxError as se:
            return ToolResult(
                success=False,
                output={"file": str(p), "syntax_valid": False},
                error=f"SyntaxError at line {se.lineno}, col {se.offset}: {se.msg}\n  {se.text}",
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

