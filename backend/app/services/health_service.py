import sqlite3
from typing import Dict, Any

from ollama import chat

from app.config import (
    SQLITE_DB_PATH,
    CHROMA_DB_DIR,
    OLLAMA_MODEL,
    get_active_search_roots,
)
from app.db import get_document_count
from app.models.results import HealthStatus


class HealthService:
    """
    Phase 9 Health Diagnostics Service.
    Checks API status, SQLite database availability, ChromaDB vector store, Ollama local model, and search roots.
    """

    def check_health(self) -> HealthStatus:
        # Check SQLite DB
        db_ok = False
        try:
            conn = sqlite3.connect(str(SQLITE_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            db_ok = True
            conn.close()
        except Exception:
            db_ok = False

        # Check Chroma DB Directory
        chroma_ok = CHROMA_DB_DIR.exists()

        # Check Ollama Availability
        ollama_ok = False
        try:
            # Short test probe
            res = chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content": "hi"}])
            ollama_ok = bool(res and res.message and res.message.content)
        except Exception:
            ollama_ok = False

        active_roots = get_active_search_roots()
        doc_count = get_document_count() if db_ok else 0

        status_str = "healthy" if (db_ok and chroma_ok) else "degraded"

        return HealthStatus(
            status=status_str,
            api_running=True,
            database_available=db_ok,
            chroma_available=chroma_ok,
            ollama_available=ollama_ok,
            active_search_roots_count=len(active_roots),
            indexed_document_count=doc_count,
        )


# Global singleton instance
health_service = HealthService()
