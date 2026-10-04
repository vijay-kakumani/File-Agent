"""
Unit and regression tests for Phase V2.3 improvements:
- Semantic candidate injection & hybrid retrieval
- Action suffix & conversational filler cleaning
- Folder score noise suppression on filename typos
- Space-aware Windows path parsing
- Date constraint filtering
- 2-tier constraint precedence
- Deterministic tie-breaking
- User identity resolution (DEFAULT_USER_NAME)
"""

import time
import datetime
from pathlib import Path
import pytest

from app.config.settings import DEFAULT_USER_NAME
from app.models.document import DocumentMetadata
from app.search.fuzzy_engine import FuzzyEngine
from app.search.ranker import MultiSignalRanker, matches_date_constraint, ConfidenceLevel
from app.agent.intent_parser import IntentParser, IntentType, FollowUpAction
from app.agent.target_resolver import TargetResolver, ResolvedTargetType


def test_space_aware_windows_path_parsing():
    parser = IntentParser()
    res = parser.parse(r"Find my internship report in D:\College\4th Year\Internship")
    assert res.folder_constraint is not None
    assert "College" in res.folder_constraint
    assert "Internship" in res.folder_constraint
    assert "D:" in res.folder_constraint
    assert "4th Year" in res.folder_constraint


def test_action_suffix_cleaning():
    parser = IntentParser()
    res1 = parser.parse("Find internship report and show file path")
    assert res1.follow_up_action == FollowUpAction.LOCATION
    assert "file path" not in (res1.query or "").lower()

    res2 = parser.parse("Find CampusConnect report and give folder")
    assert res2.follow_up_action == FollowUpAction.LOCATION
    assert "give folder" not in (res2.query or "").lower()

    res3 = parser.parse("where report internship is")
    assert res3.intent == IntentType.LOCATION
    assert "internship" in (res3.query or "").lower()


def test_conversational_prefix_and_filler_cleaning():
    parser = IntentParser()
    res1 = parser.parse("Could you please locate the file named Vijay_Resume.pdf")
    assert "vijay" in (res1.query or "").lower()
    assert "could you please locate" not in (res1.query or "").lower()

    res2 = parser.parse("me want machine learn notes")
    assert "machine" in (res2.query or "").lower()
    assert "me want" not in (res2.query or "").lower()


def test_user_identity_resolution():
    parser = IntentParser()
    res = parser.parse("That PDF I downloaded with my name on it")
    assert DEFAULT_USER_NAME.lower() in (res.query or "").lower()
    assert res.folder_constraint == "Downloads"
    assert res.extension_filter == ".pdf"


def test_date_constraint_matching():
    now = datetime.datetime.now()
    now_ts = now.timestamp()
    yesterday_ts = (now - datetime.timedelta(days=1)).timestamp()
    last_week_ts = (now - datetime.timedelta(days=5)).timestamp()
    two_months_ago_ts = (now - datetime.timedelta(days=60)).timestamp()

    assert matches_date_constraint(now_ts, "today") is True
    assert matches_date_constraint(yesterday_ts, "today") is False

    assert matches_date_constraint(yesterday_ts, "yesterday") is True
    assert matches_date_constraint(now_ts, "yesterday") is False

    assert matches_date_constraint(last_week_ts, "last week") is True
    assert matches_date_constraint(two_months_ago_ts, "last week") is False

    assert matches_date_constraint(two_months_ago_ts, "last month") is False


def test_folder_noise_suppression_on_typo():
    ranker = MultiSignalRanker()

    doc1 = DocumentMetadata(
        doc_id="doc1",
        name="Vijay_Resume.pdf",
        path=r"C:\Downloads\Vijay_Resume.pdf",
        folder="Downloads",
        extension=".pdf",
        size=1024,
        modified_time=time.time(),
        indexed_time=time.time(),
    )
    doc2 = DocumentMetadata(
        doc_id="doc2",
        name="College_Brochure.pdf",
        folder="College",
        path=r"C:\College\College_Brochure.pdf",
        extension=".pdf",
        size=1024,
        modified_time=time.time(),
        indexed_time=time.time(),
    )

    # Query with typo: "Vjay"
    ranked = ranker.rank_candidates("Vjay", [doc1, doc2])
    assert len(ranked) >= 1
    assert ranked[0].document_id == "doc1"
    # doc1 signals should have folder_score = 0.0 because stem_score >= 75 and no folder requested
    assert ranked[0].signals.folder_score == 0.0


def test_deterministic_tie_breaking():
    ranker = MultiSignalRanker()

    doc_a = DocumentMetadata(
        doc_id="doc_a",
        name="Resume_Beta.pdf",
        path=r"C:\Documents\Resume_Beta.pdf",
        folder="Documents",
        extension=".pdf",
        size=100,
        modified_time=100.0,
        indexed_time=100.0,
    )
    doc_b = DocumentMetadata(
        doc_id="doc_b",
        name="Resume_Alpha.pdf",
        path=r"C:\Documents\Resume_Alpha.pdf",
        folder="Documents",
        extension=".pdf",
        size=100,
        modified_time=100.0,
        indexed_time=100.0,
    )

    ranked1 = ranker.rank_candidates("Resume", [doc_a, doc_b])
    ranked2 = ranker.rank_candidates("Resume", [doc_b, doc_a])

    # In both runs, top candidate must be identical
    assert ranked1[0].name == ranked2[0].name
    assert ranked1[0].name == "Resume_Alpha.pdf"


def test_target_resolver_identity_boost():
    resolver = TargetResolver()

    doc_vijay = DocumentMetadata(
        doc_id="doc_v",
        name="Vijay_Resume.pdf",
        path=r"C:\Downloads\Vijay_Resume.pdf",
        folder="Downloads",
        extension=".pdf",
        size=1000,
        modified_time=time.time(),
        indexed_time=time.time(),
    )
    doc_other = DocumentMetadata(
        doc_id="doc_o",
        name="Resume.pdf",
        path=r"C:\Downloads\Resume.pdf",
        folder="Downloads",
        extension=".pdf",
        size=1000,
        modified_time=time.time(),
        indexed_time=time.time(),
    )

    res = resolver.resolve_reference(
        reference="my resume",
        candidates=[doc_other, doc_vijay]
    )

    assert res.target_type == ResolvedTargetType.DOCUMENT_REFERENCE
    assert res.document_name == "Vijay_Resume.pdf"
    assert res.is_ambiguous is False
