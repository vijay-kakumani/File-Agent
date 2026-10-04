import unittest
import tempfile
import time
from pathlib import Path
import os
import sys
import shutil

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import initialize_database, get_db_connection
from app.db.fts_index import get_document_count, get_document_by_path, get_document_by_id
from app.indexing.incremental_indexer import IncrementalIndexer
from app.models.document import DocumentMetadata


class TestPhase3IncrementalIndexing(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "test_incremental.db"
        initialize_database(self.db_path)

        # Track text extraction calls to prove unchanged files skip text extraction
        self.extraction_calls = []

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def mock_extractor(self, file_path: Path) -> str:
        self.extraction_calls.append(str(file_path))
        return f"Content of {file_path.name}"

    def test_01_new_file_gets_indexed(self):
        """Phase 3 Test 1: New file gets indexed on first run."""
        f1 = self.test_dir / "doc1.txt"
        f1.write_text("Hello World", encoding="utf-8")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)
        stats = indexer.scan_and_index(custom_roots=[self.test_dir])

        self.assertEqual(stats["total_discovered"], 1)
        self.assertEqual(stats["newly_indexed"], 1)
        self.assertEqual(stats["skipped"], 0)
        self.assertEqual(stats["updated"], 0)
        self.assertEqual(stats["deleted"], 0)
        self.assertEqual(len(self.extraction_calls), 1)

    def test_02_unchanged_file_is_skipped(self):
        """Phase 3 Test 2: Unchanged file is skipped and text extraction is NOT re-triggered."""
        f1 = self.test_dir / "doc1.pdf"
        f1.write_text("PDF content", encoding="utf-8")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)

        # 1st run
        stats1 = indexer.scan_and_index(custom_roots=[self.test_dir])
        self.assertEqual(stats1["newly_indexed"], 1)
        self.assertEqual(len(self.extraction_calls), 1)

        # Reset extraction call log
        self.extraction_calls.clear()

        # 2nd run with NO changes
        stats2 = indexer.scan_and_index(custom_roots=[self.test_dir])
        self.assertEqual(stats2["total_discovered"], 1)
        self.assertEqual(stats2["newly_indexed"], 0)
        self.assertEqual(stats2["skipped"], 1)
        self.assertEqual(stats2["updated"], 0)
        self.assertEqual(stats2["deleted"], 0)
        # PROOF: extraction function was called 0 times on unchanged run!
        self.assertEqual(len(self.extraction_calls), 0)

    def test_03_modified_file_is_reindexed(self):
        """Phase 3 Test 3: Modified file (mtime/size changed) is re-extracted and updated."""
        f1 = self.test_dir / "doc1.docx"
        f1.write_text("Version 1", encoding="utf-8")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)
        indexer.scan_and_index(custom_roots=[self.test_dir])

        self.extraction_calls.clear()
        time.sleep(0.02)  # ensure mtime changes

        # Modify file content & timestamp
        f1.write_text("Version 2 - Updated Content", encoding="utf-8")

        stats2 = indexer.scan_and_index(custom_roots=[self.test_dir])
        self.assertEqual(stats2["updated"], 1)
        self.assertEqual(stats2["skipped"], 0)
        self.assertEqual(len(self.extraction_calls), 1)

    def test_04_deleted_file_is_removed(self):
        """Phase 3 Test 4: Deleted file is removed from persistent index."""
        f1 = self.test_dir / "to_delete.md"
        f1.write_text("Delete me", encoding="utf-8")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)
        indexer.scan_and_index(custom_roots=[self.test_dir])
        self.assertEqual(get_document_count(self.db_path), 1)

        # Physically remove file
        f1.unlink()

        stats2 = indexer.scan_and_index(custom_roots=[self.test_dir])
        self.assertEqual(stats2["deleted"], 1)
        self.assertEqual(get_document_count(self.db_path), 0)

    def test_05_duplicate_filenames_separate(self):
        """Phase 3 Test 5: Duplicate filenames in different folders remain distinct."""
        subA = self.test_dir / "DirA"
        subB = self.test_dir / "DirB"
        subA.mkdir()
        subB.mkdir()

        fA = subA / "Report.pdf"
        fB = subB / "Report.pdf"
        fA.write_text("Dir A report", encoding="utf-8")
        fB.write_text("Dir B report", encoding="utf-8")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)
        stats = indexer.scan_and_index(custom_roots=[self.test_dir])

        self.assertEqual(stats["total_discovered"], 2)
        self.assertEqual(get_document_count(self.db_path), 2)

    def test_06_inaccessible_or_deleted_midscan_handled_safely(self):
        """Phase 3 Test 6: Safe error handling during indexing."""
        f1 = self.test_dir / "normal.txt"
        f1.write_text("Normal content", encoding="utf-8")

        def error_extractor(p: Path):
            if "normal" in p.name:
                return "Normal"
            raise PermissionError("Simulated read error")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=error_extractor)
        stats = indexer.scan_and_index(custom_roots=[self.test_dir])

        self.assertEqual(stats["total_discovered"], 1)

    def test_07_unsupported_extension_ignored(self):
        """Phase 3 Test 7: Unsupported file extensions (.py, .json, .exe) are ignored."""
        f1 = self.test_dir / "script.py"
        f2 = self.test_dir / "data.json"
        f3 = self.test_dir / "valid.txt"
        f1.write_text("print('hello')", encoding="utf-8")
        f2.write_text("{}", encoding="utf-8")
        f3.write_text("Valid text", encoding="utf-8")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)
        stats = indexer.scan_and_index(custom_roots=[self.test_dir])

        self.assertEqual(stats["total_discovered"], 1)
        self.assertEqual(get_document_count(self.db_path), 1)

    def test_08_restarting_application_preserves_index(self):
        """Phase 3 Test 8: Index persists across restarts and subsequent scan skips reprocessing."""
        f1 = self.test_dir / "persistent.pdf"
        f1.write_text("PDF content", encoding="utf-8")

        indexer1 = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)
        indexer1.scan_and_index(custom_roots=[self.test_dir])

        # Simulate restart with new indexer instance
        self.extraction_calls.clear()
        indexer2 = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)
        stats2 = indexer2.scan_and_index(custom_roots=[self.test_dir])

        self.assertEqual(stats2["skipped"], 1)
        self.assertEqual(len(self.extraction_calls), 0)

    def test_09_indexer_twice_no_reprocessing(self):
        """Phase 3 Test 9: Running indexer twice in succession reprocesses 0 documents."""
        f1 = self.test_dir / "docA.txt"
        f2 = self.test_dir / "docB.docx"
        f1.write_text("Content A", encoding="utf-8")
        f2.write_text("Content B", encoding="utf-8")

        indexer = IncrementalIndexer(db_path=self.db_path, extractor_fn=self.mock_extractor)

        s1 = indexer.scan_and_index(custom_roots=[self.test_dir])
        self.assertEqual(s1["newly_indexed"], 2)

        self.extraction_calls.clear()

        s2 = indexer.scan_and_index(custom_roots=[self.test_dir])
        self.assertEqual(s2["newly_indexed"], 0)
        self.assertEqual(s2["skipped"], 2)
        self.assertEqual(len(self.extraction_calls), 0)


if __name__ == "__main__":
    unittest.main()
