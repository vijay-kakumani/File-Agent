import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database, upsert_document
from app.models import DocumentMetadata, generate_canonical_doc_id
from app.search.ranker import (
    MultiSignalRanker,
    RankerConfig,
    ConfidenceLevel,
    RankedCandidate,
    CandidateSignals,
)
from file_search import search_documents, search_files


class TestMultiSignalRanker(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_ranker.db"
        initialize_database(self.db_path)

        self.ranker = MultiSignalRanker()

        # Seed test documents in SQLite
        self.doc_nikhil = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/docs/Nikhil CS.pdf")),
            name="Nikhil CS.pdf",
            path=str(Path("/docs/Nikhil CS.pdf").resolve()),
            extension=".pdf",
            folder="docs",
            size=1024,
            modified_time=1000.0,
            indexed_time=1000.0,
            content="Nikhil CS resume detailing Python skills and computer science degree.",
        )
        self.doc_resume_downloads = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/downloads/Resume.pdf")),
            name="Resume.pdf",
            path=str(Path("/downloads/Resume.pdf").resolve()),
            extension=".pdf",
            folder="downloads",
            size=2048,
            modified_time=1000.0,
            indexed_time=1000.0,
            content="Professional software engineer resume.",
        )
        self.doc_resume_college = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/college/Resume.pdf")),
            name="Resume.pdf",
            path=str(Path("/college/Resume.pdf").resolve()),
            extension=".pdf",
            folder="college",
            size=2048,
            modified_time=1050.0,
            indexed_time=1050.0,
            content="College internship resume.",
        )
        self.doc_resume_notes = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/unrelated/ResumeNotes.txt")),
            name="ResumeNotes.txt",
            path=str(Path("/unrelated/ResumeNotes.txt").resolve()),
            extension=".txt",
            folder="unrelated",
            size=512,
            modified_time=900.0,
            indexed_time=900.0,
            content="Tips on how to write a software resume.",
        )
        self.doc_random_in_resume = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/Resume/Random.pdf")),
            name="Random.pdf",
            path=str(Path("/Resume/Random.pdf").resolve()),
            extension=".pdf",
            folder="Resume",
            size=4096,
            modified_time=800.0,
            indexed_time=800.0,
            content="Unrelated random presentation slides.",
        )
        self.doc_agile_mid1 = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/college/Agile Methodologies Mid1.pdf")),
            name="Agile Methodologies Mid1.pdf",
            path=str(Path("/college/Agile Methodologies Mid1.pdf").resolve()),
            extension=".pdf",
            folder="college",
            size=3072,
            modified_time=1100.0,
            indexed_time=1100.0,
            content="Midterm exam document covering Agile methodologies, sprint backlog, and Scrum rules.",
        )
        self.doc_random_in_agile = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("/Agile Methodologies/RandomNotes.pdf")),
            name="RandomNotes.pdf",
            path=str(Path("/Agile Methodologies/RandomNotes.pdf").resolve()),
            extension=".pdf",
            folder="Agile Methodologies",
            size=1024,
            modified_time=700.0,
            indexed_time=700.0,
            content="Scratchpad notes.",
        )

        self.all_test_docs = [
            self.doc_nikhil,
            self.doc_resume_downloads,
            self.doc_resume_college,
            self.doc_resume_notes,
            self.doc_random_in_resume,
            self.doc_agile_mid1,
            self.doc_random_in_agile,
        ]

        for doc in self.all_test_docs:
            upsert_document(doc, db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_filename_ranking(self):
        res = self.ranker.search("Resume.pdf", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Resume.pdf")
        self.assertTrue(res.top_candidate.signals.exact_filename_match)
        self.assertGreaterEqual(res.top_candidate.score, 85.0)

    def test_exact_stem_ranking(self):
        res = self.ranker.search("Resume", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Resume.pdf")
        self.assertTrue(res.top_candidate.signals.exact_stem_match)
        self.assertGreaterEqual(res.top_candidate.score, 85.0)

    def test_typo_filename_ranking(self):
        res = self.ranker.search("Nikil CS", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Nikhil CS.pdf")
        self.assertGreaterEqual(res.top_candidate.signals.stem_score, 80.0)

    def test_partial_filename_ranking(self):
        res = self.ranker.search("Nikhil", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Nikhil CS.pdf")

    def test_multi_word_typo_ranking(self):
        res = self.ranker.search("Agile metodologies", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Agile Methodologies Mid1.pdf")

    def test_folder_affinity(self):
        res = self.ranker.search("college resume", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.path, self.doc_resume_college.path)

    def test_folder_only_false_positive_protection_TEST_A(self):
        """
        TEST A:
        Query: "resume"
        Candidate A: Resume.pdf (folder: downloads)
        Candidate B: ResumeNotes.txt (folder: unrelated)
        Candidate C: Random.pdf (folder: Resume)

        Candidate A & B MUST outrank Candidate C because actual document name is relevant.
        """
        res = self.ranker.search("resume", db_path=self.db_path)
        candidate_paths = [c.path for c in res.candidates]

        self.assertIn(self.doc_resume_downloads.path, candidate_paths)
        self.assertIn(self.doc_resume_notes.path, candidate_paths)

        pos_a = candidate_paths.index(self.doc_resume_downloads.path)
        pos_b = candidate_paths.index(self.doc_resume_notes.path)

        if self.doc_random_in_resume.path in candidate_paths:
            pos_c = candidate_paths.index(self.doc_random_in_resume.path)
            self.assertLess(pos_a, pos_c, "Resume.pdf must outrank Random.pdf in folder Resume")
            self.assertLess(pos_b, pos_c, "ResumeNotes.txt must outrank Random.pdf in folder Resume")

    def test_folder_only_false_positive_protection_TEST_B(self):
        """
        TEST B:
        Query: "agile methodologies"
        Candidate A: Agile Methodologies Mid1.pdf (folder: college)
        Candidate B: RandomNotes.pdf (folder: Agile Methodologies)

        Candidate A MUST outrank Candidate B.
        """
        res = self.ranker.search("agile methodologies", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Agile Methodologies Mid1.pdf")
        self.assertGreater(res.candidates[0].score, res.candidates[1].score)

    def test_extension_filtering(self):
        res_pdf = self.ranker.search("resume", extension_filter=".pdf", db_path=self.db_path)
        for cand in res_pdf.candidates:
            self.assertEqual(cand.extension.lower(), ".pdf")

        res_txt = self.ranker.search("resume", extension_filter="txt", db_path=self.db_path)
        for cand in res_txt.candidates:
            self.assertEqual(cand.extension.lower(), ".txt")

    def test_fts5_relevance_contribution(self):
        res = self.ranker.search("sprint backlog", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Agile Methodologies Mid1.pdf")
        self.assertGreater(res.top_candidate.signals.fts_score, 0.0)

    def test_exact_filename_vs_folder_only_candidate(self):
        res = self.ranker.search("Resume.pdf", db_path=self.db_path)
        self.assertEqual(res.candidates[0].name, "Resume.pdf")
        self.assertTrue(res.candidates[0].signals.exact_filename_match)

    def test_duplicate_filenames(self):
        res = self.ranker.search("Resume.pdf", db_path=self.db_path)
        doc_ids = [c.document_id for c in res.candidates]
        self.assertEqual(len(doc_ids), len(set(doc_ids)), "All candidate IDs must be unique")

        resume_cands = [c for c in res.candidates if c.name == "Resume.pdf"]
        self.assertGreaterEqual(len(resume_cands), 2, "Both Resume.pdf instances must be preserved")

    def test_ambiguous_candidates(self):
        # Two identical Resume.pdf files in downloads and college should produce AMBIGUOUS or HIGH confidence with small gap
        res = self.ranker.search("Resume.pdf", db_path=self.db_path)
        self.assertIn(res.confidence, [ConfidenceLevel.AMBIGUOUS, ConfidenceLevel.HIGH])

    def test_low_confidence_no_relevance(self):
        res = self.ranker.search("xyz999nonsense", db_path=self.db_path)
        self.assertEqual(res.confidence, ConfidenceLevel.LOW)
        if res.top_candidate:
            self.assertLess(res.top_candidate.score, self.ranker.config.low_confidence_threshold)

    def test_empty_candidate_list(self):
        empty_ranker = MultiSignalRanker()
        res = empty_ranker.rank_candidates("test", [])
        self.assertEqual(len(res), 0)

    def test_empty_query(self):
        res = self.ranker.search("", db_path=self.db_path)
        self.assertEqual(res.confidence, ConfidenceLevel.LOW)
        self.assertEqual(len(res.candidates), 0)

    def test_mixed_case_and_punctuation(self):
        res = self.ranker.search("NIKHIL_CS", db_path=self.db_path)
        self.assertIsNotNone(res.top_candidate)
        self.assertEqual(res.top_candidate.name, "Nikhil CS.pdf")

    def test_canonical_document_ids_preserved(self):
        res = self.ranker.search("Nikhil", db_path=self.db_path)
        self.assertTrue(len(res.candidates) > 0)
        self.assertIsNotNone(res.candidates[0].document_id)
        self.assertTrue(len(res.candidates[0].document_id) > 0)

    def test_zero_text_extraction_during_ranker_search(self):
        """
        INSTRUMENTED PROOF:
        Verifies zero disk text extractions occur during ranker search.
        """
        with patch("file_search.read_file") as mock_read_file, \
             patch("file_search.read_pdf") as mock_read_pdf, \
             patch("file_search.read_docx") as mock_read_docx:

            res1 = self.ranker.search("Nikil CS", db_path=self.db_path)
            res2 = self.ranker.search("resume", db_path=self.db_path)
            res3 = search_documents("Agile metodologies")

            self.assertEqual(mock_read_file.call_count, 0)
            self.assertEqual(mock_read_pdf.call_count, 0)
            self.assertEqual(mock_read_docx.call_count, 0)

            self.assertTrue(len(res1.candidates) > 0)
            self.assertTrue(len(res2.candidates) > 0)
            self.assertTrue(len(res3) > 0)


if __name__ == "__main__":
    unittest.main()
