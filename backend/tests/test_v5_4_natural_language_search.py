import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.agent.intent_parser import IntentParser, IntentType, TargetType, FollowUpAction
from app.agent.service import DocumentAgentService
from app.models import AgentResult, DocumentInfo
from app.services import state_service, document_service, search_service
from app.search import RankedCandidate, CandidateSignals
from app.models.document import DocumentMetadata


@pytest.fixture
def parser():
    return IntentParser()


@pytest.fixture
def service():
    return DocumentAgentService()


def test_v54_case_1_pdf_machine_learning(parser):
    """Case 1: Find the PDF about machine learning"""
    parsed = parser.parse("Find the PDF about machine learning")
    assert parsed.intent == IntentType.FIND
    assert parsed.extension_filter == ".pdf"
    assert parsed.query == "machine learning"


def test_v54_case_2_remember_internship(parser):
    """Case 2: I remember a document about my internship"""
    parsed = parser.parse("I remember a document about my internship")
    assert parsed.intent == IntentType.FIND
    assert parsed.query == "internship"


def test_v54_case_3_notes_normalization(parser):
    """Case 3: Find the notes where I discussed normalization"""
    parsed = parser.parse("Find the notes where I discussed normalization")
    assert parsed.intent == IntentType.FIND
    assert "normalization" in parsed.query
    assert "where i discussed" not in parsed.query.lower()


def test_v54_case_4_report_last_month(parser):
    """Case 4: That report I saved last month"""
    parsed = parser.parse("That report I saved last month")
    assert parsed.intent == IntentType.FIND
    assert parsed.date_constraint == "last month"
    assert parsed.query == "report"


def test_v54_case_5_file_from_downloads_agile(parser):
    """Case 5: The file from Downloads about agile"""
    parsed = parser.parse("The file from Downloads about agile")
    assert parsed.intent == IntentType.FIND
    assert parsed.folder_constraint == "Downloads"
    assert parsed.query == "agile"


def test_v54_case_6_open_document_we_just_found(parser, service, tmp_path):
    """Case 6: Open the document we just found -> opens active document"""
    fake_doc = tmp_path / "Active_Spec.pdf"
    fake_doc.write_text("dummy")
    state_service.set_active_document(fake_doc)

    parsed = parser.parse("Open the document we just found")
    assert parsed.intent == IntentType.OPEN
    assert parsed.target == TargetType.CURRENT_DOCUMENT

    with patch.object(document_service, "open_native_file") as mock_open:
        mock_open.return_value = f"Opened: {fake_doc.name}"
        res = service.execute_request(parsed)
        assert res.success is True
        assert "Opened: Active_Spec.pdf" in res.message
        mock_open.assert_called_once_with(fake_doc)


def test_v54_case_7_where_is_the_one_used_for_project(parser):
    """Case 7: Where is the one I used for my project?"""
    parsed = parser.parse("Where is the one I used for my project?")
    assert parsed.intent == IntentType.LOCATION
    assert parsed.query == "project"


def test_v54_case_8_find_the_other_pdf(parser, service, tmp_path):
    """Case 8: Find the other PDF -> uses candidate history from previous search"""
    doc1 = tmp_path / "Internship_Report.pdf"
    doc2 = tmp_path / "Internship_External.pdf"
    doc1.write_text("doc1")
    doc2.write_text("doc2")

    # Simulate previous search results
    cand1 = {"name": doc1.name, "path": str(doc1), "extension": ".pdf"}
    cand2 = {"name": doc2.name, "path": str(doc2), "extension": ".pdf"}
    state_service.set_active_document(doc1)
    state_service.set_last_search("internship", [cand1, cand2])

    parsed = parser.parse("Find the other PDF")
    assert parsed.document_reference == "OTHER_CANDIDATE"
    assert parsed.extension_filter == ".pdf"

    res = service.execute_request(parsed)
    assert res.success is True
    assert "Internship_External.pdf" in res.message
    assert state_service.active_document_path == doc2


def test_v54_case_9_dont_remember_filename_dbms(parser):
    """Case 9: I don't remember the filename but it was about DBMS"""
    parsed = parser.parse("I don't remember the filename but it was about DBMS")
    assert parsed.intent == IntentType.FIND
    assert parsed.target == TargetType.SEARCH  # Must NOT be CURRENT_DOCUMENT
    assert parsed.query == "DBMS"


def test_v54_case_10_assignment_yesterday(parser):
    """Case 10: Find my assignment from yesterday"""
    parsed = parser.parse("Find my assignment from yesterday")
    assert parsed.intent == IntentType.FIND
    assert parsed.date_constraint == "yesterday"
    assert parsed.query == "assignment"


