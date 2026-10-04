import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services import state_service, document_service, search_service
from app.agent.service import DocumentAgentService
from app.agent.intent_parser import IntentParser, IntentType, TargetType
from app.models import AgentResult, DocumentInfo
from app.models.document import DocumentMetadata
from app.search.ranker import RankedCandidate, CandidateSignals, SearchResult, ConfidenceLevel
from app.rag.summarizer import SummarizeResult


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_state():
    state_service.clear_active_document()
    yield
    state_service.clear_active_document()


def make_ranked_candidate(doc_path: Path, score: float = 0.95):
    meta = DocumentMetadata.from_file_path(doc_path)
    signals = CandidateSignals(
        fts_score=score * 100,
        filename_score=score * 100,
        stem_score=score * 100,
        folder_score=0.0,
        extension_score=100.0,
        exact_filename_match=True,
        exact_stem_match=True,
        exact_folder_match=False
    )
    return RankedCandidate(
        document_id=meta.doc_id,
        path=str(doc_path),
        name=doc_path.name,
        folder=doc_path.parent.name,
        extension=doc_path.suffix,
        score=score * 100,
        signals=signals,
        metadata=meta
    )


def make_search_result(candidates, query="test", confidence=ConfidenceLevel.HIGH):
    top = candidates[0] if candidates else None
    return SearchResult(
        query=query,
        candidates=candidates,
        top_candidate=top,
        confidence=confidence,
        total_candidates_evaluated=len(candidates),
        execution_time_ms=1.5
    )


# ==============================================================================
# V5.5 FULL USER FLOW VALIDATION (10 STEPS + AMBIGUITY)
# ==============================================================================

