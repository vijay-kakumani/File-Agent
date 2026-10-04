import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.db.database import get_db_connection
from app.models.document import DocumentMetadata, generate_canonical_doc_id


def upsert_document(doc: DocumentMetadata, db_path: Path = None) -> DocumentMetadata:
    """
    Inserts or updates document metadata in 'documents' table and updates
    'documents_fts' virtual table in a single atomic SQLite transaction.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            # 1. Upsert metadata table
            conn.execute(
                """
                INSERT INTO documents (doc_id, name, path, extension, folder, size, modified_time, indexed_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    name = excluded.name,
                    path = excluded.path,
                    extension = excluded.extension,
                    folder = excluded.folder,
                    size = excluded.size,
                    modified_time = excluded.modified_time,
                    indexed_time = excluded.indexed_time;
                """,
                (
                    doc.doc_id,
                    doc.name,
                    doc.path,
                    doc.extension,
                    doc.folder,
                    doc.size,
                    doc.modified_time,
                    doc.indexed_time,
                ),
            )

            # 2. Delete existing FTS record for this doc_id if present
            conn.execute("DELETE FROM documents_fts WHERE doc_id = ?;", (doc.doc_id,))

            # 3. Insert into FTS table
            conn.execute(
                """
                INSERT INTO documents_fts (doc_id, name, folder, path, content)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    doc.doc_id,
                    doc.name,
                    doc.folder,
                    doc.path,
                    doc.content or "",
                ),
            )
        return doc
    finally:
        conn.close()


def delete_document(doc_id_or_path: str, db_path: Path = None) -> bool:
    """
    Deletes a document from both metadata and FTS tables by ID or Path string.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            # Find doc_id if path string was provided
            cursor = conn.execute(
                "SELECT doc_id FROM documents WHERE doc_id = ? OR path = ?;",
                (doc_id_or_path, doc_id_or_path),
            )
            row = cursor.fetchone()
            if not row:
                return False

            doc_id = row["doc_id"]
            conn.execute("DELETE FROM documents WHERE doc_id = ?;", (doc_id,))
            conn.execute("DELETE FROM documents_fts WHERE doc_id = ?;", (doc_id,))
            return True
    finally:
        conn.close()


def get_document_by_id(doc_id: str, db_path: Path = None) -> Optional[DocumentMetadata]:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM documents WHERE doc_id = ?;", (doc_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Fetch content from FTS
        fts_cursor = conn.execute("SELECT content FROM documents_fts WHERE doc_id = ?;", (doc_id,))
        fts_row = fts_cursor.fetchone()
        content = fts_row["content"] if fts_row else None

        return DocumentMetadata(
            doc_id=row["doc_id"],
            name=row["name"],
            path=row["path"],
            extension=row["extension"],
            folder=row["folder"],
            size=row["size"],
            modified_time=row["modified_time"],
            indexed_time=row["indexed_time"],
            content=content,
        )
    finally:
        conn.close()


def get_document_by_path(file_path: Path, db_path: Path = None) -> Optional[DocumentMetadata]:
    doc_id = generate_canonical_doc_id(file_path)
    return get_document_by_id(doc_id, db_path)


def search_filename_fts(query: str, limit: int = 20, db_path: Path = None) -> List[DocumentMetadata]:
    """
    Full-Text Search matching filename.
    """
    sanitized_query = clean_fts_query(query)
    if not sanitized_query:
        return []

    conn = get_db_connection(db_path)
    try:
        sql = """
            SELECT d.*, fts.content, rank
            FROM documents_fts fts
            JOIN documents d ON d.doc_id = fts.doc_id
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
        """
        fts_match = f"name:{sanitized_query}*"
        cursor = conn.execute(sql, (fts_match, limit))
        rows = cursor.fetchall()
        return [row_to_document(row) for row in rows]
    except sqlite3.OperationalError:
        # Fallback to simple LIKE query if FTS match fails syntax
        like_query = f"%{query.strip()}%"
        sql = "SELECT d.*, NULL as content FROM documents d WHERE name LIKE ? LIMIT ?;"
        cursor = conn.execute(sql, (like_query, limit))
        return [row_to_document(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def search_content_fts(query: str, limit: int = 20, db_path: Path = None) -> List[DocumentMetadata]:
    """
    Full-Text Search matching document content.
    """
    sanitized_query = clean_fts_query(query)
    if not sanitized_query:
        return []

    conn = get_db_connection(db_path)
    try:
        sql = """
            SELECT d.*, fts.content, rank
            FROM documents_fts fts
            JOIN documents d ON d.doc_id = fts.doc_id
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
        """
        fts_match = f"content:{sanitized_query}*"
        cursor = conn.execute(sql, (fts_match, limit))
        return [row_to_document(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def search_all_fts(query: str, limit: int = 20, db_path: Path = None) -> List[DocumentMetadata]:
    """
    Combined FTS5 search matching name, folder, path, or content.
    """
    sanitized_query = clean_fts_query(query)
    if not sanitized_query:
        return []

    conn = get_db_connection(db_path)
    try:
        sql = """
            SELECT d.*, fts.content, rank
            FROM documents_fts fts
            JOIN documents d ON d.doc_id = fts.doc_id
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
        """
        # Search across all columns with prefix matching
        fts_match = f"{sanitized_query}*"
        cursor = conn.execute(sql, (fts_match, limit))
        rows = cursor.fetchall()

        if not rows:
            # Fallback to name search or simple LIKE
            return search_filename_fts(query, limit, db_path)

        return [row_to_document(row) for row in rows]
    except sqlite3.OperationalError:
        return search_filename_fts(query, limit, db_path)
    finally:
        conn.close()


def get_all_documents(limit: int = 100, db_path: Path = None) -> List[DocumentMetadata]:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("SELECT *, NULL as content FROM documents ORDER BY indexed_time DESC LIMIT ?;", (limit,))
        return [row_to_document(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_document_count(db_path: Path = None) -> int:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) as count FROM documents;")
        row = cursor.fetchone()
        return row["count"] if row else 0
    finally:
        conn.close()


def clean_fts_query(query: str) -> str:
    """
    Sanitizes user input string for safe SQLite FTS5 MATCH expressions.
    Removes quotes, colons, AND, OR, NOT operators.
    """
    cleaned = "".join([c if c.isalnum() or c in (" ", "-", "_") else " " for c in query])
    words = [w for w in cleaned.strip().split() if w.lower() not in ("and", "or", "not")]
    return " ".join(words)


def row_to_document(row: sqlite3.Row) -> DocumentMetadata:
    return DocumentMetadata(
        doc_id=row["doc_id"],
        name=row["name"],
        path=row["path"],
        extension=row["extension"],
        folder=row["folder"],
        size=row["size"],
        modified_time=row["modified_time"],
        indexed_time=row["indexed_time"],
        content=row["content"] if "content" in row.keys() else None,
    )
