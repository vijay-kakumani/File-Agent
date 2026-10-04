import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.rag.summarizer import DocumentSummarizer, SummarizeResult, _split_text_for_map


class TestDocumentSummarizer(unittest.TestCase):

    def setUp(self):
        self.summarizer = DocumentSummarizer(
            direct_char_limit=1000,
            chunk_size=500,
            group_size=2,
        )

    def test_empty_document(self):
        """Empty document returns clean summary without calling Ollama."""
        res = self.summarizer.summarize_text("")
        self.assertEqual(res.summary, "Document is empty.")
        self.assertEqual(res.total_ollama_calls, 0)

    @patch("app.rag.summarizer.chat")
    def test_small_document_direct_summary(self, mock_chat):
        """Document <= direct_char_limit uses direct 1-pass summarization."""
        mock_response = MagicMock()
        mock_response.message.content = "Concise direct summary of small document."
        mock_chat.return_value = mock_response

        text = "This is a small document about software engineering principles."
        res = self.summarizer.summarize_text(text, doc_name="small.txt")

        self.assertEqual(res.mode, "DIRECT")
        self.assertEqual(res.total_ollama_calls, 1)
        self.assertEqual(mock_chat.call_count, 1)
        self.assertIn("Concise direct summary", res.summary)

    @patch("app.rag.summarizer.chat")
    def test_medium_document_map_reduce(self, mock_chat):
        """Document > direct_char_limit triggers Map-Reduce summarization."""
        # Create text exceeding direct_char_limit (1000 chars)
        paragraph = "This paragraph details project requirements, scope, timelines, and milestones. " * 8 + "\n\n"
        large_text = paragraph * 4  # ~2500 chars -> splits into ~5 map chunks

        mock_response = MagicMock()
        mock_response.message.content = "Section summary content."
        mock_chat.return_value = mock_response

        res = self.summarizer.summarize_text(large_text, doc_name="medium.txt")

        self.assertEqual(res.mode, "MAP_REDUCE")
        self.assertGreater(res.map_call_count, 1)
        self.assertGreater(res.reduce_call_count, 0)
        self.assertEqual(res.total_ollama_calls, res.map_call_count + res.reduce_call_count)

    @patch("app.rag.summarizer.chat")
    def test_large_document_map_stage(self, mock_chat):
        """Verifies Map stage creates expected chunk count and executes Map calls."""
        chunks = ["Section A content " * 30, "Section B content " * 30, "Section C content " * 30]
        text = "\n\n".join(chunks)

        mock_response = MagicMock()
        mock_response.message.content = "Map chunk summary."
        mock_chat.return_value = mock_response

        res = self.summarizer.summarize_text(text, doc_name="large.txt")

        self.assertEqual(res.map_call_count, len(chunks))

    @patch("app.rag.summarizer.chat")
    def test_reduce_stage(self, mock_chat):
        """Verifies Reduce stage combines intermediate summaries."""
        mock_response = MagicMock()
        mock_response.message.content = "Final reduced summary."
        mock_chat.return_value = mock_response

        text = "Large document text " * 100
        res = self.summarizer.summarize_text(text, doc_name="large.txt")

        self.assertGreater(res.reduce_call_count, 0)
        self.assertEqual(res.summary, "Final reduced summary.")

    @patch("app.rag.summarizer.chat")
    def test_hierarchical_reduce(self, mock_chat):
        """Verifies multi-level recursive reduction when intermediate summaries exceed threshold."""
        # Create summarizer with very low direct_char_limit to force hierarchical reduction
        hierarchical_summarizer = DocumentSummarizer(
            direct_char_limit=200,
            chunk_size=100,
            group_size=2,
        )

        mock_response = MagicMock()
        mock_response.message.content = "Hierarchical intermediate summary with enough length to test."
        mock_chat.return_value = mock_response

        text = "Comprehensive technical specification and architecture details. " * 30
        res = hierarchical_summarizer.summarize_text(text, doc_name="huge.txt")

        self.assertEqual(res.mode, "MAP_REDUCE")
        self.assertGreaterEqual(res.reduce_call_count, 2)  # At least 2 reduce iterations

    @patch("app.rag.summarizer.chat")
    def test_ollama_failure(self, mock_chat):
        """Ollama failure handled gracefully without crashing."""
        mock_chat.side_effect = Exception("Ollama service offline")

        text = "Small document text."
        res = self.summarizer.summarize_text(text, doc_name="test.txt")

        self.assertIsNotNone(res.error)
        self.assertIn("Error generating summary", res.summary)

    @patch("app.rag.summarizer.chat")
    def test_model_returns_empty_output(self, mock_chat):
        """Model returns empty string content."""
        mock_response = MagicMock()
        mock_response.message.content = ""
        mock_chat.return_value = mock_response

        text = "Small document text."
        res = self.summarizer.summarize_text(text, doc_name="test.txt")

        self.assertEqual(res.error, "Empty model response")
        self.assertIn("Model returned an empty summary", res.summary)

    def test_extraction_failure(self):
        """Non-existent file returns clean error result."""
        res = self.summarizer.summarize_file(Path("D:/NonExistentFile.pdf"))
        self.assertEqual(res.error, "File not found")
        self.assertIn("does not exist", res.summary)

    @patch("app.rag.summarizer.chat")
    def test_summary_remains_grounded(self, mock_chat):
        """Verifies prompt sent to Ollama enforces strict grounding rules."""
        mock_response = MagicMock()
        mock_response.message.content = "Summary"
        mock_chat.return_value = mock_response

        self.summarizer.summarize_text("Document text about agile methodologies.", doc_name="test.txt")

        args, kwargs = mock_chat.call_args
        messages = kwargs["messages"]
        system_msg = messages[0]["content"]

        self.assertIn("Do NOT invent facts", system_msg)
        self.assertIn("grounded", system_msg)

    def test_split_text_for_map(self):
        """Verifies paragraph splitting helper for Map stage."""
        text = "Paragraph 1 text.\n\nParagraph 2 text.\n\nParagraph 3 text."
        chunks = _split_text_for_map(text, chunk_size=50)
        self.assertGreater(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
