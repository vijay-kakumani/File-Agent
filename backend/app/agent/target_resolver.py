import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from app.models.document import DocumentMetadata
from app.search.fuzzy_engine import (
    FuzzyEngine,
    normalize_text,
    SHORTHAND_EXPANSIONS,
    normalize_path_for_matching,
    matches_path_hierarchy,
)
from app.db import get_all_documents, search_all_fts
from app.services.state_service import state_service
from app.config.settings import DEFAULT_USER_NAME


class ResolvedTargetType(str, Enum):
    CURRENT_DOCUMENT = "CURRENT_DOCUMENT"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    SEARCH = "SEARCH"
    MULTIPLE_DOCUMENTS = "MULTIPLE_DOCUMENTS"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class TargetCandidate:
    document_id: str
    name: str
    path: str
    folder: str
    extension: str
    score: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "name": self.name,
            "path": self.path,
            "folder": self.folder,
            "extension": self.extension,
            "score": round(self.score, 2),
            "reason": self.reason,
        }


@dataclass
class TargetResolutionResult:
    target_type: ResolvedTargetType
    resolved_path: Optional[Path] = None
    resolved_doc_id: Optional[str] = None
    document_name: Optional[str] = None
    candidates: List[TargetCandidate] = field(default_factory=list)
    is_ambiguous: bool = False
    confidence: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_type": self.target_type.value,
            "resolved_path": str(self.resolved_path) if self.resolved_path else None,
            "resolved_doc_id": self.resolved_doc_id,
            "document_name": self.document_name,
            "candidates": [c.to_dict() for c in self.candidates],
            "is_ambiguous": self.is_ambiguous,
            "confidence": round(self.confidence, 2),
            "reason": self.reason,
        }