def test_v54_case_11_pdf_from_d_drive(parser, service):
    """Case 11: That PDF from D drive"""
    parsed = parser.parse("That PDF from D drive")
    assert parsed.intent == IntentType.FIND
    assert parsed.extension_filter == ".pdf"
    assert parsed.folder_constraint == "D:"

    # Verify constraint-only execution
    fake_meta = DocumentMetadata(
        doc_id="fake_d_pdf",
        name="Archive.pdf",
        path="D:/Storage/Archive.pdf",
        extension=".pdf",
        folder="Storage",
        size=100,
        modified_time=1700000000.0,
    )
    with patch("app.search.ranker.get_all_documents", return_value=[fake_meta]):
        res = service.execute_request(parsed)
        assert res.success is True
        assert "Archive.pdf" in res.message


def test_v54_case_12_containing_info_react(parser):
    """Case 12: Show me the document containing information about React"""
    parsed = parser.parse("Show me the document containing information about React")
    assert parsed.intent == IntentType.FIND
    assert parsed.query == "React"


def test_v54_case_13_report_working_on_recently(parser):
    """Case 13: Find the report I was working on recently"""
    parsed = parser.parse("Find the report I was working on recently")
    assert parsed.intent == IntentType.FIND
    assert parsed.date_constraint == "recent"
    assert parsed.query == "report"


def test_v54_case_14_open_latest_internship_document(parser):
    """Case 14: Open my latest internship document"""
    parsed = parser.parse("Open my latest internship document")
    assert parsed.intent == IntentType.OPEN
    assert parsed.follow_up_action == FollowUpAction.OPEN
    assert parsed.date_constraint == "recent"
    assert parsed.query == "internship"


def test_v54_case_15_find_ml_and_open_it(parser):
    """Case 15: Find something related to machine learning and open it"""
    parsed = parser.parse("Find something related to machine learning and open it")
    assert parsed.intent == IntentType.FIND
    assert parsed.follow_up_action == FollowUpAction.OPEN
    assert parsed.query == "machine learning"


def test_v54_ambiguity_clarification_format(service, tmp_path):
    """Verify that genuine ambiguity outputs candidate choices cleanly."""
    c1 = tmp_path / "Report_2025.pdf"
    c2 = tmp_path / "Report_2026.pdf"
    c1.write_text("2025")
    c2.write_text("2026")

    meta1 = DocumentMetadata("id1", c1.name, str(c1), ".pdf", "Docs", 100, 1000.0)
    meta2 = DocumentMetadata("id2", c2.name, str(c2), ".pdf", "Docs", 100, 1000.0)

    sig1 = CandidateSignals(80.0, 80.0, 80.0, 0.0, 0.0, False, False, False)
    sig2 = CandidateSignals(80.0, 80.0, 80.0, 0.0, 0.0, False, False, False)

    cand1 = RankedCandidate("id1", str(c1), c1.name, "Docs", ".pdf", 85.0, sig1, meta1)
    cand2 = RankedCandidate("id2", str(c2), c2.name, "Docs", ".pdf", 84.5, sig2, meta2)

    fake_search_res = MagicMock()
    fake_search_res.candidates = [cand1, cand2]
    fake_search_res.confidence = "AMBIGUOUS"

    with patch.object(search_service, "search_candidates", return_value=fake_search_res):
        parsed = IntentParser().parse("Find the report")
        res = service.execute_request(parsed)
        assert res.ambiguous is True
        assert "Multiple matching documents found" in res.message
        assert f"- {c1.name}" in res.message
        assert f"- {c2.name}" in res.message


def test_v54_query_reformulation_fallback(service, tmp_path):
    """Verify fallback relaxation when strict folder constraint produces zero candidates."""
    target_doc = tmp_path / "Agile_Spec.docx"
    target_doc.write_text("agile content")
    meta = DocumentMetadata("id_agile", target_doc.name, str(target_doc), ".docx", "OtherFolder", 100, 1000.0)
    sig = CandidateSignals(85.0, 85.0, 85.0, 0.0, 0.0, True, True, False)
    cand = RankedCandidate("id_agile", str(target_doc), target_doc.name, "OtherFolder", ".docx", 88.0, sig, meta)

    strict_res = MagicMock()
    strict_res.candidates = []
    strict_res.confidence = "LOW"

    relaxed_res = MagicMock()
    relaxed_res.candidates = [cand]
    relaxed_res.confidence = "HIGH"

    def mock_search_fn(query, extension_filter=None, folder_constraint=None, date_constraint=None, limit=10):
        if folder_constraint == "NonexistentFolder":
            return strict_res
        return relaxed_res

    with patch.object(search_service, "search_candidates", side_effect=mock_search_fn):
        parsed = IntentParser().parse("Find Agile_Spec in NonexistentFolder")
        res = service.execute_request(parsed)
        assert res.success is True
        assert "Agile_Spec.docx" in res.message
