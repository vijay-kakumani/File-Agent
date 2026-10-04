import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.agent import DocumentAgentService
from app.services import state_service, document_service


class TestOpeningBehavior(unittest.TestCase):
    """
    Behavioral consistency verification for DocumentAgentService and DocumentService.
    Verifies that plain FIND and non-opening intents NEVER trigger document_service.open_native_file()
    or os.startfile(), while explicit OPEN requests do.
    """

    def setUp(self):
        state_service.clear_active_document()
        self.agent_service = DocumentAgentService()
        self.test_doc_path = Path("D:/College/Nikhil CS.pdf")

    def tearDown(self):
        state_service.clear_active_document()

    @patch("app.services.search_service.MultiSignalRanker.search")
    def test_find_does_not_open(self, mock_search):
        """
        1. FIND request:
           "Find Nikhil CS"
           -> search
           -> select/set current document if unambiguous
           -> return "Found: Nikhil CS.pdf"
           -> DO NOT call open_native_file()
        """
        mock_cand = MagicMock()
        mock_cand.path = str(self.test_doc_path)
        mock_cand.name = "Nikhil CS.pdf"
        mock_cand.folder = "College"

        mock_search_res = MagicMock()
        mock_search_res.confidence = "HIGH"
        mock_search_res.candidates = [mock_cand]
        mock_search_res.top_candidate = mock_cand
        mock_search.return_value = mock_search_res

        with patch.object(document_service, "open_native_file") as mock_open:
            res = self.agent_service.process_message("Find Nikhil CS")

            # Must set current document
            self.assertEqual(state_service.active_document_path, self.test_doc_path)
            # Must return "Found: Nikhil CS.pdf"
            self.assertEqual(res.message, "Found: Nikhil CS.pdf")
            self.assertEqual(res.intent, "FIND")
            self.assertTrue(res.success)
            # Crucial assertion: open_native_file MUST NOT be called
            mock_open.assert_not_called()
            self.assertEqual(mock_open.call_count, 0)

    @patch("app.services.search_service.MultiSignalRanker.search")
    def test_find_and_open_opens(self, mock_search):
        """
        2. FIND + OPEN request:
           "Find Nikhil CS and open it"
           -> search
           -> select/set current document
           -> call open_native_file() exactly once
        """
        mock_cand = MagicMock()
        mock_cand.path = str(self.test_doc_path)
        mock_cand.name = "Nikhil CS.pdf"
        mock_cand.folder = "College"

        mock_search_res = MagicMock()
        mock_search_res.confidence = "HIGH"
        mock_search_res.candidates = [mock_cand]
        mock_search_res.top_candidate = mock_cand
        mock_search.return_value = mock_search_res

        with patch.object(document_service, "open_native_file", return_value="Opened: Nikhil CS.pdf") as mock_open:
            res = self.agent_service.process_message("Find Nikhil CS and open it")

            # Must set current document
            self.assertEqual(state_service.active_document_path, self.test_doc_path)
            self.assertEqual(res.intent, "FIND")
            self.assertTrue(res.success)
            # Crucial assertion: open_native_file MUST be called exactly once
            mock_open.assert_called_once_with(self.test_doc_path)
            self.assertEqual(mock_open.call_count, 1)

    def test_open_opens_current_document(self):
        """
        3. OPEN request:
           "Open it"
           -> open current document using open_native_file()
        """
        state_service.set_active_document(self.test_doc_path)

        with patch.object(document_service, "open_native_file", return_value="Opened: Nikhil CS.pdf") as mock_open:
            res = self.agent_service.process_message("Open it")

            self.assertEqual(res.intent, "OPEN")
            self.assertTrue(res.success)
            mock_open.assert_called_once_with(self.test_doc_path)
            self.assertEqual(mock_open.call_count, 1)

    def test_location_does_not_open(self):
        """
        4. LOCATION request:
           "Where is it?"
           -> returns location
           -> DO NOT call open_native_file()
        """
        state_service.set_active_document(self.test_doc_path)

        with patch.object(document_service, "open_native_file") as mock_open, \
             patch.object(document_service, "get_document_location", return_value="Location: D:\\College\\Nikhil CS.pdf"):
            res = self.agent_service.process_message("Where is it?")

            self.assertEqual(res.intent, "LOCATION")
            self.assertTrue(res.success)
            self.assertIn("Location:", res.message)
            # Crucial assertion: open_native_file MUST NOT be called
            mock_open.assert_not_called()
            self.assertEqual(mock_open.call_count, 0)

    def test_summarize_does_not_open(self):
        """
        5. SUMMARIZE request:
           "Summarize it"
           -> summarizes active document
           -> DO NOT call open_native_file()
        """
        state_service.set_active_document(self.test_doc_path)

        mock_sum_res = MagicMock()
        mock_sum_res.summary = "Executive summary of document."
        mock_sum_res.error = None
        mock_sum_res.to_dict.return_value = {"summary": "Executive summary of document."}

        with patch.object(document_service, "open_native_file") as mock_open, \
             patch.object(self.agent_service.summarizer, "summarize_file", return_value=mock_sum_res):
            res = self.agent_service.process_message("Summarize it")

            self.assertEqual(res.intent, "SUMMARIZE")
            self.assertTrue(res.success)
            self.assertEqual(res.message, "Executive summary of document.")
            # Crucial assertion: open_native_file MUST NOT be called
            mock_open.assert_not_called()
            self.assertEqual(mock_open.call_count, 0)

    def test_ask_does_not_open(self):
        """
        6. ASK request:
           "What is this document about?"
           -> Q&A on active document
           -> DO NOT call open_native_file()
        """
        state_service.set_active_document(self.test_doc_path)

        mock_qa_res = MagicMock()
        mock_qa_res.answer = "This document discusses computer science."
        mock_qa_res.not_found = False
        mock_qa_res.to_dict.return_value = {"answer": "This document discusses computer science."}

        with patch.object(document_service, "open_native_file") as mock_open, \
             patch.object(self.agent_service.qa_service, "ask", return_value=mock_qa_res):
            res = self.agent_service.process_message("What is this document about?")

            self.assertEqual(res.intent, "ASK")
            self.assertTrue(res.success)
            self.assertEqual(res.message, "This document discusses computer science.")
            # Crucial assertion: open_native_file MUST NOT be called
            mock_open.assert_not_called()
            self.assertEqual(mock_open.call_count, 0)


if __name__ == "__main__":
    unittest.main()
