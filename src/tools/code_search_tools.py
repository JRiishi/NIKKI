import ast
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.tools.base import BaseTool, ToolResult, PermissionTier

class RegexSearchTool(BaseTool):
    name = "regex_search"
    description = "Search for regex patterns across text files in a workspace directory."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for."},
                "directory": {"type": "string", "description": "Directory to search within (default '.')."},
                "file_extension": {"type": "string", "description": "Optional extension filter (e.g. '.py', '.js')."}
            },
            "required": ["pattern"]
        }

    def execute(self, pattern: str, directory: str = ".", file_extension: Optional[str] = None, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        p = Path(directory)
        if not p.is_dir():
            return ToolResult(success=False, error=f"Directory not found: {directory}", execution_time_ms=(time.perf_counter() - t0)*1000)

        try:
            regex = re.compile(pattern, re.IGNORECASE)
            matches = []

            for root, dirs, files in os.walk(p):
                # skip git, pycache, venv
                dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".venv", "venv", "node_modules", ".gemini"}]
                for file in files:
                    if file_extension and not file.endswith(file_extension):
                        continue
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            for idx, line in enumerate(f, 1):
                                if regex.search(line):
                                    matches.append({
                                        "file": str(file_path),
                                        "line": idx,
                                        "text": line.strip()
                                    })
                                    if len(matches) >= 50:
                                        break
                    except Exception:
                        continue
                if len(matches) >= 50:
                    break

            return ToolResult(
                success=True,
                output={"pattern": pattern, "match_count": len(matches), "matches": matches},
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

class SymbolSearchTool(BaseTool):
    name = "symbol_search"
    description = "AST-based extraction of functions, classes, and methods across Python files."
    permission_tier = PermissionTier.SAFE_READ

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Python file or directory to scan for code symbols."}
            },
            "required": ["file_path"]
        }

    def execute(self, file_path: str, **kwargs) -> ToolResult:
        t0 = time.perf_counter()
        target = Path(file_path)
        files_to_scan = []
        if target.is_file() and target.suffix == ".py":
            files_to_scan.append(target)
        elif target.is_dir():
            files_to_scan = list(target.rglob("*.py"))[:30]
        else:
            return ToolResult(success=False, error=f"Target not found: {file_path}", execution_time_ms=(time.perf_counter() - t0)*1000)

        symbols = []
        try:
            for py_file in files_to_scan:
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                try:
                    tree = ast.parse(content, filename=str(py_file))
                except SyntaxError:
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        symbols.append({
                            "type": "class",
                            "name": node.name,
                            "file": str(py_file),
                            "line": node.lineno,
                            "doc": ast.get_docstring(node)
                        })
                    elif isinstance(node, ast.FunctionDef):
                        symbols.append({
                            "type": "function",
                            "name": node.name,
                            "file": str(py_file),
                            "line": node.lineno,
                            "args": [a.arg for a in node.args.args],
                            "doc": ast.get_docstring(node)
                        })

            return ToolResult(
                success=True,
                output={"symbols_found": len(symbols), "symbols": symbols[:60]},
                execution_time_ms=(time.perf_counter() - t0)*1000
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), execution_time_ms=(time.perf_counter() - t0)*1000)