class TargetResolver:
    """
    Phase V2.2 Target Resolution Engine.
    Resolves natural user references ('resume', 'internship report', 'cv', 'ml notes',
    pronouns, content descriptions, deep path constraints) against indexed documents.
    Preserves genuine ambiguity without forcing arbitrary single picks.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        self.fuzzy_engine = FuzzyEngine()

    def resolve_reference(
        self,
        reference: str,
        folder_constraint: Optional[str] = None,
        extension_filter: Optional[str] = None,
        candidates: Optional[List[DocumentMetadata]] = None,
        db_path: Optional[Path] = None,
    ) -> TargetResolutionResult:
        """
        Resolves an indirect or direct document reference to an indexed candidate.
        """
        active_db = db_path or self.db_path
        all_docs = candidates or get_all_documents(limit=100, db_path=active_db)

        if not reference or not reference.strip():
            # If no reference, check if active document exists
            if state_service.active_document_path:
                active_p = state_service.active_document_path
                return TargetResolutionResult(
                    target_type=ResolvedTargetType.CURRENT_DOCUMENT,
                    resolved_path=active_p,
                    document_name=active_p.name,
                    confidence=100.0,
                    reason="Active document from state",
                )
            return TargetResolutionResult(
                target_type=ResolvedTargetType.NOT_FOUND,
                confidence=0.0,
                reason="Empty reference and no active document",
            )

        ref_clean = reference.strip()
        ref_lower = ref_clean.lower()

        # 1. Pronoun / Context reference ('it', 'that', 'this document', 'that file')
        if re.match(r'^(?:it|that|this|the document|this document|that document|this report|that file|the file)$', ref_lower):
            if state_service.active_document_path:
                active_p = state_service.active_document_path
                return TargetResolutionResult(
                    target_type=ResolvedTargetType.CURRENT_DOCUMENT,
                    resolved_path=active_p,
                    document_name=active_p.name,
                    confidence=100.0,
                    reason="Resolved pronoun to active document",
                )
            return TargetResolutionResult(
                target_type=ResolvedTargetType.NOT_FOUND,
                confidence=0.0,
                reason="Pronoun reference with no active document",
            )

        # 2. Filter candidates by extension and folder constraint if provided
        filtered_candidates = all_docs
        if extension_filter:
            ext_target = extension_filter.strip().lower()
            if not ext_target.startswith("."):
                ext_target = f".{ext_target}"
            filtered_candidates = [d for d in filtered_candidates if d.extension.lower() == ext_target]

        if folder_constraint:
            filtered_candidates = [
                d for d in filtered_candidates
                if matches_path_hierarchy(d.path, folder_constraint=folder_constraint)
            ]

        if not filtered_candidates:
            # Fallback to unfiltered if constraints were overly restrictive
            filtered_candidates = all_docs

        # 3. Shorthand expansion
        expanded_terms = [ref_clean]
        for shorthand, expansions in SHORTHAND_EXPANSIONS.items():
            if shorthand == ref_lower or shorthand in ref_lower:
                expanded_terms.extend(expansions)
        expanded_terms = list(dict.fromkeys(expanded_terms))

        # 4. Multi-Signal Candidate Scoring
        scored_candidates: List[TargetCandidate] = []

        norm_ref = normalize_text(ref_clean)

        for doc in filtered_candidates:
            stem = Path(doc.name).stem
            norm_name = normalize_text(doc.name)
            norm_stem = normalize_text(stem)

            # Direct exact match check
            exact_name = (norm_ref == norm_name)
            exact_stem = (norm_ref == norm_stem)

            # Fuzzy match score
            fuzzy_res = self.fuzzy_engine.score_candidate(ref_clean, doc)
            best_fuzzy = max(fuzzy_res.name_score, fuzzy_res.stem_score)

            # Check expanded shorthand matches
            shorthand_bonus = 0.0
            for term in expanded_terms:
                t_norm = normalize_text(term)
                if t_norm == norm_stem or t_norm == norm_name:
                    shorthand_bonus = max(shorthand_bonus, 100.0)
                elif t_norm in norm_name or t_norm in norm_stem:
                    shorthand_bonus = max(shorthand_bonus, 90.0)
                elif norm_name in t_norm or norm_stem in t_norm:
                    shorthand_bonus = max(shorthand_bonus, 85.0)

            # Check if reference is a token of candidate stem (e.g. 'resume' in 'Vijay_Resume')
            stem_tokens = norm_stem.split()
            if norm_ref in stem_tokens:
                shorthand_bonus = max(shorthand_bonus, 95.0)

            # Path constraint match bonus
            path_bonus = 0.0
            if folder_constraint and matches_path_hierarchy(doc.path, folder_constraint=folder_constraint):
                path_bonus = 15.0

            # Content match relevance check (FTS)
            fts_bonus = 0.0
            if doc.content:
                c_lower = doc.content.lower()
                if norm_ref in c_lower:
                    fts_bonus = 30.0

            # User identity resolution (e.g. 'my resume' / 'my cv' -> user's document)
            user_identity_bonus = 0.0
            is_user_doc = (DEFAULT_USER_NAME.lower() in norm_stem or DEFAULT_USER_NAME.lower() in norm_name)
            if is_user_doc and ("my" in ref_lower or DEFAULT_USER_NAME.lower() in ref_lower):
                user_identity_bonus = 25.0

            if exact_name or exact_stem:
                score = 100.0 + path_bonus + user_identity_bonus
                reason = "Exact filename/stem match"
            elif shorthand_bonus >= 95.0:
                score = shorthand_bonus + path_bonus + user_identity_bonus
                reason = "Exact shorthand / stem token match"
            elif shorthand_bonus >= 80.0:
                score = shorthand_bonus + path_bonus + user_identity_bonus
                reason = "Shorthand / alias match"
            else:
                score = best_fuzzy * 0.7 + fts_bonus + path_bonus + user_identity_bonus
                reason = f"Fuzzy similarity ({round(best_fuzzy, 1)})"

            if score >= 40.0:
                scored_candidates.append(
                    TargetCandidate(
                        document_id=doc.doc_id,
                        name=doc.name,
                        path=doc.path,
                        folder=doc.folder,
                        extension=doc.extension,
                        score=score,
                        reason=reason,
                    )
                )

        # Sort candidates by score descending, prioritizing exact matches and user identity
        scored_candidates.sort(
            key=lambda c: (
                round(c.score, 2),
                1 if (DEFAULT_USER_NAME.lower() in c.name.lower() and "my" in ref_lower) else 0,
                1 if normalize_text(Path(c.name).stem) == norm_ref else 0,
                -len(c.name)
            ),
            reverse=True
        )

        if not scored_candidates:
            return TargetResolutionResult(
                target_type=ResolvedTargetType.NOT_FOUND,
                confidence=0.0,
                reason="No candidate reached minimum resolution threshold (40.0)",
            )

        top = scored_candidates[0]

        # 5. Ambiguity Detection (e.g. 'resume' with multiple valid resumes)
        if len(scored_candidates) > 1:
            second = scored_candidates[1]
            score_diff = abs(top.score - second.score)
            if score_diff < 10.0:
                # Genuinely ambiguous candidates
                return TargetResolutionResult(
                    target_type=ResolvedTargetType.MULTIPLE_DOCUMENTS,
                    resolved_path=Path(top.path),
                    resolved_doc_id=top.document_id,
                    document_name=top.name,
                    candidates=scored_candidates,
                    is_ambiguous=True,
                    confidence=top.score,
                    reason=f"Ambiguous candidates ({top.name} vs {second.name}, diff={round(score_diff, 1)})",
                )

        # Single clear winner
        return TargetResolutionResult(
            target_type=ResolvedTargetType.DOCUMENT_REFERENCE,
            resolved_path=Path(top.path),
            resolved_doc_id=top.document_id,
            document_name=top.name,
            candidates=scored_candidates,
            is_ambiguous=False,
            confidence=top.score,
            reason=top.reason,
        )


# Global singleton
target_resolver = TargetResolver()
