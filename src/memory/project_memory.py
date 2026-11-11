import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.memory.state_db import StateDatabase

def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file for staleness tracking."""
    if not file_path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

class ProjectMemory:
    """
    Long-term project memory storing architecture notes, coding conventions,
    design decisions, and file summaries with hash-based staleness detection.
    """

    def __init__(self, db: StateDatabase):
        self.db = db

    def record_decision(self, title: str, decision: str) -> None:
        self.db.set_memory(key=f"decision:{title}", category="decision", content=decision)

    def record_convention(self, name: str, rule: str) -> None:
        self.db.set_memory(key=f"convention:{name}", category="convention", content=rule)

    def record_architecture(self, component: str, description: str) -> None:
        self.db.set_memory(key=f"arch:{component}", category="architecture", content=description)

    def record_file_summary(self, file_path: Path, summary: str) -> None:
        file_hash = compute_file_hash(file_path)
        self.db.set_memory(
            key=f"file:{file_path.as_posix()}",
            category="file_summary",
            content=summary,
            file_path=str(file_path),
            file_hash=file_hash
        )

    def is_file_stale(self, file_path: Path) -> bool:
        """Check if file has changed since the last stored summary."""
        mem = self.db.get_memory(f"file:{file_path.as_posix()}")
        if not mem:
            return True
        current_hash = compute_file_hash(file_path)
        return mem.get("file_hash") != current_hash

    def get_summary_context(self) -> str:
        """Render high-level project memory for inclusion in agent prompt."""
        decisions = self.db.get_memories_by_category("decision")
        conventions = self.db.get_memories_by_category("convention")
        arch = self.db.get_memories_by_category("architecture")

        parts = []
        if arch:
            parts.append("### Project Architecture:")
            for a in arch:
                parts.append(f"- {a['key'].replace('arch:', '')}: {a['content']}")
        if conventions:
            parts.append("### Coding Conventions:")
            for c in conventions:
                parts.append(f"- {c['key'].replace('convention:', '')}: {c['content']}")
        if decisions:
            parts.append("### Recorded Decisions:")
            for d in decisions:
                parts.append(f"- {d['key'].replace('decision:', '')}: {d['content']}")

        return "\n".join(parts) if parts else "No project memory recorded yet."
