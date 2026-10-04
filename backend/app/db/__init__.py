from app.db.database import get_db_connection, verify_fts5_support, initialize_database
from app.db.fts_index import (
    upsert_document,
    delete_document,
    get_document_by_id,
    get_document_by_path,
    search_filename_fts,
    search_content_fts,
    search_all_fts,
    get_all_documents,
    get_document_count,
)

__all__ = [
    "get_db_connection",
    "verify_fts5_support",
    "initialize_database",
    "upsert_document",
    "delete_document",
    "get_document_by_id",
    "get_document_by_path",
    "search_filename_fts",
    "search_content_fts",
    "search_all_fts",
    "get_all_documents",
    "get_document_count",
]
