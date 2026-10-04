import time
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional, Set
import sqlite3

from app.config.settings import (
    get_active_search_roots,
    SUPPORTED_EXTENSIONS,
    SQLITE_DB_PATH,
)
from app.db.database import initialize_database, get_db_connection
from app.db.fts_index import upsert_document, delete_document
from app.models.document import DocumentMetadata, generate_canonical_doc_id
from app.documents.extractor import extract_text


from app.rag import VectorStore


class IncrementalIndexer:
    """
    Incremental Document Indexer.
    Compares filesystem state (path, size, mtime) against persistent SQLite metadata.
    Skips unchanged documents, indexes new documents, updates modified documents,
    and removes deleted documents. Also syncs persistent ChromaDB vector embeddings.
    """

    def __init__(
        self,
        db_path: Path = None,
        chroma_dir: Path = None,
        extractor_fn: Callable[[Path], str] = None,
        enable_vectors: bool = True
    ):
        self.db_path = db_path or SQLITE_DB_PATH
        self.chroma_dir = chroma_dir
        self.extractor_fn = extractor_fn or extract_text
        self.enable_vectors = enable_vectors

        # Ensure database and FTS5 tables are initialized
        initialize_database(self.db_path)

        if self.enable_vectors:
            self.vector_store = VectorStore(chroma_dir=self.chroma_dir)
        else:
            self.vector_store = None

    def get_existing_db_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetches current indexed documents metadata from SQLite.
        Returns dict keyed by doc_id: {"path": str, "size": int, "modified_time": float}
        """
        conn = get_db_connection(self.db_path)
        try:
            cursor = conn.execute("SELECT doc_id, path, size, modified_time FROM documents;")
            rows = cursor.fetchall()
            return {
                row["doc_id"]: {
                    "path": row["path"],
                    "size": row["size"],
                    "modified_time": row["modified_time"],
                }
                for row in rows
            }
        finally:
            conn.close()

    def scan_and_index(
        self,
        custom_roots: Optional[List[Path]] = None,
        extract_content: bool = True
    ) -> Dict[str, Any]:
        """
        Executes an incremental scan over configured search roots.
        Categorizes files into NEW, MODIFIED, UNCHANGED, and DELETED.
        """
        start_time = time.time()
        search_roots = get_active_search_roots(custom_roots)

        existing_db_docs = self.get_existing_db_metadata()
        discovered_doc_ids: Set[str] = set()

        total_discovered = 0
        newly_indexed_count = 0
        updated_count = 0
        skipped_count = 0
        deleted_count = 0

        for root in search_roots:
            if not root.exists() or not root.is_dir():
                continue

            try:
                for file_path in root.rglob("*"):
                    try:
                        if not file_path.is_file():
                            continue

                        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                            continue

                        resolved_path = file_path.resolve()
                        stat = resolved_path.stat()
                        doc_id = generate_canonical_doc_id(resolved_path)
                        discovered_doc_ids.add(doc_id)
                        total_discovered += 1

                        file_size = stat.st_size
                        file_mtime = stat.st_mtime

                        if doc_id not in existing_db_docs:
                            # 1. NEW FILE
                            content = self.extractor_fn(resolved_path) if extract_content else None
                            doc_meta = DocumentMetadata(
                                doc_id=doc_id,
                                name=resolved_path.name,
                                path=str(resolved_path),
                                extension=resolved_path.suffix.lower(),
                                folder=resolved_path.parent.name,
                                size=file_size,
                                modified_time=file_mtime,
                                indexed_time=time.time(),
                                content=content
                            )
                            upsert_document(doc_meta, self.db_path)
                            if self.vector_store and content:
                                self.vector_store.upsert_document_vectors(doc_meta, content)
                            newly_indexed_count += 1

                        else:
                            # Check if file has modified size or mtime
                            prev = existing_db_docs[doc_id]
                            size_changed = prev["size"] != file_size
                            mtime_changed = abs(prev["modified_time"] - file_mtime) > 0.001

                            if size_changed or mtime_changed:
                                # 2. MODIFIED FILE
                                content = self.extractor_fn(resolved_path) if extract_content else None
                                doc_meta = DocumentMetadata(
                                    doc_id=doc_id,
                                    name=resolved_path.name,
                                    path=str(resolved_path),
                                    extension=resolved_path.suffix.lower(),
                                    folder=resolved_path.parent.name,
                                    size=file_size,
                                    modified_time=file_mtime,
                                    indexed_time=time.time(),
                                    content=content
                                )
                                upsert_document(doc_meta, self.db_path)
                                if self.vector_store and content:
                                    self.vector_store.upsert_document_vectors(doc_meta, content)
                                updated_count += 1
                            else:
                                # 3. UNCHANGED FILE - SKIP text extraction, SQLite update & vector embedding!
                                skipped_count += 1

                    except (PermissionError, OSError, ValueError):
                        # Skip unreadable or deleted individual files mid-scan safely
                        continue

            except (PermissionError, OSError):
                # Skip inaccessible directories safely
                continue

        # 4. DELETED FILES: Any doc in SQLite that was not discovered in this scan
        for db_doc_id in list(existing_db_docs.keys()):
            if db_doc_id not in discovered_doc_ids:
                delete_document(db_doc_id, self.db_path)
                if self.vector_store:
                    self.vector_store.delete_document_vectors(db_doc_id)
                deleted_count += 1

        elapsed = time.time() - start_time

        return {
            "total_discovered": total_discovered,
            "newly_indexed": newly_indexed_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "deleted": deleted_count,
            "elapsed_seconds": round(elapsed, 4)
        }
