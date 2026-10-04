import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models import DocumentMetadata, generate_canonical_doc_id
from app.rag.vector_store import VectorStore, chunk_text, VectorSearchResult
from app.indexing import IncrementalIndexer


class TestVectorStore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.chroma_dir = Path(self.temp_dir.name) / "test_chroma"
        self.db_path = Path(self.temp_dir.name) / "test_vector_db.db"

        self.store = VectorStore(chroma_dir=self.chroma_dir)

        # Sample document metadata entries
        self.doc_resume = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/downloads/Vijay_Resume.pdf")),
            name="Vijay_Resume.pdf",
            path=str(Path("/downloads/Vijay_Resume.pdf").resolve()),
            extension=".pdf",
            folder="downloads",
            size=2048,
            modified_time=1000.0,
            indexed_time=1000.0,
            content="Vijay Software Engineer CV detailing Python skills, machine learning, and computer science degree.",
        )

        self.doc_agile = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/work/Agile_Guide.docx")),
            name="Agile_Guide.docx",
            path=str(Path("/work/Agile_Guide.docx").resolve()),
            extension=".docx",
            folder="work",
            size=4096,
            modified_time=1000.0,
            indexed_time=1000.0,
            content="Guide to software project management, Scrum framework, sprint planning, and backlog refinement.",
        )

        self.doc_duplicate_resume = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/college/Vijay_Resume.pdf")),
            name="Vijay_Resume.pdf",
            path=str(Path("/college/Vijay_Resume.pdf").resolve()),
            extension=".pdf",
            folder="college",
            size=2048,
            modified_time=900.0,
            indexed_time=900.0,
            content="College internship resume for software roles.",
        )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_persistent_collection_creation(self):
        self.assertIsNotNone(self.store._collection)
        self.assertEqual(self.store._collection.name, "documents")

    def test_document_indexing(self):
        chunks_added = self.store.upsert_document_vectors(self.doc_resume)
        self.assertGreater(chunks_added, 0)
        self.assertEqual(self.store.get_document_chunk_count(self.doc_resume.doc_id), chunks_added)

    def test_chunk_metadata(self):
        self.store.upsert_document_vectors(self.doc_resume)
        results = self.store.search_semantic("Python skills", document_id=self.doc_resume.doc_id)
        self.assertTrue(len(results) > 0)

        meta = results[0].metadata
        self.assertEqual(meta.get("document_id"), self.doc_resume.doc_id)
        self.assertEqual(meta.get("document_name"), self.doc_resume.name)
        self.assertEqual(meta.get("absolute_path"), self.doc_resume.path)
        self.assertEqual(meta.get("folder"), self.doc_resume.folder)
        self.assertIn("chunk_index", meta)

    def test_stable_chunk_ids(self):
        self.store.upsert_document_vectors(self.doc_resume)
        raw_items = self.store._collection.get(where={"document_id": self.doc_resume.doc_id})
        ids = raw_items.get("ids", [])
        self.assertTrue(len(ids) > 0)
        for idx, chunk_id in enumerate(ids):
            self.assertEqual(chunk_id, f"{self.doc_resume.doc_id}_chunk_{idx}")

    def test_duplicate_filenames(self):
        self.store.upsert_document_vectors(self.doc_resume)
        self.store.upsert_document_vectors(self.doc_duplicate_resume)

        count_downloads = self.store.get_document_chunk_count(self.doc_resume.doc_id)
        count_college = self.store.get_document_chunk_count(self.doc_duplicate_resume.doc_id)

        self.assertGreater(count_downloads, 0)
        self.assertGreater(count_college, 0)
        self.assertNotEqual(self.doc_resume.doc_id, self.doc_duplicate_resume.doc_id)

    def test_semantic_query_returns_expected_document(self):
        self.store.upsert_document_vectors(self.doc_resume)
        self.store.upsert_document_vectors(self.doc_agile)

        res_cv = self.store.search_semantic("my CV")
        self.assertTrue(len(res_cv) > 0)
        self.assertEqual(res_cv[0].document_name, "Vijay_Resume.pdf")

        res_scrum = self.store.search_semantic("software project management")
        self.assertTrue(len(res_scrum) > 0)
        self.assertEqual(res_scrum[0].document_name, "Agile_Guide.docx")

    def test_document_specific_filtering(self):
        self.store.upsert_document_vectors(self.doc_resume)
        self.store.upsert_document_vectors(self.doc_agile)

        results = self.store.search_semantic("scrum", document_id=self.doc_agile.doc_id)
        self.assertTrue(len(results) > 0)
        for r in results:
            self.assertEqual(r.document_id, self.doc_agile.doc_id)

    def test_document_modification_updates_vectors(self):
        self.store.upsert_document_vectors(self.doc_resume)
        initial_count = self.store.get_document_chunk_count(self.doc_resume.doc_id)

        # Updated text content
        updated_meta = DocumentMetadata(
            doc_id=self.doc_resume.doc_id,
            name=self.doc_resume.name,
            path=self.doc_resume.path,
            extension=self.doc_resume.extension,
            folder=self.doc_resume.folder,
            size=4096,
            modified_time=2000.0,
            indexed_time=2000.0,
            content="Updated CV text describing cloud computing, AWS, and Docker skills.",
        )
        self.store.upsert_document_vectors(updated_meta)

        res = self.store.search_semantic("cloud computing")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0].document_name, "Vijay_Resume.pdf")

    def test_document_deletion_removes_vectors(self):
        self.store.upsert_document_vectors(self.doc_resume)
        self.assertGreater(self.store.get_document_chunk_count(self.doc_resume.doc_id), 0)

        self.store.delete_document_vectors(self.doc_resume.doc_id)
        self.assertEqual(self.store.get_document_chunk_count(self.doc_resume.doc_id), 0)

    def test_persistence_after_process_restart(self):
        """
        PROCESS RESTART TEST:
        Indexes vector in process A instance, closes, re-opens process B instance,
        and verifies vectors persist.
        """
        store_a = VectorStore(chroma_dir=self.chroma_dir)
        store_a.upsert_document_vectors(self.doc_resume)
        del store_a

        # Re-open vector store on same path (simulating restart)
        store_b = VectorStore(chroma_dir=self.chroma_dir)
        res = store_b.search_semantic("my CV")

        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0].document_name, "Vijay_Resume.pdf")

    def test_unchanged_document_does_not_regenerate_embeddings(self):
        """
        INSTRUMENTED PROOF:
        Verifies that scanning an unchanged document in IncrementalIndexer calls embedding generation 0 times.
        """
        # Create a test file in temp directory
        test_file = Path(self.temp_dir.name) / "TestDoc.txt"
        test_file.write_text("Sample text for incremental indexing test.", encoding="utf-8")

        indexer = IncrementalIndexer(
            db_path=self.db_path,
            chroma_dir=self.chroma_dir,
            enable_vectors=True
        )

        # Pass 1: New file -> should extract and embed
        res1 = indexer.scan_and_index(custom_roots=[Path(self.temp_dir.name)])
        self.assertEqual(res1["newly_indexed"], 1)

        # Pass 2: Unchanged file -> patch encode to verify 0 calls!
        with patch.object(indexer.vector_store.model, "encode") as mock_encode:
            res2 = indexer.scan_and_index(custom_roots=[Path(self.temp_dir.name)])
            self.assertEqual(res2["skipped"], 1)
            self.assertEqual(mock_encode.call_count, 0)

    def test_failed_embedding_generation_handled_safely(self):
        with patch.object(self.store.model, "encode", side_effect=RuntimeError("Embedding failure")):
            res = self.store.upsert_document_vectors(self.doc_resume)
            self.assertEqual(res, 0)

    def test_empty_query_handling(self):
        res = self.store.search_semantic("")
        self.assertEqual(len(res), 0)

    def test_empty_collection_handling(self):
        empty_dir = Path(self.temp_dir.name) / "empty_chroma"
        empty_store = VectorStore(chroma_dir=empty_dir)
        res = empty_store.search_semantic("query")
        self.assertEqual(len(res), 0)


if __name__ == "__main__":
    unittest.main()
