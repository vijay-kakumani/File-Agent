import unittest
from unittest.mock import patch, MagicMock

from app.agent.intent_parser import (
    IntentParser,
    ParsedRequest,
    IntentType,
    TargetType,
    FollowUpAction,
    ParserConfidence,
)


class TestIntentParser(unittest.TestCase):

    def setUp(self):
        self.parser = IntentParser()

    def test_find_request(self):
        msg = "I have a pdf in downloads about agile methodologies, find it"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIn("agile methodologies", res.query.lower())
        self.assertEqual(res.extension_filter, ".pdf")
        self.assertEqual(res.folder_constraint, "Downloads")

    def test_location_request(self):
        msg = "Where is my internship report?"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.LOCATION)
        self.assertIn("internship report", res.query.lower())

    def test_open_request(self):
        msg = "Open it"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.OPEN)
        self.assertEqual(res.target, TargetType.CURRENT_DOCUMENT)

    def test_read_request(self):
        msg = "Read it"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.READ)
        self.assertEqual(res.target, TargetType.CURRENT_DOCUMENT)

    def test_ask_request(self):
        msg = "What technologies were used?"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.ASK)
        self.assertEqual(res.target, TargetType.CURRENT_DOCUMENT)

    def test_summarize_request(self):
        msg = "Summarize this document"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.SUMMARIZE)
        self.assertEqual(res.target, TargetType.CURRENT_DOCUMENT)

    def test_find_and_open(self):
        msg = "Find the document about Agile and open it"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIn("agile", res.query.lower())
        self.assertEqual(res.follow_up_action, FollowUpAction.OPEN)

    def test_find_and_summarize(self):
        msg = "Find my internship report and summarize it"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIn("internship report", res.query.lower())
        self.assertEqual(res.follow_up_action, FollowUpAction.SUMMARIZE)

    def test_find_and_location(self):
        msg = "Find my internship report and tell me where it is"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIn("internship report", res.query.lower())
        self.assertEqual(res.follow_up_action, FollowUpAction.LOCATION)

    def test_current_document_it(self):
        for phrase in ["open it", "read it", "summarize it", "where is it"]:
            res = self.parser.parse(phrase)
            self.assertEqual(res.target, TargetType.CURRENT_DOCUMENT)

    def test_downloads_extraction(self):
        msg = "find my resume in downloads"
        res = self.parser.parse(msg)
        self.assertEqual(res.folder_constraint, "Downloads")
        self.assertEqual(res.query.lower(), "resume")

    def test_desktop_extraction(self):
        msg = "Find my resume in the desktop folder"
        res = self.parser.parse(msg)
        self.assertEqual(res.folder_constraint, "Desktop")
        self.assertEqual(res.query.lower(), "resume")

    def test_documents_extraction(self):
        msg = "find report in documents"
        res = self.parser.parse(msg)
        self.assertEqual(res.folder_constraint, "Documents")
        self.assertEqual(res.query.lower(), "report")

    def test_college_folder_extraction(self):
        msg = "There is a document somewhere in my college folder about python internship"
        res = self.parser.parse(msg)
        self.assertEqual(res.folder_constraint, "College")
        self.assertIn("python internship", res.query.lower())

    def test_absolute_path_extraction(self):
        msg = r"Open D:\College\Resume.pdf"
        res = self.parser.parse(msg)
        self.assertEqual(res.absolute_path, r"D:\College\Resume.pdf")

    def test_pdf_extraction(self):
        msg = "I have a pdf about agile"
        res = self.parser.parse(msg)
        self.assertEqual(res.extension_filter, ".pdf")

    def test_docx_extraction(self):
        msg = "find word document about project"
        res = self.parser.parse(msg)
        self.assertEqual(res.extension_filter, ".docx")

    def test_natural_sentence_variation(self):
        for variation in ["Find my resume", "Can you find my resume?", "Please locate my resume", "Look for my resume"]:
            res = self.parser.parse(variation)
            self.assertEqual(res.intent, IntentType.FIND)
            self.assertEqual(res.query.lower(), "resume")

    def test_typo_preservation(self):
        msg = "I think I saved a file called Nikil CS in downloads"
        res = self.parser.parse(msg)
        # Typo "Nikil CS" MUST be preserved in query for RapidFuzz
        self.assertEqual(res.query, "Nikil CS")
        self.assertEqual(res.folder_constraint, "Downloads")

    def test_noisy_filler_language(self):
        msg = "Can you please find my internship report in Downloads?"
        res = self.parser.parse(msg)
        self.assertEqual(res.query.lower(), "internship report")
        self.assertEqual(res.folder_constraint, "Downloads")

    def test_empty_request(self):
        res = self.parser.parse("")
        self.assertEqual(res.intent, IntentType.UNKNOWN)
        self.assertEqual(res.confidence, ParserConfidence.LOW)

    def test_ambiguous_request(self):
        res = self.parser.parse("do something")
        self.assertIn(res.intent, [IntentType.FIND, IntentType.UNKNOWN])

    def test_malformed_llm_response(self):
        mock_response = MagicMock()
        mock_response.message.content = "INVALID JSON OUTPUT"
        with patch("app.agent.intent_parser.chat", return_value=mock_response):
            res = self.parser._parse_llm_fallback("complex message")
            self.assertIsNone(res)

    def test_deterministic_parser_without_llm(self):
        """
        INSTRUMENTED PROOF:
        Verifies that standard deterministic requests call Ollama chat 0 times.
        """
        queries = [
            "I have a pdf in downloads about agile methodologies, find it",
            "Find my resume in the desktop folder",
            "Find the document about Agile and open it",
            "Where is my internship report?",
            "Open it",
            "Read it",
            "Summarize this document",
        ]
        with patch("app.agent.intent_parser.chat") as mock_chat:
            for q in queries:
                res = self.parser.parse(q)
                self.assertEqual(res.parser_source, "DETERMINISTIC")
            self.assertEqual(mock_chat.call_count, 0)

    def test_llm_fallback_invocation(self):
        mock_response = MagicMock()
        mock_response.message.content = '{"intent": "FIND", "query": "complex topic", "confidence": "HIGH"}'
        with patch("app.agent.intent_parser.chat", return_value=mock_response) as mock_chat:
            # Message designed to trigger LOW confidence deterministically
            res = self.parser._parse_llm_fallback("unusual complex sentence structure")
            self.assertEqual(mock_chat.call_count, 1)
            self.assertIsNotNone(res)
            self.assertEqual(res.parser_source, "LLM")


if __name__ == "__main__":
    unittest.main()