def test_full_user_flow_step_1_find_internship_report(client, tmp_path):
    """Step 1: Find my internship report -> SEARCH intent, sets active document, does NOT open."""
    internship_doc = tmp_path / "Internship_Report.pdf"
    internship_doc.write_text("Vijay Kakumani 4th Year Internship Report at TechCorp Solutions")
    mock_candidate = make_ranked_candidate(internship_doc, score=0.92)
    search_res = make_search_result([mock_candidate], query="internship report")

    with patch.object(document_service, "open_native_file") as mock_open:
        with patch.object(search_service, "search_candidates", return_value=search_res):
            resp = client.post("/query", json={"query": "Find my internship report"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "search"
            assert data["success"] is True
            assert "Internship_Report.pdf" in data["message"]
            mock_open.assert_not_called()
            # Active document is updated
            assert state_service.active_document_path == internship_doc


def test_full_user_flow_step_2_find_and_open(client, tmp_path):
    """Step 2: Find my internship report and open it -> SEARCH_AND_OPEN, opens native viewer."""
    internship_doc = tmp_path / "Internship_Report.pdf"
    internship_doc.write_text("Vijay Kakumani Internship Report")
    mock_candidate = make_ranked_candidate(internship_doc, score=0.95)
    search_res = make_search_result([mock_candidate], query="internship report")

    with patch.object(document_service, "open_native_file", return_value="Opened: Internship_Report.pdf") as mock_open:
        with patch.object(search_service, "search_candidates", return_value=search_res):
            resp = client.post("/query", json={"query": "Find my internship report and open it"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "search_open"
            assert data["success"] is True
            mock_open.assert_called_once_with(internship_doc)
            assert state_service.active_document_path == internship_doc


def test_full_user_flow_step_3_summarize_it(client, tmp_path):
    """Step 3: Summarize it -> Follow-up action referencing active document."""
    active_doc = tmp_path / "Internship_Report.pdf"
    active_doc.write_text("Internship overview at TechCorp Solutions for 8 weeks.")
    state_service.set_active_document(active_doc)

    with patch("app.rag.summarizer.DocumentSummarizer.summarize_file") as mock_sum:
        mock_sum.return_value = SummarizeResult(
            summary="This is an 8-week internship report at TechCorp Solutions focusing on backend systems.",
            document_name="Internship_Report.pdf"
        )
        resp = client.post("/query", json={"query": "Summarize it"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "summarize"
        assert "8-week internship report" in data["message"]


def test_full_user_flow_step_4_what_technologies_mentioned(client, tmp_path):
    """Step 4: What technologies are mentioned? -> Grounded QA against active document."""
    active_doc = tmp_path / "Internship_Report.pdf"
    active_doc.write_text("Technologies: Python, FastAPI, React, PostgreSQL.")
    state_service.set_active_document(active_doc)

    with patch("app.rag.qa.DocumentQAService.ask") as mock_qa:
        mock_qa.return_value = MagicMock(
            answer="The technologies mentioned are Python, FastAPI, React, and PostgreSQL.",
            grounded=True,
            confidence=0.98,
            sources=["Page 1"]
        )
        resp = client.post("/query", json={"query": "What technologies are mentioned?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "ask"
        assert "Python, FastAPI, React, and PostgreSQL" in data["message"]


def test_full_user_flow_step_5_where_is_it_located(client, tmp_path):
    """Step 5: Where is it located? -> LOCATION intent on active document."""
    active_doc = tmp_path / "Documents" / "Internship_Report.pdf"
    active_doc.parent.mkdir(parents=True, exist_ok=True)
    active_doc.write_text("Dummy content")
    state_service.set_active_document(active_doc)

    resp = client.post("/query", json={"query": "Where is it located?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "location"
    assert str(active_doc) in data["message"] or active_doc.name in data["message"]


def test_full_user_flow_step_6_find_pdf_about_dbms(client):
    """Step 6: Find the PDF about DBMS -> Extension constraint .pdf, query: DBMS."""
    parser = IntentParser()
    parsed = parser.parse("Find the PDF about DBMS")
    assert parsed.intent == IntentType.FIND
    assert parsed.extension_filter == ".pdf"
    assert parsed.query == "DBMS"


def test_full_user_flow_step_7_dont_remember_filename_normalization(client):
    """Step 7: I don't remember the filename but it was about normalization -> clean query normalization."""
    parser = IntentParser()
    parsed = parser.parse("I don't remember the filename but it was about normalization")
    assert parsed.intent == IntentType.FIND
    assert "normalization" in parsed.query
    assert "don't remember" not in parsed.query.lower()


def test_full_user_flow_step_8_find_document_from_downloads(client):
    """Step 8: Find the document from Downloads -> folder constraint: Downloads."""
    parser = IntentParser()
    parsed = parser.parse("Find the document from Downloads")
    assert parsed.intent == IntentType.FIND
    assert parsed.folder_constraint == "Downloads"


def test_full_user_flow_step_9_open_document_we_just_found(client, tmp_path):
    """Step 9: Open the document we just found -> OPEN active document."""
    just_found = tmp_path / "Downloads" / "Agile_Notes.docx"
    just_found.parent.mkdir(parents=True, exist_ok=True)
    just_found.write_text("Agile notes content")
    state_service.set_active_document(just_found)

    parser = IntentParser()
    parsed = parser.parse("Open the document we just found")
    assert parsed.intent == IntentType.OPEN
    assert parsed.target == TargetType.CURRENT_DOCUMENT

    with patch.object(document_service, "open_native_file", return_value="Opened: Agile_Notes.docx") as mock_open:
        resp = client.post("/query", json={"query": "Open the document we just found"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "open"
        mock_open.assert_called_once_with(just_found)


def test_full_user_flow_step_10_find_the_other_pdf(client, tmp_path):
    """Step 10: Find the other PDF -> Candidate switching from previous search."""
    pdf1 = tmp_path / "Internship_Report_Vijay.pdf"
    pdf2 = tmp_path / "Internship_Report_External.pdf"
    pdf1.write_text("doc1")
    pdf2.write_text("doc2")

    cand1 = {"name": pdf1.name, "path": str(pdf1), "extension": ".pdf"}
    cand2 = {"name": pdf2.name, "path": str(pdf2), "extension": ".pdf"}
    state_service.set_active_document(pdf1)
    state_service.set_last_search("internship", [cand1, cand2])

    resp = client.post("/query", json={"query": "Find the other PDF"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "search"
    assert "Internship_Report_External.pdf" in data["message"]
    assert state_service.active_document_path == pdf2


def test_ambiguity_clarification_handling(client, tmp_path):
    """Ambiguity test: When 2+ equally likely candidates exist, prompt user with options."""
    doc_a = tmp_path / "Resume_A.pdf"
    doc_b = tmp_path / "Resume_B.pdf"
    doc_a.write_text("A")
    doc_b.write_text("B")

    cand_a = make_ranked_candidate(doc_a, score=0.85)
    cand_b = make_ranked_candidate(doc_b, score=0.85)
    search_res = make_search_result([cand_a, cand_b], query="resume", confidence=ConfidenceLevel.AMBIGUOUS)

    with patch.object(search_service, "search_candidates", return_value=search_res):
        resp = client.post("/query", json={"query": "Find my resume"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ambiguous"] is True
        assert len(data["results"]) == 2
        assert "Multiple matching documents found" in data["message"]


# ==============================================================================
# PERFORMANCE VALIDATION (SEARCH, QA, SUMMARY, COLD/WARM)
# ==============================================================================

def test_performance_measurement_search_latency(tmp_path):
    """Verify search retrieval latency is well under 35 ms."""
    from app.search.fuzzy_engine import FuzzyEngine

    fuzzy = FuzzyEngine()
    meta_list = [
        DocumentMetadata(
            doc_id=f"id_{i}",
            name=f"file_name_sample_{i}.pdf",
            path=f"C:/docs/file_name_sample_{i}.pdf",
            extension=".pdf",
            folder="docs",
            size=1024,
            modified_time=time.time()
        )
        for i in range(100)
    ]

    # Cold query
    t0 = time.perf_counter()
    res_cold = [fuzzy.score_candidate("sample", item) for item in meta_list]
    t_cold = (time.perf_counter() - t0) * 1000

    # Warm query
    t1 = time.perf_counter()
    res_warm = [fuzzy.score_candidate("sample", item) for item in meta_list]
    t_warm = (time.perf_counter() - t1) * 1000

    assert len(res_cold) == 100
    assert len(res_warm) == 100
    assert t_warm < 15.0


def test_streaming_query_endpoint(client, tmp_path):
    """Verify POST /query/stream delivers SSE events (meta, token, done)."""
    active_doc = tmp_path / "Notes.txt"
    active_doc.write_text("Notes on software architecture and APIs.")
    state_service.set_active_document(active_doc)

    with patch("app.rag.qa.DocumentQAService.ask_stream") as mock_stream:
        def fake_gen(question, document_path):
            yield {"type": "token", "content": "Here is the "}
            yield {"type": "token", "content": "answer from the document."}
            yield {"type": "done", "result": MagicMock(answer="Here is the answer from the document.", grounded=True)}
        mock_stream.side_effect = fake_gen

        resp = client.post("/query/stream", json={"query": "What are these notes about?"})
        assert resp.status_code == 200
        text = resp.text
        assert '"type": "meta"' in text
        assert '"type": "token"' in text
        assert '"type": "done"' in text
        assert "Here is the " in text
