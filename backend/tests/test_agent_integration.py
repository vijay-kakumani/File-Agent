import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from app.models import AgentResult, DocumentInfo
from app.agent import DocumentAgentService
from app.services import state_service, document_service, search_service, indexing_service
import file_search


class TestAgentIntegration(unittest.TestCase):

    def setUp(self):
        state_service.clear_active_document()
        self.client = TestClient(app)
        self.agent_service = DocumentAgentService()

        self.test_doc_path = Path("D:/College/Resume.pdf")

    def tearDown(self):
        state_service.clear_active_document()

    def test_missing_current_document(self):
        """Contextual requests without an active document return document-required response."""
        state_service.clear_active_document()
        res = self.agent_service.process_message("Summarize it")
        self.assertFalse(res.success)
        self.assertIn("No active document selected", res.message)

    @patch("app.services.document_service.os.startfile")
    @patch("app.services.search_service.MultiSignalRanker.search")
    def test_find_and_open(self, mock_search, mock_startfile):
        """Combined action 'Find my resume and open it' locates candidate and calls os.startfile."""
        mock_cand = MagicMock()
        mock_cand.path = str(self.test_doc_path)
        mock_cand.name = "Resume.pdf"
        mock_cand.folder = "College"

        mock_search_res = MagicMock()
        mock_search_res.confidence = "HIGH"
        mock_search_res.candidates = [mock_cand]
        mock_search_res.top_candidate = mock_cand
        mock_search.return_value = mock_search_res

        with patch("pathlib.Path.exists", return_value=True):
            res = self.agent_service.process_message("Find my resume and open it")
            self.assertTrue(res.success)
            self.assertEqual(res.intent, "FIND")
            self.assertIsNotNone(state_service.active_document_path)
            self.assertEqual(state_service.active_document_path.name, "Resume.pdf")
            self.assertTrue(mock_startfile.called)

    @patch("app.rag.summarizer.DocumentSummarizer.summarize_file")
    @patch("app.services.search_service.MultiSignalRanker.search")
    def test_find_and_summarize(self, mock_search, mock_sum_file):
        """Combined action 'Find my internship report and summarize it' locates candidate and summarizes."""
        mock_cand = MagicMock()
        mock_cand.path = str(self.test_doc_path)
        mock_cand.name = "Resume.pdf"
        mock_cand.folder = "College"

        mock_search_res = MagicMock()
        mock_search_res.confidence = "HIGH"
        mock_search_res.candidates = [mock_cand]
        mock_search_res.top_candidate = mock_cand
        mock_search.return_value = mock_search_res

        mock_sum_res = MagicMock()
        mock_sum_res.summary = "Integrated summary of internship report."
        mock_sum_res.error = None
        mock_sum_file.return_value = mock_sum_res

        with patch("pathlib.Path.exists", return_value=True):
            res = self.agent_service.process_message("Find my resume and summarize it")
            self.assertTrue(res.success)
            self.assertIn("Integrated summary", res.message)

    @patch("app.services.search_service.MultiSignalRanker.search")
    def test_ambiguous_result(self, mock_search):
        """Ambiguous search result returns candidate list without selecting random file."""
        c1 = MagicMock(path="D:/College/Resume_1.pdf", name="Resume_1.pdf", folder="College")
        c2 = MagicMock(path="D:/College/Resume_2.pdf", name="Resume_2.pdf", folder="College")

        mock_search_res = MagicMock()
        mock_search_res.confidence = "AMBIGUOUS"
        mock_search_res.candidates = [c1, c2]
        mock_search.return_value = mock_search_res

        res = self.agent_service.process_message("find resume")
        self.assertTrue(res.ambiguous)
        self.assertIn("Multiple matching documents found", res.message)
        self.assertEqual(len(res.search_candidates), 2)
        self.assertIsNone(state_service.active_document_path)

    @patch("app.services.search_service.MultiSignalRanker.search")
    def test_low_confidence_result(self, mock_search):
        """Low confidence search returns clear non-match message."""
        mock_search_res = MagicMock()
        mock_search_res.confidence = "LOW"
        mock_search_res.candidates = []
        mock_search.return_value = mock_search_res

        res = self.agent_service.process_message("xyz non-existent document")
        self.assertFalse(res.success)
        self.assertIn("could be identified", res.message)

    @patch("app.rag.qa.DocumentQAService.ask")
    def test_ask_request_with_active_document(self, mock_qa_ask):
        """Ask request uses active document state."""
        state_service.set_active_document(self.test_doc_path)
        mock_qa_res = MagicMock()
        mock_qa_res.answer = "Python and FastAPI"
        mock_qa_res.not_found = False
        mock_qa_res.to_dict.return_value = {"answer": "Python and FastAPI"}
        mock_qa_ask.return_value = mock_qa_res

        res = self.agent_service.process_message("What technologies were used?")
        self.assertTrue(res.success)
        self.assertEqual(res.message, "Python and FastAPI")

    def test_api_health_endpoint(self):
        """FastAPI /api/health GET endpoint."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("indexed_document_count", data)

    def test_api_current_document_endpoint(self):
        """FastAPI /api/current-document GET endpoint."""
        state_service.set_active_document(self.test_doc_path)
        response = self.client.get("/api/current-document")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["current_document"])
        self.assertEqual(data["current_document"]["name"], "Resume.pdf")

    def test_api_refresh_endpoint(self):
        """FastAPI /api/refresh POST endpoint."""
        response = self.client.post("/api/refresh")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("document_count", data)

    @patch("app.services.document_service.os.startfile")
    @patch("app.services.search_service.MultiSignalRanker.search")
    def test_api_chat_endpoint_contract(self, mock_search, mock_startfile):
        """FastAPI /api/chat POST endpoint returns standardized JSON contract."""
        mock_cand = MagicMock()
        mock_cand.path = str(self.test_doc_path)
        mock_cand.name = "Resume.pdf"
        mock_cand.folder = "College"

        mock_search_res = MagicMock()
        mock_search_res.confidence = "HIGH"
        mock_search_res.candidates = [mock_cand]
        mock_search_res.top_candidate = mock_cand
        mock_search.return_value = mock_search_res

        with patch("pathlib.Path.exists", return_value=True):
            response = self.client.post("/api/chat", json={"message": "Find my resume"})
            self.assertEqual(response.status_code, 200)
            data = response.json()

            # Assert clean response contract
            self.assertIn("success", data)
            self.assertIn("response", data)
            self.assertIn("intent", data)
            self.assertIn("current_document", data)
            self.assertIn("search_results", data)
            self.assertIn("document_count", data)

    def test_compatibility_facade(self):
        """Verifies file_search.agent() facade delegates to DocumentAgentService."""
        with patch.object(DocumentAgentService, "process_message") as mock_proc:
            mock_proc.return_value = "Facade output"
            res = file_search.agent("Find my resume")
            self.assertTrue(mock_proc.called)


if __name__ == "__main__":
    unittest.main()
