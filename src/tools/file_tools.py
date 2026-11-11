import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from src.tools.base import BaseTool, ToolResult, PermissionTier

class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read text file contents with optional start_line and end_line bounds."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."},
                "start_line": {"type": "integer", "description": "1-based starting line number (optional)."},
                "end_line": {"type": "integer", "description": "1-based ending line number (optional)."}
            },
            "required": ["path"]
        }

    def execute(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        p = Path(path)
        if not p.is_file():
            return ToolResult(success=False, error=f"File not found: {path}", execution_time_ms=(time.perf_counter() - t0)*1000)

        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s_idx = max(0, (start_line - 1)) if start_line else 0
            e_idx = min(total_lines, end_line) if end_line else total_lines

            selected_lines = lines[s_idx:e_idx]
            content = "".join(selected_lines)

            return ToolResult(
                success=True,
                output={
                    "path": str(p),
                    "total_lines": total_lines,
                    "showing_lines": f"{s_idx+1}-{e_idx}",
                    "content": content
                },
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Create a new file or completely overwrite an existing file with given content."
    permission_tier = PermissionTier.WORKSPACE_WRITE

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write."},
                "content": {"type": "string", "description": "Content to write into the file."}
            },
            "required": ["path", "content"]
        }

    def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to {p}",
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

class PatchFileTool(BaseTool):
    name = "patch_file"
    description = "Replace an exact target block of text in an existing file with replacement text."
    permission_tier = PermissionTier.WORKSPACE_WRITE

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to patch."},
                "target": {"type": "string", "description": "Exact text substring to find and replace."},
                "replacement": {"type": "string", "description": "Replacement text to substitute in place of target."}
            },
            "required": ["path", "target", "replacement"]
        }

    def execute(self, path: str, target: str, replacement: str, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        p = Path(path)
        if not p.is_file():
            return ToolResult(success=False, error=f"File not found: {path}", execution_time_ms=(time.perf_counter() - t0)*1000)

        try:
            with open(p, "r", encoding="utf-8") as f:
                original = f.read()

            if target not in original:
                return ToolResult(
                    success=False,
                    error=f"Target string not found in {path}. Ensure exact whitespace and line matches.",
                    execution_time_ms=(time.perf_counter() - t0)*1000
                )

            count = original.count(target)
            patched = original.replace(target, replacement, 1)

            with open(p, "w", encoding="utf-8") as f:
                f.write(patched)

            diff_summary = f"- {target}\n+ {replacement}"
            return ToolResult(
                success=True,
                output=f"Patched 1 occurrence in {path} (total occurrences was {count}).",
                diff=diff_summary,
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

class ListDirTool(BaseTool):
    name = "list_dir"
    description = "List files and directories in a given path with optional recursive pattern match."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to inspect (defaults to current dir)."},
                "pattern": {"type": "string", "description": "Glob pattern (e.g. *.py, **/*.json)."}
            }
        }

    def execute(self, path: str = ".", pattern: Optional[str] = None, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        p = Path(path)
        if not p.is_dir():
            return ToolResult(success=False, error=f"Directory not found: {path}", execution_time_ms=(time.perf_counter() - t0)*1000)

        try:
            entries = []
            if pattern:
                items = list(p.glob(pattern))[:100]
            else:
                items = list(p.iterdir())[:100]

            for item in items:
                entries.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size_bytes": item.stat().st_size if item.is_file() else 0
                })

            return ToolResult(
                success=True,
                output={"directory": str(p), "count": len(entries), "items": entries},
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

