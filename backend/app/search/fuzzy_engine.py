import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from rapidfuzz import fuzz
from app.models.document import DocumentMetadata


def normalize_text(text: str) -> str:
    """
    Normalizes input query or file/folder string:
    - lowercase
    - replaces path separators, underscores, hyphens with spaces
    - collapses multiple spaces
    """
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[\/\\_\-\.]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


@dataclass
class FuzzyResult:
    document: DocumentMetadata
    name_score: float
    stem_score: float
    folder_score: float
    overall_score: float

    def to_dict(self) -> dict:
        return {
            "name": self.document.name,
            "path": self.document.path,
            "folder": self.document.folder,
            "name_score": self.name_score,
            "stem_score": self.stem_score,
            "folder_score": self.folder_score,
            "overall_score": self.overall_score,
        }


class FuzzyEngine:
    """
    RapidFuzz Typo & Spelling Matching Engine.
    Operates strictly in-memory on indexed metadata candidates.
    Never opens files, reads PDFs/DOCXs, or scans filesystem roots on queries.
    """

    def __init__(self, min_threshold: float = 50.0):
        self.min_threshold = min_threshold

    def score_candidate(self, query: str, doc: DocumentMetadata) -> FuzzyResult:
        norm_query = normalize_text(query)
        norm_name = normalize_text(doc.name)

        # Stem without file extension
        stem = Path(doc.name).stem
        norm_stem = normalize_text(stem)
        norm_folder = normalize_text(doc.folder)

        if not norm_query or not norm_name:
            return FuzzyResult(doc, 0.0, 0.0, 0.0, 0.0)

        query_tokens = norm_query.split()
        name_tokens = norm_name.split()
        stem_tokens = norm_stem.split()

        # 1. Filename Score
        token_name = fuzz.token_set_ratio(norm_query, norm_name, processor=None)
        if token_name > 0:
            if len(query_tokens) > len(name_tokens) and len(name_tokens) > 0:
                token_name = token_name * (len(name_tokens) / len(query_tokens))
            ratio_name = fuzz.WRatio(norm_query, norm_name, processor=None)
            name_score = max(ratio_name, token_name)
        else:
            name_score = float(fuzz.ratio(norm_query, norm_name, processor=None))

        # 2. Stem Score
        token_stem = fuzz.token_set_ratio(norm_query, norm_stem, processor=None)
        if token_stem > 0:
            if len(query_tokens) > len(stem_tokens) and len(stem_tokens) > 0:
                token_stem = token_stem * (len(stem_tokens) / len(query_tokens))
            ratio_stem = fuzz.WRatio(norm_query, norm_stem, processor=None)
            stem_score = max(ratio_stem, token_stem)
        else:
            stem_score = float(fuzz.ratio(norm_query, norm_stem, processor=None))

        # 3. Folder Score
        folder_score = 0.0
        if norm_folder:
            partial_folder = fuzz.partial_ratio(norm_query, norm_folder, processor=None)
            token_folder = fuzz.token_set_ratio(norm_query, norm_folder, processor=None)
            folder_score = max(partial_folder, token_folder)

        # Combined overall score prioritizing filename & stem match
        overall_score = max(name_score, stem_score * 1.02, folder_score * 0.75)
        overall_score = min(100.0, overall_score)

        return FuzzyResult(
            document=doc,
            name_score=round(float(name_score), 2),
            stem_score=round(float(stem_score), 2),
            folder_score=round(float(folder_score), 2),
            overall_score=round(float(overall_score), 2),
        )

    def search_candidates(
        self,
        query: str,
        candidates: List[DocumentMetadata],
        limit: int = 20,
        threshold: Optional[float] = None
    ) -> List[FuzzyResult]:
        eff_threshold = threshold if threshold is not None else self.min_threshold
        norm_query = normalize_text(query)

        if not norm_query or not candidates:
            return []

        results = []
        for doc in candidates:
            res = self.score_candidate(norm_query, doc)
            if res.overall_score >= eff_threshold:
                results.append(res)

        # Sort by overall_score descending, then name length ascending (prefer precise matches)
        results.sort(key=lambda r: (r.overall_score, -len(r.document.name)), reverse=True)
        return results[:limit]


