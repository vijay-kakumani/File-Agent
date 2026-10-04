from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config import get_active_search_roots, SUPPORTED_EXTENSIONS
from app.db import initialize_database
from app.services import (
    state_service,
    document_service,
    search_service,
    indexing_service,
)
from app.rag import DocumentSummarizer

# Initialize database schema and FTS5 index on module load
try:
    initialize_database()
except Exception as _db_err:
    print(f"Warning: Database initialization error: {_db_err}")

# Centralized configuration
SEARCH_DIRS = get_active_search_roots()

# Module level state properties delegation
document_index: List[Dict[str, Any]] = []
indexed_documents = set()


def __getattr__(name: str):
    if name == "current_document":
        return state_service.active_document_path
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def get_current_document() -> Optional[Path]:
    return state_service.active_document_path


def set_current_document(path: Optional[Path]) -> Optional[Path]:
    return state_service.set_active_document(path)


def build_file_index() -> int:
    global document_index
    count = indexing_service.build_file_index()
    document_index = indexing_service.get_indexed_documents()
    return count


def read_file(file_path: Path) -> str:
    return document_service.read_document(Path(file_path))


def read_pdf(pdf_path: Path) -> str:
    return document_service.read_document(Path(pdf_path))


def read_docx(docx_path: Path) -> str:
    return document_service.read_document(Path(docx_path))


def read_text_file(file_path: Path) -> str:
    return document_service.read_document(Path(file_path))


def search_files(query: str, extension_filter: Optional[str] = None) -> List[Path]:
    if not query or not query.strip():
        return []
    res = search_service.search_candidates(query=query, extension_filter=extension_filter)
    return [Path(c.path) for c in res.candidates]


def search_file_content(query: str) -> List[Path]:
    return search_files(query)


def search_documents(query: str, extension_filter: Optional[str] = None) -> List[Path]:
    return search_files(query, extension_filter=extension_filter)


def open_file(file_path: Path) -> str:
    return document_service.open_native_file(Path(file_path))


def summarise_document(file_path: Path) -> str:
    summarizer = DocumentSummarizer()
    res = summarizer.summarize_file(Path(file_path))
    return res.summary


def agent(user_request: str) -> Any:
    from app.agent import DocumentAgentService
    svc = DocumentAgentService()
    res = svc.process_message(user_request)
    # If res is an AgentResult object, convert to backward-compatible return format if string expected
    if hasattr(res, "message"):
        # If intent is FIND and succeeded with data, return legacy dict format for API compatibility
        if res.intent == "FIND" and res.data and "selected" in res.data:
            return {
                "selected": res.data.get("selected"),
                "path": res.data.get("path"),
                "matches": [c["path"] for c in res.search_candidates] if res.search_candidates else [res.data.get("path")],
                "open_status": res.message,
            }
        return res.message
    return res


# Compatibility facade helper
def ensure_indexed() -> int:
    return indexing_service.get_count()