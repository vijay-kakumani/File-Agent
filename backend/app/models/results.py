from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class DocumentInfo:
    name: str
    path: str
    extension: str
    folder: str
    size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "extension": self.extension,
            "folder": self.folder,
            "size": self.size,
        }

    @classmethod
    def from_path(cls, path: Any) -> "DocumentInfo":
        p = Path(path)
        resolved = str(p.resolve() if p.is_absolute() else p)
        return cls(
            name=p.name,
            path=resolved,
            extension=p.suffix.lower(),
            folder=p.parent.name if p.parent else "",
            size=0,
        )


@dataclass
class AgentResult:
    success: bool
    intent: str
    message: str
    data: Optional[Dict[str, Any]] = None
    active_document: Optional[Dict[str, Any]] = None
    search_candidates: List[Dict[str, Any]] = field(default_factory=list)
    ambiguous: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "intent": self.intent,
            "message": self.message,
            "data": self.data,
            "active_document": self.active_document,
            "search_candidates": self.search_candidates,
            "ambiguous": self.ambiguous,
            "error": self.error,
        }


@dataclass
class HealthStatus:
    status: str
    api_running: bool
    database_available: bool
    chroma_available: bool
    ollama_available: bool
    active_search_roots_count: int
    indexed_document_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "api_running": self.api_running,
            "database_available": self.database_available,
            "chroma_available": self.chroma_available,
            "ollama_available": self.ollama_available,
            "active_search_roots_count": self.active_search_roots_count,
            "indexed_document_count": self.indexed_document_count,
        }
