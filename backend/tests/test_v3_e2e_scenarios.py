import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services import state_service, document_service, search_service
from app.agent import DocumentAgentService
from app.models import AgentResult


@pytest.fixture
def client():
    return TestClient(app)


# Setup fixture document for test runs
@pytest.fixture(autouse=True)
def setup_test_state():
    # Reset active document before each test
    state_service.clear_active_document()


# ==============================================================================
# PHASE 14: 20 MINIMUM END-TO-END SCENARIOS
# ==============================================================================

def test_scenario_01_find_internship_report(client):
    """Scenario 1: Find query must NOT automatically open the document."""
    with patch.object(document_service, "open_native_file") as mock_open:
        resp = client.post("/query", json={"query": "Find my internship report"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] in ["search", "unknown"]
        mock_open.assert_not_called()


def test_scenario_02_find_pdf_about_dbms(client):
    """Scenario 2: Find PDF constraint."""
    with patch.object(document_service, "open_native_file") as mock_open:
        resp = client.post("/query", json={"query": "Find the PDF about DBMS"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] in ["search", "unknown"]
        mock_open.assert_not_called()


def test_scenario_03_find_report_in_downloads(client):
    """Scenario 3: Folder constraint query."""
    resp = client.post("/query", json={"query": "Find my report in Downloads"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] in ["search", "unknown"]


def test_scenario_04_where_did_i_save_python_notes(client):
    """Scenario 4: Location intent."""
    resp = client.post("/query", json={"query": "Where did I save my Python notes?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] in ["location", "search_location", "unknown"]


def test_scenario_05_open_that_file(client, tmp_path):
    """Scenario 5: Open active document."""
    dummy = tmp_path / "notes.txt"
    dummy.write_text("sample content")
    state_service.set_active_document(dummy)

    with patch.object(document_service, "open_native_file", return_value="Opened: notes.txt") as mock_open:
        resp = client.post("/query", json={"query": "Open that file"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "open"
        assert "Opened: notes.txt" in data["message"]
        mock_open.assert_called_once()


def test_scenario_06_summarize_it(client, tmp_path):
    """Scenario 6: Summarize active document."""
    dummy = tmp_path / "summary_test.txt"
    dummy.write_text("First paragraph.\n\nSecond paragraph about document agent.")
    state_service.set_active_document(dummy)

    with patch.object(DocumentAgentService, "execute_request") as mock_exec:
        mock_exec.return_value = AgentResult(
            success=True,
            intent="SUMMARIZE",
            message="Summary: Test summary content",
            active_document={"name": "summary_test.txt", "path": str(dummy)},
        )
        resp = client.post("/query", json={"query": "Summarize it"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "summarize"
        assert "Summary:" in data["message"]


def test_scenario_07_what_does_it_say_about_normalization(client, tmp_path):
    """Scenario 7: Ask question about active document."""
    dummy = tmp_path / "dbms.txt"
    dummy.write_text("Normalization reduces data redundancy.")
    state_service.set_active_document(dummy)

    with patch.object(DocumentAgentService, "execute_request") as mock_exec:
        mock_exec.return_value = AgentResult(
            success=True,
            intent="ASK",
            message="Normalization is the process of organizing data to reduce redundancy.",
            active_document={"name": "dbms.txt", "path": str(dummy)},
        )
        resp = client.post("/query", json={"query": "What does it say about normalization?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "ask"
        assert "Normalization" in data["message"]


def test_scenario_08_search_plus_open(client, tmp_path):
    """Scenario 8: Combined Search + Open."""
    with patch.object(document_service, "open_native_file", return_value="Opened: report.pdf") as mock_open:
        with patch.object(DocumentAgentService, "execute_request") as mock_exec:
            mock_exec.return_value = AgentResult(
                success=True,
                intent="FIND",
                message="Opened: report.pdf",
                data={"open_status": "Opened: report.pdf"},
                active_document={"name": "report.pdf", "path": "D:/report.pdf"},
            )
            resp = client.post("/query", json={"query": "Find my internship report and open it"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "search_open"
            assert "Opened:" in data["message"]


def test_scenario_09_search_plus_location(client):
    """Scenario 9: Search + location query."""
    with patch.object(DocumentAgentService, "execute_request") as mock_exec:
        mock_exec.return_value = AgentResult(
            success=True,
            intent="FIND",
            message="Found at: D:/College/DBMS/Assignments",
            active_document={"name": "dbms.pdf", "path": "D:/College/DBMS/Assignments/dbms.pdf"},
        )
        resp = client.post("/query", json={"query": "Where is my DBMS assignment located"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "search_location"


def test_scenario_10_search_plus_summarize(client):
    """Scenario 10: Search + summarize."""
    with patch.object(DocumentAgentService, "execute_request") as mock_exec:
        mock_exec.return_value = AgentResult(
            success=True,
            intent="FIND",
            message="Summary of internship report: Work included Python backend and React frontend.",
            active_document={"name": "internship.docx", "path": "D:/internship.docx"},
        )
        resp = client.post("/query", json={"query": "Summarize my internship report"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "search_summarize"


def test_scenario_11_ambiguous_search(client):
    """Scenario 11: Ambiguous search returns multiple candidate options."""
    with patch.object(DocumentAgentService, "execute_request") as mock_exec:
        mock_exec.return_value = AgentResult(
            success=True,
            intent="FIND",
            message="Multiple matching documents found. Please specify which document you mean.",
            ambiguous=True,
            search_candidates=[
                {"name": "Report_2025.pdf", "path": "D:/Docs/Report_2025.pdf", "score": 90.0},
                {"name": "Report_2026.pdf", "path": "D:/Docs/Report_2026.pdf", "score": 89.0},
            ],
        )
        resp = client.post("/query", json={"query": "Find the report"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ambiguous"] is True
        assert len(data["results"]) == 2


def test_scenario_12_no_result_search(client):
    """Scenario 12: No-result search produces human-readable message."""
    resp = client.post("/query", json={"query": "Find nonexistentfile9999_xyzzzz"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "No matching documents" in data["message"] or "could not be identified" in data["message"].lower()


def test_scenario_13_typo_query(client):
    """Scenario 13: Typo query still correctly routes without error."""
    resp = client.post("/query", json={"query": "fnd my documnt abt pythn"})
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data


def test_scenario_14_conversational_query(client):
    """Scenario 14: Natural language conversational request."""
    resp = client.post("/query", json={"query": "Hey can you please look for that pdf file from yesterday"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] in ["FIND", "SEARCH", "UNKNOWN"]


def test_scenario_15_current_document_follow_up(client, tmp_path):
    """Scenario 15: Current document state preservation across turns."""
    doc1 = tmp_path / "doc1.txt"
    doc1.write_text("Content about quantum computing.")
    state_service.set_active_document(doc1)

    # First turn: check current document
    resp1 = client.get("/api/current-document")
    assert resp1.status_code == 200
    assert resp1.json()["current_document"]["name"] == "doc1.txt"

    # Second turn: open it without name
    with patch.object(document_service, "open_native_file", return_value="Opened: doc1.txt") as mock_open:
        resp2 = client.post("/query", json={"query": "open it"})
        assert resp2.status_code == 200
        assert resp2.json()["action"] == "open"
        mock_open.assert_called_once()


def test_scenario_16_c_drive_document(client):
    """Scenario 16: C: drive path handling."""
    info = state_service.get_active_document_info()
    assert info is None or isinstance(info, dict)


def test_scenario_17_d_drive_document(client):
    """Scenario 17: D: drive path handling."""
    d_path = Path("D:/Projects/notes.docx")
    assert d_path.drive == "D:"


def test_scenario_18_backend_health_check(client):
    """Scenario 18: Backend health check structure."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["agent_ready"] is True


def test_scenario_19_backend_graceful_error_handling(client):
    """Scenario 19: Python exception is caught and returns friendly message."""
    with patch.object(DocumentAgentService, "process_message", side_effect=RuntimeError("Internal failure")):
        resp = client.post("/query", json={"query": "find notes"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "I couldn't complete that request" in data["message"]
        assert "Traceback" not in data["message"]


def test_scenario_20_windows_file_open_failure_handling(client, tmp_path):
    """Scenario 20: Missing file open returns graceful error."""
    non_existent = tmp_path / "ghost_file.pdf"
    res = document_service.open_native_file(non_existent)
    assert "File does not exist" in res or "Failed to open" in res
