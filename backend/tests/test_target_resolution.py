import tempfile
import unittest
from pathlib import Path

from app.db import initialize_database, upsert_document
from app.models import DocumentMetadata, generate_canonical_doc_id
from app.services.state_service import state_service
from app.agent.target_resolver import (
    TargetResolver,
    ResolvedTargetType,
    SHORTHAND_EXPANSIONS,
    matches_path_hierarchy,
)


class TestTargetResolution(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_target_resolution.db"
        initialize_database(self.db_path)

        state_service.clear_active_document()

        # Seed realistic metadata candidates
        self.doc_resume_downloads = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("C:/Downloads/Resume.pdf")),
            name="Resume.pdf",
            path=str(Path("C:/Downloads/Resume.pdf")),
            extension=".pdf",
            folder="Downloads",
            size=1024,
            modified_time=1000.0,
            content="Resume detailing software engineering experience.",
        )
        self.doc_vijay_resume = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("C:/Downloads/Vijay_Resume.pdf")),
            name="Vijay_Resume.pdf",
            path=str(Path("C:/Downloads/Vijay_Resume.pdf")),
            extension=".pdf",
            folder="Downloads",
            size=2048,
            modified_time=1000.0,
            content="Vijay resume detailing Python, JavaScript, and React.",
        )
        self.doc_internship = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("C:/Documents/College/4th_Year/Internship/Internship_Report.pdf")),
            name="Internship_Report.pdf",
            path=str(Path("C:/Documents/College/4th_Year/Internship/Internship_Report.pdf")),
            extension=".pdf",
            folder="Internship",
            size=4096,
            modified_time=1000.0,
            content="Final internship report detailing 8 weeks internship and 40% latency reduction.",
        )
        self.doc_internship_external = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("D:/College/4th_Year/Internship/Internship_Report_External.pdf")),
            name="Internship_Report_External.pdf",
            path=str(Path("D:/College/4th_Year/Internship/Internship_Report_External.pdf")),
            extension=".pdf",
            folder="Internship",
            size=4096,
            modified_time=1000.0,
            content="External 12-week internship at partner research lab.",
        )
        self.doc_campusconnect = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("C:/Downloads/CampusConnect_Report.pdf")),
            name="CampusConnect_Report.pdf",
            path=str(Path("C:/Downloads/CampusConnect_Report.pdf")),
            extension=".pdf",
            folder="Downloads",
            size=3072,
            modified_time=1000.0,
            content="CampusConnect university student collaboration platform with FastAPI and React.",
        )
        self.doc_agile = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("D:/College/Agile/Agile_Methodologies.docx")),
            name="Agile_Methodologies.docx",
            path=str(Path("D:/College/Agile/Agile_Methodologies.docx")),
            extension=".docx",
            folder="Agile",
            size=2048,
            modified_time=1000.0,
            content="Scrum guide, sprint retrospectives, daily standups, and 2-week sprint cycles.",
        )
        self.doc_ml_notes = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path("D:/Projects/Python/Machine_Learning_Notes.txt")),
            name="Machine_Learning_Notes.txt",
            path=str(Path("D:/Projects/Python/Machine_Learning_Notes.txt")),
            extension=".txt",
            folder="Python",
            size=1024,
            modified_time=1000.0,
            content="Machine learning fundamentals, linear regression, gradient descent loss function.",
        )

        self.all_docs = [
            self.doc_resume_downloads,
            self.doc_vijay_resume,
            self.doc_internship,
            self.doc_internship_external,
            self.doc_campusconnect,
            self.doc_agile,
            self.doc_ml_notes,
        ]

        for doc in self.all_docs:
            upsert_document(doc, db_path=self.db_path)

        self.resolver = TargetResolver(db_path=self.db_path)

    def tearDown(self):
        state_service.clear_active_document()
        self.temp_dir.cleanup()

    def test_explicit_filename(self):
        res = self.resolver.resolve_reference("Machine_Learning_Notes.txt", db_path=self.db_path)
        self.assertEqual(res.target_type, ResolvedTargetType.DOCUMENT_REFERENCE)
        self.assertEqual(res.document_name, "Machine_Learning_Notes.txt")
        self.assertFalse(res.is_ambiguous)

    def test_cv_shorthand(self):
        res = self.resolver.resolve_reference("my cv", db_path=self.db_path)
        self.assertIn(res.target_type, [ResolvedTargetType.DOCUMENT_REFERENCE, ResolvedTargetType.MULTIPLE_DOCUMENTS])
        self.assertIn("Resume.pdf", [c.name for c in res.candidates])

    def test_internship_report_resolution(self):
        res = self.resolver.resolve_reference("internship report", db_path=self.db_path)
        self.assertIn(res.target_type, [ResolvedTargetType.DOCUMENT_REFERENCE, ResolvedTargetType.MULTIPLE_DOCUMENTS])
        self.assertIn("Internship_Report.pdf", [c.name for c in res.candidates])

    def test_campusconnect_document_resolution(self):
        res = self.resolver.resolve_reference("CampusConnect document", db_path=self.db_path)
        self.assertEqual(res.document_name, "CampusConnect_Report.pdf")

    def test_implicit_shorthand_ml_notes(self):
        res = self.resolver.resolve_reference("ml notes", db_path=self.db_path)
        self.assertEqual(res.document_name, "Machine_Learning_Notes.txt")

    def test_implicit_shorthand_agile_doc(self):
        res = self.resolver.resolve_reference("agile doc", db_path=self.db_path)
        self.assertEqual(res.document_name, "Agile_Methodologies.docx")

    def test_active_document_resolution(self):
        state_service.set_active_document(Path(self.doc_agile.path))
        res = self.resolver.resolve_reference("", db_path=self.db_path)
        self.assertEqual(res.target_type, ResolvedTargetType.CURRENT_DOCUMENT)
        self.assertEqual(res.document_name, "Agile_Methodologies.docx")

    def test_pronoun_reference_with_active_doc(self):
        state_service.set_active_document(Path(self.doc_campusconnect.path))
        for pronoun in ["it", "that", "this document", "that file", "the document"]:
            res = self.resolver.resolve_reference(pronoun, db_path=self.db_path)
            self.assertEqual(res.target_type, ResolvedTargetType.CURRENT_DOCUMENT)
            self.assertEqual(res.document_name, "CampusConnect_Report.pdf")

    def test_pronoun_reference_without_active_doc(self):
        state_service.clear_active_document()
        res = self.resolver.resolve_reference("it", db_path=self.db_path)
        self.assertEqual(res.target_type, ResolvedTargetType.NOT_FOUND)

    def test_ambiguous_reference_preserves_ambiguity(self):
        # Multiple resumes exist in the corpus (Resume.pdf and Vijay_Resume.pdf)
        res = self.resolver.resolve_reference("resume", db_path=self.db_path)
        self.assertTrue(res.is_ambiguous or len(res.candidates) > 1)
        cand_names = [c.name for c in res.candidates]
        self.assertIn("Resume.pdf", cand_names)
        self.assertIn("Vijay_Resume.pdf", cand_names)

    def test_unknown_reference(self):
        res = self.resolver.resolve_reference("nonexistent_random_doc_xyz123", db_path=self.db_path)
        self.assertEqual(res.target_type, ResolvedTargetType.NOT_FOUND)

    def test_deep_path_matching_hierarchy(self):
        # Assert D: drive hierarchical match
        cand = "D:/College/4th_Year/Internship/Internship_Report_External.pdf"
        self.assertTrue(matches_path_hierarchy(cand, folder_constraint="D:\\College\\4th_Year\\Internship"))
        self.assertTrue(matches_path_hierarchy(cand, folder_constraint="College/4th_Year/Internship"))
        self.assertTrue(matches_path_hierarchy(cand, drive_constraint="D"))
        # Should not match C: drive constraint
        self.assertFalse(matches_path_hierarchy(cand, drive_constraint="C"))


if __name__ == "__main__":
    unittest.main()
