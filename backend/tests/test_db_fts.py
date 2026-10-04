import unittest
import tempfile
import time
from pathlib import Path
import os
import sys
import shutil

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import (
    DEFAULT_SEARCH_ROOTS,
    SUPPORTED_EXTENSIONS,
    get_active_search_roots,
    OLLAMA_MODEL,
    EMBEDDING_MODEL,
)
from app.db.database import (
    get_db_connection,
    verify_fts5_support,
    initialize_database,
)
from app.db.fts_index import (
    upsert_document,
    delete_document,
    get_document_by_id,
    get_document_by_path,
    search_filename_fts,
    search_content_fts,
    search_all_fts,
    get_document_count,
)
from app.models.document import DocumentMetadata, generate_canonical_doc_id


class TestPhase1And2(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for test database and files
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "test_agent_index.db"
        initialize_database(self.db_path)

    def tearDown(self):
        # Clean up temporary test directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_phase1_settings(self):
        """Phase 1: Test settings, search roots, supported extensions, model configs."""
        self.assertIn(".pdf", SUPPORTED_EXTENSIONS)
        self.assertIn(".docx", SUPPORTED_EXTENSIONS)
        self.assertIn(".txt", SUPPORTED_EXTENSIONS)
        self.assertIn(".md", SUPPORTED_EXTENSIONS)
        self.assertEqual(OLLAMA_MODEL, "qwen2.5:1.5b")
        self.assertEqual(EMBEDDING_MODEL, "all-MiniLM-L6-v2")

        active_roots = get_active_search_roots()
        self.assertTrue(isinstance(active_roots, list))
        for root in active_roots:
            self.assertTrue(root.exists())

    def test_02_fts5_verification(self):
        """Phase 2: Test FTS5 support verification and WAL mode."""
        conn = get_db_connection(self.db_path)
        self.assertTrue(verify_fts5_support(conn))
        cursor = conn.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        self.assertEqual(row[0].lower(), "wal")
        conn.close()

    def test_03_insert_document(self):
        """Phase 2: Test inserting a document into SQLite FTS5."""
        dummy_file = self.test_dir / "resume_nikhil.pdf"
        dummy_file.write_text("Nikhil software engineer python agile", encoding="utf-8")

        meta = DocumentMetadata.from_file_path(dummy_file, content="Nikhil software engineer python agile")
        upsert_document(meta, self.db_path)

        count = get_document_count(self.db_path)
        self.assertEqual(count, 1)

        fetched = get_document_by_id(meta.doc_id, self.db_path)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "resume_nikhil.pdf")
        self.assertEqual(fetched.content, "Nikhil software engineer python agile")

    def test_04_update_document(self):
        """Phase 2: Test updating an existing document metadata and content."""
        dummy_file = self.test_dir / "notes.txt"
        dummy_file.write_text("Version 1 content", encoding="utf-8")

        meta1 = DocumentMetadata.from_file_path(dummy_file, content="Version 1 content")
        upsert_document(meta1, self.db_path)

        # Update file content and mtime
        time.sleep(0.01)
        dummy_file.write_text("Version 2 updated content with agile methodologies", encoding="utf-8")
        meta2 = DocumentMetadata.from_file_path(dummy_file, content="Version 2 updated content with agile methodologies")

        upsert_document(meta2, self.db_path)

        # Ensure total count remains 1
        self.assertEqual(get_document_count(self.db_path), 1)

        fetched = get_document_by_path(dummy_file, self.db_path)
        self.assertEqual(fetched.content, "Version 2 updated content with agile methodologies")

    def test_05_delete_document(self):
        """Phase 2: Test deleting a document."""
        dummy_file = self.test_dir / "temp_doc.md"
        dummy_file.write_text("Temporary documentation", encoding="utf-8")

        meta = DocumentMetadata.from_file_path(dummy_file, content="Temporary documentation")
        upsert_document(meta, self.db_path)

        self.assertEqual(get_document_count(self.db_path), 1)

        success = delete_document(meta.doc_id, self.db_path)
        self.assertTrue(success)
        self.assertEqual(get_document_count(self.db_path), 0)
        self.assertIsNone(get_document_by_id(meta.doc_id, self.db_path))

    def test_06_filename_search_fts(self):
        """Phase 2: Test FTS5 filename search."""
        f1 = self.test_dir / "Nikhil_CS_Resume.pdf"
        f2 = self.test_dir / "Agile_Project_Report.docx"
        f1.write_text("Content 1", encoding="utf-8")
        f2.write_text("Content 2", encoding="utf-8")

        upsert_document(DocumentMetadata.from_file_path(f1, "Content 1"), self.db_path)
        upsert_document(DocumentMetadata.from_file_path(f2, "Content 2"), self.db_path)

        results = search_filename_fts("Nikhil", limit=10, db_path=self.db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Nikhil_CS_Resume.pdf")

    def test_07_content_search_fts(self):
        """Phase 2: Test FTS5 content search."""
        f1 = self.test_dir / "doc1.txt"
        f2 = self.test_dir / "doc2.txt"
        f1.write_text("Photosynthesis occurs in plants and chlorophyll.", encoding="utf-8")
        f2.write_text("Agile software development utilizes 2-week sprints.", encoding="utf-8")

        upsert_document(DocumentMetadata.from_file_path(f1, f1.read_text()), self.db_path)
        upsert_document(DocumentMetadata.from_file_path(f2, f2.read_text()), self.db_path)

        results = search_content_fts("sprints", limit=10, db_path=self.db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "doc2.txt")

    def test_08_folder_and_metadata(self):
        """Phase 2: Test folder and path metadata storing and filtering."""
        sub_dir = self.test_dir / "Downloads"
        sub_dir.mkdir(parents=True, exist_ok=True)
        f = sub_dir / "internship_report.pdf"
        f.write_text("Internship report details", encoding="utf-8")

        meta = DocumentMetadata.from_file_path(f, "Internship report details")
        upsert_document(meta, self.db_path)

        fetched = get_document_by_id(meta.doc_id, self.db_path)
        self.assertEqual(fetched.folder, "Downloads")
        self.assertTrue("Downloads" in fetched.path)

    def test_09_duplicate_filenames_different_directories(self):
        """Phase 2: Test duplicate filenames in different directories have unique canonical IDs."""
        dir1 = self.test_dir / "FolderA"
        dir2 = self.test_dir / "FolderB"
        dir1.mkdir(parents=True, exist_ok=True)
        dir2.mkdir(parents=True, exist_ok=True)

        f1 = dir1 / "Resume.pdf"
        f2 = dir2 / "Resume.pdf"
        f1.write_text("FolderA Resume", encoding="utf-8")
        f2.write_text("FolderB Resume", encoding="utf-8")

        m1 = DocumentMetadata.from_file_path(f1, "FolderA Resume")
        m2 = DocumentMetadata.from_file_path(f2, "FolderB Resume")

        self.assertNotEqual(m1.doc_id, m2.doc_id)

        upsert_document(m1, self.db_path)
        upsert_document(m2, self.db_path)

        self.assertEqual(get_document_count(self.db_path), 2)

        results = search_filename_fts("Resume", limit=10, db_path=self.db_path)
        self.assertEqual(len(results), 2)

    def test_10_database_persistence_across_reconnect(self):
        """Phase 2: Verify database persists across process/connection restarts."""
        f = self.test_dir / "persistent_file.md"
        f.write_text("Persistent content", encoding="utf-8")

        m = DocumentMetadata.from_file_path(f, "Persistent content")
        upsert_document(m, self.db_path)

        # Verify DB file exists on disk
        self.assertTrue(self.db_path.exists())

        # Simulate backend restart by re-initializing and querying database at db_path
        initialize_database(self.db_path)

        fetched = get_document_by_id(m.doc_id, self.db_path)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "persistent_file.md")


if __name__ == "__main__":
    unittest.main()
