import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import get_active_search_roots
from app.db import initialize_database, upsert_document
from app.models import DocumentMetadata, generate_canonical_doc_id
from app.search import FuzzyEngine, normalize_text
from file_search import search_files, search_documents, read_file


class TestFuzzySearch(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_fuzzy.db"
        initialize_database(self.db_path)

        # Create sample documents metadata in test SQLite DB
        self.docs = [
            DocumentMetadata(
                doc_id=generate_canonical_doc_id(Path("/docs/Nikhil CS.pdf")),
                name="Nikhil CS.pdf",
                path=str(Path("/docs/Nikhil CS.pdf").resolve()),
                extension=".pdf",
                folder="docs",
                size=1024,
                modified_time=1000.0,
                indexed_time=1000.0,
                content="Nikhil resume document detailing Python skills and computer science degree.",
            ),
            DocumentMetadata(
                doc_id=generate_canonical_doc_id(Path("/downloads/resume.docx")),
                name="resume.docx",
                path=str(Path("/downloads/resume.docx").resolve()),
                extension=".docx",
                folder="downloads",
                size=2048,
                modified_time=1000.0,
                indexed_time=1000.0,
                content="Professional resume for software developer.",
            ),
            DocumentMetadata(
                doc_id=generate_canonical_doc_id(Path("/work/Agile Methodologies.pdf")),
                name="Agile Methodologies.pdf",
                path=str(Path("/work/Agile Methodologies.pdf").resolve()),
                extension=".pdf",
                folder="work",
                size=4096,
                modified_time=1000.0,
                indexed_time=1000.0,
                content="Guide to Agile methodologies, sprint planning, and Scrum software development.",
            ),
            DocumentMetadata(
                doc_id=generate_canonical_doc_id(Path("/college/internship/report.pdf")),
                name="report.pdf",
                path=str(Path("/college/internship/report.pdf").resolve()),
                extension=".pdf",
                folder="college/internship",
                size=8192,
                modified_time=1000.0,
                indexed_time=1000.0,
                content="College internship project report on machine learning.",
            ),
            DocumentMetadata(
                doc_id=generate_canonical_doc_id(Path("/backup/resume.docx")),
                name="resume.docx",
                path=str(Path("/backup/resume.docx").resolve()),
                extension=".docx",
                folder="backup",
                size=2048,
                modified_time=900.0,
                indexed_time=900.0,
                content="Old backup resume file.",
            ),
        ]

        for doc in self.docs:
            upsert_document(doc, db_path=self.db_path)

        self.engine = FuzzyEngine()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_text_normalization(self):
        self.assertEqual(normalize_text("Nikhil_CS-Resume.pdf"), "nikhil cs resume pdf")
        self.assertEqual(normalize_text("  Path/To\\File.docx  "), "path to file docx")
        self.assertEqual(normalize_text(""), "")

    def test_exact_filename_match(self):
        results = self.engine.search_candidates("Nikhil CS.pdf", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "Nikhil CS.pdf")
        self.assertGreaterEqual(results[0].overall_score, 90.0)

    def test_one_char_typo(self):
        # "Nikil CS" -> "Nikhil CS.pdf"
        results = self.engine.search_candidates("Nikil CS", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "Nikhil CS.pdf")
        self.assertGreaterEqual(results[0].overall_score, 80.0)

    def test_missing_character(self):
        # "resme" -> "resume.docx"
        results = self.engine.search_candidates("resme", self.docs)
        self.assertTrue(len(results) > 0)
        matched_names = [r.document.name for r in results]
        self.assertIn("resume.docx", matched_names)

    def test_extra_character(self):
        # "reportt" -> "report.pdf"
        results = self.engine.search_candidates("reportt", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "report.pdf")

    def test_transposed_character(self):
        # "metodologies" -> "Agile Methodologies.pdf"
        results = self.engine.search_candidates("metodologies", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "Agile Methodologies.pdf")

    def test_partial_filename(self):
        # "Nikhil" -> "Nikhil CS.pdf"
        results = self.engine.search_candidates("Nikhil", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "Nikhil CS.pdf")

    def test_multi_word_typo(self):
        # "Agile metodologies" -> "Agile Methodologies.pdf"
        results = self.engine.search_candidates("Agile metodologies", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "Agile Methodologies.pdf")

    def test_folder_name_fuzzy(self):
        # "college internship" -> report.pdf in folder "college/internship"
        results = self.engine.search_candidates("college internship", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "report.pdf")

    def test_duplicate_filenames(self):
        # "resume" should match both resume.docx files in downloads and backup
        results = self.engine.search_candidates("resume", self.docs)
        names = [r.document.name for r in results]
        self.assertEqual(names.count("resume.docx"), 2)

    def test_below_threshold_query(self):
        results = self.engine.search_candidates("xyz999nonsense", self.docs, threshold=60.0)
        self.assertEqual(len(results), 0)

    def test_empty_query(self):
        results = self.engine.search_candidates("", self.docs)
        self.assertEqual(len(results), 0)

    def test_case_and_punctuation_normalization(self):
        results = self.engine.search_candidates("nikhil_cs", self.docs)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].document.name, "Nikhil CS.pdf")

    def test_zero_text_extraction_during_fuzzy_search(self):
        """
        INSTRUMENTED PROOF:
        Verifies that executing fuzzy queries calls text extraction / disk read 0 times.
        """
        with patch("file_search.read_file") as mock_read_file, \
             patch("file_search.read_pdf") as mock_read_pdf, \
             patch("file_search.read_docx") as mock_read_docx, \
             patch("app.db.get_all_documents", return_value=self.docs):

            res1 = search_files("Nikil CS")
            res2 = search_files("resme")
            res3 = search_files("Agile metodologies")
            res4 = search_documents("college internship")

            self.assertEqual(mock_read_file.call_count, 0)
            self.assertEqual(mock_read_pdf.call_count, 0)
            self.assertEqual(mock_read_docx.call_count, 0)

            self.assertTrue(len(res1) > 0)
            self.assertTrue(len(res2) > 0)
            self.assertTrue(len(res3) > 0)
            self.assertTrue(len(res4) > 0)


if __name__ == "__main__":
    unittest.main()
