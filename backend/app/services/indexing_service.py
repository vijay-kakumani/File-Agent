from pathlib import Path
from typing import List, Dict, Any, Optional

from app.indexing import IncrementalIndexer
from app.db import get_all_documents, get_document_count
from app.models import DocumentMetadata


class IndexingService:
    """
    Phase 9 Canonical Indexing Lifecycle Service.
    Coordinates incremental filesystem scanning, SQLite/FTS5 metadata indexing, and vector sync.
    Single ownership of file index lifecycle.
    """

    def __init__(self, indexer: Optional[IncrementalIndexer] = None):
        self.indexer = indexer or IncrementalIndexer()

    def build_file_index(self) -> int:
        self.indexer.scan_and_index()
        return get_document_count()

    def get_indexed_documents(self, limit: int = 1000) -> List[Dict[str, Any]]:
        docs = get_all_documents(limit=limit)
        return [
            {
                "name": d.name,
                "path": str(Path(d.path)),
                "extension": d.extension,
                "folder": d.folder,
                "size": d.size,
            }
            for d in docs
        ]

    def get_count(self) -> int:
        return get_document_count()


# Global singleton instance
indexing_service = IndexingService()