# Standard abbreviation and natural alias dictionary
SHORTHAND_EXPANSIONS: dict[str, list[str]] = {
    "cv": ["resume", "cv"],
    "curriculum vitae": ["resume", "cv"],
    "my cv": ["vijay resume", "resume", "cv"],
    "my resume": ["vijay resume", "resume"],
    "my curriculum vitae": ["vijay resume", "resume", "cv"],
    "cs resume": ["nikhil cs resume", "resume"],
    "college resume": ["resume"],
    "intern": ["internship", "intern report", "intern"],
    "intern doc": ["internship report", "internship", "intern"],
    "intern rept": ["internship report", "internship", "intern"],
    "intern report": ["internship report", "internship", "intern"],
    "rept": ["report"],
    "internship": ["internship report", "internship", "intern"],
    "internship report": ["internship report", "intern report", "intern"],
    "cc report": ["campusconnect report", "campusconnect"],
    "cc doc": ["campusconnect report", "campusconnect"],
    "campus connect": ["campusconnect"],
    "campusconnect": ["campusconnect report"],
    "ml notes": ["machine learning notes", "machine learning"],
    "ml": ["machine learning"],
    "machine learning notes": ["machine learning notes"],
    "agile doc": ["agile methodologies", "agile"],
    "agile notes": ["agile methodologies", "agile"],
    "scrum guide": ["agile methodologies", "scrum"],
    "python guide": ["python backend guide", "python"],
    "backend guide": ["python backend guide"],
    "budget summary": ["q3 budget summary", "budget"],
    "budget": ["q3 budget summary"],
    "tax receipt": ["tax receipt 2025", "tax"],
    "tax": ["tax receipt"],
    "aws cert": ["aws cloud practitioner", "aws"],
    "aws practitioner": ["aws cloud practitioner"],
    "system spec": ["system architecture spec", "architecture"],
    "architecture spec": ["system architecture spec"],
}


def normalize_path_for_matching(path_str: str) -> str:
    """Normalizes backslashes to forward slashes and lowercases for path matching."""
    if not path_str:
        return ""
    p = path_str.replace("\\", "/").lower()
    # Normalize simulated drive representations
    p = re.sub(r'\bd_drive_sim\b', 'd:', p)
    p = re.sub(r'\bc_drive_sim\b', 'c:', p)
    return p


def matches_path_hierarchy(
    candidate_path: str,
    folder_constraint: Optional[str] = None,
    drive_constraint: Optional[str] = None,
) -> bool:
    """
    Checks if candidate_path satisfies deep hierarchical path and drive constraints.
    Supports complete folder hierarchies like 'College/4th_Year/Internship' or 'D:\\College\\4th_Year\\Internship'.
    """
    if not folder_constraint and not drive_constraint:
        return True

    norm_cand = normalize_path_for_matching(candidate_path)

    def _cand_has_drive_letter(dl: str) -> bool:
        dl = dl.lower()
        cand_lower = candidate_path.lower()
        if "_drive_sim" in cand_lower or "_drive" in cand_lower:
            cand_drive = "c" if ("c_drive_sim" in cand_lower or "c_drive" in cand_lower) else "d"
            return dl == cand_drive
        return f"{dl}:" in norm_cand

    # Check drive constraint if specified
    if drive_constraint:
        drive_letter = drive_constraint.lower().replace(":", "").replace("drive", "").strip()
        if drive_letter and not _cand_has_drive_letter(drive_letter):
            return False

    if not folder_constraint:
        return True

    norm_folder = normalize_path_for_matching(folder_constraint)

    # Check drive specified inside folder_constraint
    drive_match = re.match(r'^([a-zA-Z]):', norm_folder)
    if drive_match:
        drive_letter = drive_match.group(1).lower()
        if not _cand_has_drive_letter(drive_letter):
            return False
        # Remove drive prefix from folder check
        norm_folder = norm_folder[2:].lstrip("/")

    # Check whole normalized folder string
    clean_subpath = norm_folder.strip("/")
    if not clean_subpath:
        return True

    def _strip_sep(s: str) -> str:
        return re.sub(r'[\s_\-]+', '', s.lower())

    # 1. Direct substring match (exact or separator-agnostic)
    if clean_subpath in norm_cand or _strip_sep(clean_subpath) in _strip_sep(norm_cand):
        return True

    # 2. Segment-by-segment hierarchical order check (separator-agnostic)
    segments = [s.strip() for s in clean_subpath.split("/") if s.strip()]
    cand_segments = [s.strip() for s in norm_cand.split("/") if s.strip()]

    # Check that all segments appear in cand_segments in same relative order
    curr_idx = 0
    for seg in segments:
        clean_seg = _strip_sep(seg)
        found = False
        for i in range(curr_idx, len(cand_segments)):
            clean_cand = _strip_sep(cand_segments[i])
            if clean_seg in clean_cand or clean_cand in clean_seg:
                curr_idx = i + 1
                found = True
                break
        if not found:
            return False

    return True

