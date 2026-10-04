import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models import DocumentMetadata, generate_canonical_doc_id
from app.rag.qa import DocumentQAService, DocumentQAResult
from app.rag.vector_store import VectorStore, VectorSearchResult


class TestDocumentQA(unittest.TestCase):

    def setUp(self):
        self.mock_vector_store = MagicMock(spec=VectorStore)
        self.qa_service = DocumentQAService(
            vector_store=self.mock_vector_store,
            top_k=4,
            distance_threshold=0.60,
        )

        self.doc_a_path = Path("D:/College/Internship_A.pdf")
        self.doc_a_id = generate_canonical_doc_id(self.doc_a_path)

        self.doc_b_path = Path("D:/College/Internship_B.pdf")
        self.doc_b_id = generate_canonical_doc_id(self.doc_b_path)

    def test_no_active_document(self):
        """Active document safety check: returns document-required response if no document is active."""
        res = self.qa_service.ask("What is the CGPA?")
        self.assertTrue(res.not_found)
        self.assertFalse(res.grounded)
        self.assertIn("No active document selected", res.answer)

    def test_empty_question(self):
        """Empty question handling."""
        res = self.qa_service.ask("", document_path=self.doc_a_path)
        self.assertTrue(res.not_found)
        self.assertIn("Empty question", res.answer)

    @patch("app.rag.qa.chat")
    def test_correct_answer_from_context(self, mock_chat):
        """Grounded answer from retrieved context."""
        chunk = VectorSearchResult(
            document_id=self.doc_a_id,
            document_name="Internship_A.pdf",
            path=str(self.doc_a_path),
            chunk_index=0,
            text="The internship duration was 8 weeks. CGPA requirement: 3.8.",
            distance=0.25,
            similarity=0.875,
            metadata={},
        )
        self.mock_vector_store.search_semantic.return_value = [chunk]

        mock_response = MagicMock()
        mock_response.message.content = "The internship duration was 8 weeks."
        mock_chat.return_value = mock_response

        res = self.qa_service.ask("What is the internship duration?", document_path=self.doc_a_path)
        self.assertTrue(res.grounded)
        self.assertFalse(res.not_found)
        self.assertIn("8 weeks", res.answer)
        self.assertEqual(res.document_id, self.doc_a_id)

    @patch("app.rag.qa.chat")
    def test_answer_absent_from_document(self, mock_chat):
        """Question about missing fact returns not-found behavior."""
        self.mock_vector_store.search_semantic.return_value = []

        res = self.qa_service.ask("Who is the CEO of the company?", document_path=self.doc_a_path)
        self.assertTrue(res.not_found)
        self.assertFalse(res.grounded)
        self.assertIn("couldn't find", res.answer.lower())
        self.assertEqual(mock_chat.call_count, 0)

    @patch("app.rag.qa.chat")
    def test_document_isolation(self, mock_chat):
        """
        DOCUMENT ISOLATION TEST:
        Document A: Internship duration was 8 weeks.
        Document B: Internship duration was 12 weeks.
        When A is active, search_semantic must filter strictly by Document A's document_id.
        """
        # Search call MUST filter by doc_a_id
        chunk_a = VectorSearchResult(
            document_id=self.doc_a_id,
            document_name="Internship_A.pdf",
            path=str(self.doc_a_path),
            chunk_index=0,
            text="Internship duration was 8 weeks.",
            distance=0.15,
            similarity=0.925,
            metadata={},
        )
        self.mock_vector_store.search_semantic.return_value = [chunk_a]

        mock_response = MagicMock()
        mock_response.message.content = "The internship duration is 8 weeks."
        mock_chat.return_value = mock_response

        res = self.qa_service.ask("What is the internship duration?", document_path=self.doc_a_path)

        # Assert search_semantic was called with document_id=self.doc_a_id
        self.mock_vector_store.search_semantic.assert_called_with(
            query="What is the internship duration?",
            document_id=self.doc_a_id,
            limit=4,
        )
        self.assertIn("8 weeks", res.answer)

    @patch("app.rag.qa.chat")
    def test_duplicate_concepts_separate_docs(self, mock_chat):
        """Verify prompt sent to Ollama receives ONLY context from active document."""
        chunk_a = VectorSearchResult(
            document_id=self.doc_a_id,
            document_name="Internship_A.pdf",
            path=str(self.doc_a_path),
            chunk_index=0,
            text="Technologies used: Python, FastAPI, ChromaDB.",
            distance=0.30,
            similarity=0.85,
            metadata={},
        )
        self.mock_vector_store.search_semantic.return_value = [chunk_a]

        mock_response = MagicMock()
        mock_response.message.content = "Python, FastAPI, ChromaDB"
        mock_chat.return_value = mock_response

        self.qa_service.ask("What technologies were used?", document_path=self.doc_a_path)

        # Inspect prompt passed to chat
        args, kwargs = mock_chat.call_args
        messages = kwargs["messages"]
        user_msg = messages[1]["content"]

        self.assertIn("Python, FastAPI, ChromaDB", user_msg)
        self.assertNotIn("12 weeks", user_msg)

    @patch("app.rag.qa.chat")
    def test_retrieval_threshold(self, mock_chat):
        """Chunks exceeding distance threshold (e.g. distance = 0.85 > 0.60) are discarded."""
        high_distance_chunk = VectorSearchResult(
            document_id=self.doc_a_id,
            document_name="Internship_A.pdf",
            path=str(self.doc_a_path),
            chunk_index=0,
            text="Irrelevant text content",
            distance=0.85,  # Exceeds threshold of 0.60
            similarity=0.575,
            metadata={},
        )
        self.mock_vector_store.search_semantic.return_value = [high_distance_chunk]

        res = self.qa_service.ask("What is the CGPA?", document_path=self.doc_a_path)
        self.assertTrue(res.not_found)
        self.assertEqual(mock_chat.call_count, 0)  # Ollama was NOT called

    @patch("app.rag.qa.chat")
    def test_ollama_unavailable(self, mock_chat):
        """Ollama network/connection failure handling."""
        chunk = VectorSearchResult(
            document_id=self.doc_a_id,
            document_name="Internship_A.pdf",
            path=str(self.doc_a_path),
            chunk_index=0,
            text="Some relevant context",
            distance=0.20,
            similarity=0.90,
            metadata={},
        )
        self.mock_vector_store.search_semantic.return_value = [chunk]
        mock_chat.side_effect = ConnectionError("Ollama service unreachable")

        res = self.qa_service.ask("What is the duration?", document_path=self.doc_a_path)
        self.assertIsNotNone(res.error)
        self.assertIn("Error querying local AI model", res.answer)

    @patch("app.rag.qa.chat")
    def test_malformed_empty_model_response(self, mock_chat):
        """Model returns empty string content."""
        chunk = VectorSearchResult(
            document_id=self.doc_a_id,
            document_name="Internship_A.pdf",
            path=str(self.doc_a_path),
            chunk_index=0,
            text="Some relevant context",
            distance=0.20,
            similarity=0.90,
            metadata={},
        )
        self.mock_vector_store.search_semantic.return_value = [chunk]

        mock_response = MagicMock()
        mock_response.message.content = ""
        mock_chat.return_value = mock_response

        res = self.qa_service.ask("What is the duration?", document_path=self.doc_a_path)
        self.assertTrue(res.not_found)

    def test_no_cross_document_contamination(self):
        """Verifies Chroma query filter includes document_id to prevent cross-document leakage."""
        self.mock_vector_store.search_semantic.return_value = []
        self.qa_service.ask("What is the internship duration?", document_path=self.doc_a_path)
        self.mock_vector_store.search_semantic.assert_called_with(
            query="What is the internship duration?",
            document_id=self.doc_a_id,
            limit=4,
        )


if __name__ == "__main__":
    unittest.main()
