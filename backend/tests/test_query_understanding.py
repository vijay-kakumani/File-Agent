import unittest
from app.agent.intent_parser import (
    IntentParser,
    IntentType,
    TargetType,
    FollowUpAction,
    ParserConfidence,
)


class TestQueryUnderstanding(unittest.TestCase):

    def setUp(self):
        self.parser = IntentParser()

    # =========================================================================
    # 1. QUERY UNDERSTANDING
    # =========================================================================
    def test_plain_search(self):
        msg = "Vijay_Resume.pdf"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIn("vijay", res.query.lower())

    def test_conversational_wording(self):
        msg = "can you please locate that document about agile methodologies for me"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertEqual(res.query.lower(), "agile methodologies")

    def test_filler_removal(self):
        msg = "um hey can you please find that document about campusconnect right now please"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertEqual(res.query.lower(), "campusconnect")

    def test_typo_preservation(self):
        msg = "Find CampussConnect_Report.pdf"
        res = self.parser.parse(msg)
        self.assertIn("campussconnect", res.query.lower())

    def test_missing_character(self):
        msg = "Find CampuConnect_Report.pdf"
        res = self.parser.parse(msg)
        self.assertIn("campuconnect", res.query.lower())

    def test_transposed_characters(self):
        msg = "Locate Viayj_Resume.pdf"
        res = self.parser.parse(msg)
        self.assertIn("viayj", res.query.lower())

    def test_shorthand_references(self):
        for phrase in ["Find ml notes", "Look for cc report", "Find cs resume"]:
            res = self.parser.parse(phrase)
            self.assertEqual(res.intent, IntentType.FIND)
            self.assertTrue(len(res.query) > 0)

    def test_semantic_wording(self):
        msg = "Retrieve the writeup on student team collaboration"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIn("student team collaboration", res.query.lower())

    def test_content_description_search(self):
        msg = "Find document where I mentioned 40% latency reduction"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIn("40% latency reduction", res.query.lower())

    # =========================================================================
    # 2. CONSTRAINT EXTRACTION
    # =========================================================================
    def test_drive_constraint(self):
        msg = "Find documents in C drive"
        res = self.parser.parse(msg)
        self.assertIn("C:", res.folder_constraint)

    def test_folder_constraint(self):
        msg = "Find resume in Downloads"
        res = self.parser.parse(msg)
        self.assertEqual(res.folder_constraint, "Downloads")
        self.assertEqual(res.query.lower(), "resume")

    def test_nested_folder_constraint(self):
        msg = "Find report in Documents/College/4th_Year/Internship"
        res = self.parser.parse(msg)
        self.assertIn("College/4th_Year/Internship", res.folder_constraint)

    def test_absolute_path_constraint(self):
        msg = r"Open D:\College\4th_Year\Internship\Internship_Report_External.pdf"
        res = self.parser.parse(msg)
        self.assertEqual(res.absolute_path, r"D:\College\4th_Year\Internship\Internship_Report_External.pdf")

    def test_extension_constraint(self):
        msg = "find agile methodologies docx"
        res = self.parser.parse(msg)
        self.assertEqual(res.extension_filter, ".docx")
        self.assertEqual(res.query.lower(), "agile methodologies")

    def test_multiple_constraints(self):
        msg = "Find pdf report about internship in Downloads"
        res = self.parser.parse(msg)
        self.assertEqual(res.extension_filter, ".pdf")
        self.assertEqual(res.folder_constraint, "Downloads")
        self.assertIn("internship", res.query.lower())

    # =========================================================================
    # 3. ACTION SEPARATION
    # =========================================================================
    def test_plain_find_does_not_open(self):
        msg = "Find my resume"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertIsNone(res.follow_up_action)

    def test_find_plus_open(self):
        msg = "Find my resume and open it"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertEqual(res.follow_up_action, FollowUpAction.OPEN)

    def test_find_plus_summarize(self):
        msg = "Find CampusConnect_Report.pdf and summarize it"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertEqual(res.follow_up_action, FollowUpAction.SUMMARIZE)

    def test_find_plus_location(self):
        msg = "Find my resume and tell me where it is"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.FIND)
        self.assertEqual(res.follow_up_action, FollowUpAction.LOCATION)

    def test_document_referenced_question(self):
        msg = "What tech I used in my resume?"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.ASK)
        self.assertEqual(res.target, TargetType.DOCUMENT_REFERENCE)
        self.assertIn(res.document_reference, ["resume", "my resume"])
        self.assertIn("what tech i used", res.question.lower())

    def test_where_did_i_save_location_action(self):
        msg = "Where did I save my CampusConnect report?"
        res = self.parser.parse(msg)
        self.assertEqual(res.intent, IntentType.LOCATION)
        self.assertIn("campusconnect report", res.query.lower())


if __name__ == "__main__":
    unittest.main()
