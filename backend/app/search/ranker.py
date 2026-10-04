import time
import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.models.document import DocumentMetadata
from app.search.fuzzy_engine import (
    FuzzyEngine,
    normalize_text,
    SHORTHAND_EXPANSIONS,
    matches_path_hierarchy,
)
from app.db import search_all_fts, get_all_documents, get_document_by_id
from app.config.settings import DEFAULT_USER_NAME


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    AMBIGUOUS = "AMBIGUOUS"
    LOW = "LOW"


def matches_date_constraint(doc_modified_time: Optional[float], date_constraint: Optional[str]) -> bool:
    if not date_constraint or doc_modified_time is None:
        return False
    c = date_constraint.lower().strip()
    try:
        doc_dt = datetime.datetime.fromtimestamp(doc_modified_time)
        now = datetime.datetime.now()

        if c == "today":
            return doc_dt.date() == now.date()
        elif c == "yesterday":
            yesterday = (now - datetime.timedelta(days=1)).date()
            return doc_dt.date() == yesterday
        elif c == "last week":
            diff_days = (now - doc_dt).days
            return 0 <= diff_days <= 7
        elif c == "last month":
            diff_days = (now - doc_dt).days
            return 0 <= diff_days <= 30
        elif c == "recent":
            diff_days = (now - doc_dt).days
            return 0 <= diff_days <= 14
        else:
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }
            if c in month_names:
                return doc_dt.month == month_names[c]
    except Exception:
        return False
    return False


@dataclass
class CandidateSignals:
    fts_score: float
    filename_score: float
    stem_score: float
    folder_score: float
    extension_score: float
    exact_filename_match: bool
    exact_stem_match: bool
    exact_folder_match: bool
    semantic_score: float = 0.0
    date_match: bool = False

    def to_dict(self) -> dict:
        return {
            "fts_score": round(self.fts_score, 2),
            "filename_score": round(self.filename_score, 2),
            "stem_score": round(self.stem_score, 2),
            "folder_score": round(self.folder_score, 2),
            "extension_score": round(self.extension_score, 2),
            "exact_filename_match": self.exact_filename_match,
            "exact_stem_match": self.exact_stem_match,
            "exact_folder_match": self.exact_folder_match,
            "semantic_score": round(self.semantic_score, 2),
            "date_match": self.date_match,
        }


@dataclass
class RankedCandidate:
    document_id: str
    path: str
    name: str
    folder: str
    extension: str
    score: float
    signals: CandidateSignals
    metadata: DocumentMetadata

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "path": self.path,
            "name": self.name,
            "folder": self.folder,
            "extension": self.extension,
            "score": round(self.score, 2),
            "signals": self.signals.to_dict(),
        }


@dataclass
class SearchResult:
    query: str
    candidates: List[RankedCandidate]
    top_candidate: Optional[RankedCandidate]
    confidence: ConfidenceLevel
    total_candidates_evaluated: int
    execution_time_ms: float

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "confidence": self.confidence.value,
            "top_candidate": self.top_candidate.to_dict() if self.top_candidate else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "total_candidates_evaluated": self.total_candidates_evaluated,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


@dataclass
class RankerConfig:
    filename_stem_weight: float = 0.40
    fts_weight: float = 0.25
    semantic_weight: float = 0.20
    folder_weight: float = 0.10
    extension_weight: float = 0.05
    exact_match_bonus: float = 0.05

    min_document_relevance_gate: float = 35.0
    high_confidence_threshold: float = 70.0
    ambiguity_margin: float = 12.0
    low_confidence_threshold: float = 40.0
    min_score_cutoff: float = 25.0

    fts_candidate_limit: int = 50
    fuzzy_candidate_limit: int = 50
    semantic_candidate_limit: int = 25
    max_merged_candidates: int = 100


class MultiSignalRanker:
    """
    Phase V2.3 Multi-Signal Hybrid Retrieval Ranker.
    Combines FTS5 lexical matching, ChromaDB semantic embeddings, RapidFuzz fuzzy similarity,
    deep hierarchical path resolution, shorthand expansion, and exact-match bonuses into a unified score.
    Operates 100% in-memory over indexed SQLite candidates and precomputed vector embeddings
    without runtime disk text extraction.
    """

    def __init__(self, config: Optional[RankerConfig] = None, vector_store: Optional[Any] = None):
        self.config = config or RankerConfig()
        self.fuzzy_engine = FuzzyEngine()
        self.vector_store = vector_store

    def rank_candidates(
        self,
        query: str,
        candidates: List[DocumentMetadata],
        fts_doc_ids: Optional[Dict[str, int]] = None,
        semantic_scores: Optional[Dict[str, float]] = None,
        extension_filter: Optional[str] = None,
        folder_constraint: Optional[str] = None,
        date_constraint: Optional[str] = None,
    ) -> List[RankedCandidate]:
        if not query or not query.strip() or not candidates:
            return []

        fts_map = fts_doc_ids or {}
        sem_map = semantic_scores or {}
        norm_query = normalize_text(query)
        target_ext = extension_filter.strip().lower() if extension_filter else None
        if target_ext and not target_ext.startswith("."):
            target_ext = f".{target_ext}"

        # Shorthand expansion
        expanded_terms = [query]
        q_lower = query.lower().strip()
        for shorthand, expansions in SHORTHAND_EXPANSIONS.items():
            if shorthand == q_lower or shorthand in q_lower:
                expanded_terms.extend(expansions)
        expanded_terms = list(dict.fromkeys(expanded_terms))

        ranked = []

        for doc in candidates:
            # 1. Fuzzy scores with shorthand expansion
            fuzzy_res = self.fuzzy_engine.score_candidate(query, doc)
            best_name_score = fuzzy_res.name_score
            best_stem_score = fuzzy_res.stem_score

            for et in expanded_terms:
                if et != query:
                    et_res = self.fuzzy_engine.score_candidate(et, doc)
                    best_name_score = max(best_name_score, et_res.name_score)
                    best_stem_score = max(best_stem_score, et_res.stem_score)

            filename_score = best_name_score if best_name_score >= 30.0 else 0.0
            stem_score = best_stem_score if best_stem_score >= 30.0 else 0.0
            folder_score = fuzzy_res.folder_score if fuzzy_res.folder_score >= 30.0 else 0.0

            # Suppress unrelated folder score noise on filename typos if no folder constraint was specified
            if not folder_constraint and stem_score >= 75.0:
                folder_score = 0.0

            # 2. FTS5 score
            fts_score = 0.0
            if doc.doc_id in fts_map:
                rank_pos = fts_map[doc.doc_id]
                fts_score = max(40.0, 100.0 - (rank_pos * 8.0))

            # 3. ChromaDB Semantic Score
            semantic_score = sem_map.get(doc.doc_id, 0.0)

            # 4. Exact matches and partial stem matches
            norm_name = normalize_text(doc.name)
            stem = Path(doc.name).stem
            norm_stem = normalize_text(stem)
            norm_folder = normalize_text(doc.folder)

            exact_filename_match = (norm_query == norm_name)
            exact_stem_match = (norm_query == norm_stem)

            # Shorthand exact stem match: if candidate stem matches any expanded term
            if not exact_stem_match:
                for et in expanded_terms:
                    if normalize_text(et) == norm_stem:
                        exact_stem_match = True
                        break

            exact_folder_match = (
                norm_query == norm_folder
                or norm_query in norm_folder.split()
            )

            # Partial stem match: candidate stem starts with query or stem tokens match query
            stem_tokens = norm_stem.split()
            partial_stem_match = (
                norm_stem.startswith(norm_query)
                or (len(norm_query) >= 3 and any(t.startswith(norm_query) for t in stem_tokens))
                or (len(stem_tokens) > 0 and stem_tokens[0] == norm_query)
            )

            # 5. Extension score
            if target_ext:
                extension_score = 100.0 if doc.extension.lower() == target_ext else 0.0
            else:
                extension_score = 0.0

            # 6. Deep Hierarchical Path / Folder Constraint Matching
            path_matches_constraint = True
            path_boost = 0.0
            if folder_constraint:
                path_matches_constraint = matches_path_hierarchy(doc.path, folder_constraint=folder_constraint)
                if path_matches_constraint:
                    path_boost = 25.0
                    folder_score = max(folder_score, 90.0)
                    exact_folder_match = True

            # 7. Date Constraint Matching
            date_match = False
            date_boost = 0.0
            if date_constraint:
                date_match = matches_date_constraint(doc.modified_time, date_constraint)
                if date_match:
                    date_boost = 25.0

            # 8. Relevance Gate: check document-level evidence (name, stem, FTS5 content, semantic)
            name_stem_signal = max(filename_score, stem_score)
            doc_evidence = max(name_stem_signal, fts_score, semantic_score)
            if exact_filename_match or exact_stem_match:
                doc_evidence = 100.0
            elif partial_stem_match:
                doc_evidence = max(doc_evidence, 80.0)

            if doc_evidence < self.config.min_document_relevance_gate:
                gate_factor = doc_evidence / self.config.min_document_relevance_gate
                effective_folder_score = folder_score * gate_factor
            else:
                effective_folder_score = folder_score

            # 9. Dynamic Weighting based on query type
            if name_stem_signal >= 75.0 or exact_stem_match or exact_filename_match:
                w_stem = 0.60
                w_fts = 0.15
                w_sem = 0.05
                w_folder = 0.15
            elif name_stem_signal < 50.0 and (semantic_score >= 50.0 or fts_score >= 40.0):
                w_stem = 0.15
                w_fts = 0.35
                w_sem = 0.40
                w_folder = 0.05
            else:
                w_stem = self.config.filename_stem_weight
                w_fts = self.config.fts_weight
                w_sem = self.config.semantic_weight
                w_folder = self.config.folder_weight

            exact_bonus = 0.0
            if exact_filename_match:
                exact_bonus = 100.0
            elif exact_stem_match:
                exact_bonus = 90.0
            elif partial_stem_match:
                exact_bonus = 75.0
            elif exact_folder_match and doc_evidence >= self.config.min_document_relevance_gate:
                exact_bonus = 50.0

            # User identity boost: if query or raw_query refers to "my" or user name, boost candidate matching DEFAULT_USER_NAME
            user_identity_bonus = 0.0
            if (DEFAULT_USER_NAME.lower() in norm_name or DEFAULT_USER_NAME.lower() in norm_stem):
                if "my" in q_lower or DEFAULT_USER_NAME.lower() in q_lower or "my" in norm_query:
                    user_identity_bonus = 25.0

            weighted_score = (
                (name_stem_signal * w_stem)
                + (fts_score * w_fts)
                + (semantic_score * w_sem)
                + (effective_folder_score * w_folder)
                + (extension_score * self.config.extension_weight)
                + (exact_bonus * self.config.exact_match_bonus)
                + path_boost
                + date_boost
                + user_identity_bonus
            )

            # Boost exact matches so they unambiguously rank top
            if exact_filename_match or exact_stem_match:
                final_score = min(100.0, max(weighted_score, 85.0 + (exact_bonus * 0.12)))
            elif partial_stem_match and not (folder_constraint and not path_matches_constraint):
                final_score = min(100.0, max(weighted_score, 78.0 + (exact_bonus * 0.10)))
            else:
                final_score = min(100.0, weighted_score)

            # Tier 1 Hard Filters:
            # Explicit folder / drive constraint violated: hard zero
            if folder_constraint and not path_matches_constraint:
                final_score = 0.0

            # Target extension specified and violated: hard zero
            if target_ext and doc.extension.lower() != target_ext:
                final_score = 0.0

            # Date constraint specified and not matched: penalize heavily
            if date_constraint and not date_match:
                final_score = final_score * 0.2

            signals = CandidateSignals(
                fts_score=fts_score,
                filename_score=filename_score,
                stem_score=stem_score,
                folder_score=folder_score,
                extension_score=extension_score,
                exact_filename_match=exact_filename_match,
                exact_stem_match=exact_stem_match,
                exact_folder_match=exact_folder_match,
                semantic_score=semantic_score,
                date_match=date_match,
            )

            ranked.append(
                RankedCandidate(
                    document_id=doc.doc_id,
                    path=doc.path,
                    name=doc.name,
                    folder=doc.folder,
                    extension=doc.extension,
                    score=round(float(final_score), 2),
                    signals=signals,
                    metadata=doc,
                )
            )

        # Deterministic Stable Tie-Breaking:
        # Pre-sort alphabetically by lowercase name (stable sort)
        ranked.sort(key=lambda r: r.name.lower())
        # Sort descending by composite score tuple
        ranked.sort(
            key=lambda r: (
                round(r.score, 2),
                1 if (DEFAULT_USER_NAME.lower() in r.name.lower() and ("my" in q_lower or DEFAULT_USER_NAME.lower() in q_lower or "my" in norm_query)) else 0,
                1 if (r.signals.exact_filename_match or r.signals.exact_stem_match) else 0,
                round(r.signals.stem_score, 2),
                round(r.signals.semantic_score, 2),
                1 if r.signals.exact_folder_match else 0,
                len(Path(r.path).parts),
            ),
            reverse=True,
        )
        return ranked

    def search(
        self,
        query: str,
        extension_filter: Optional[str] = None,
        folder_constraint: Optional[str] = None,
        date_constraint: Optional[str] = None,
        limit: int = 20,
        db_path: Optional[Path] = None,
    ) -> SearchResult:
        start_time = time.perf_counter()

        if not query or not query.strip():
            if not folder_constraint and not extension_filter and not date_constraint:
                return SearchResult(
                    query=query or "",
                    candidates=[],
                    top_candidate=None,
                    confidence=ConfidenceLevel.LOW,
                    total_candidates_evaluated=0,
                    execution_time_ms=0.0,
                )

            # Handle constraint-only query (e.g., "That PDF from D drive")
            all_docs = get_all_documents(limit=self.config.max_merged_candidates, db_path=db_path)
            target_ext = extension_filter.strip().lower() if extension_filter else None
            if target_ext and not target_ext.startswith("."):
                target_ext = f".{target_ext}"

            matched = []
            for doc in all_docs:
                if target_ext and doc.extension.lower() != target_ext:
                    continue
                if folder_constraint and not matches_path_hierarchy(doc.path, folder_constraint=folder_constraint):
                    continue
                if date_constraint and not matches_date_constraint(doc.modified_time, date_constraint):
                    continue

                signals = CandidateSignals(
                    fts_score=0.0,
                    filename_score=80.0,
                    stem_score=80.0,
                    folder_score=90.0 if folder_constraint else 0.0,
                    extension_score=90.0 if target_ext else 0.0,
                    exact_filename_match=False,
                    exact_stem_match=False,
                    exact_folder_match=bool(folder_constraint),
                    semantic_score=0.0,
                    date_match=bool(date_constraint),
                )
                matched.append(
                    RankedCandidate(
                        document_id=doc.doc_id,
                        path=doc.path,
                        name=doc.name,
                        folder=doc.folder,
                        extension=doc.extension,
                        score=88.0,
                        signals=signals,
                        metadata=doc,
                    )
                )

            if date_constraint and "recent" in str(date_constraint).lower():
                matched.sort(key=lambda c: c.metadata.modified_time or 0.0, reverse=True)

            top = matched[0] if matched else None
            conf = ConfidenceLevel.HIGH if len(matched) == 1 else (ConfidenceLevel.AMBIGUOUS if len(matched) > 1 else ConfidenceLevel.LOW)
            return SearchResult(
                query=query or "",
                candidates=matched,
                top_candidate=top,
                confidence=conf,
                total_candidates_evaluated=len(all_docs),
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # Step 1: FTS5 candidates with shorthand expansion
        expanded_terms = [query]
        q_lower = query.lower().strip()
        for shorthand, expansions in SHORTHAND_EXPANSIONS.items():
            if shorthand == q_lower or shorthand in q_lower:
                expanded_terms.extend(expansions)
        expanded_terms = list(dict.fromkeys(expanded_terms))

        fts_candidates = []
        for eq in expanded_terms:
            for d in search_all_fts(eq, limit=self.config.fts_candidate_limit, db_path=db_path):
                if d.doc_id not in [fc.doc_id for fc in fts_candidates]:
                    fts_candidates.append(d)

        fts_doc_ids = {doc.doc_id: idx for idx, doc in enumerate(fts_candidates)}

        # Step 2: Metadata / RapidFuzz candidates from SQLite
        all_docs = get_all_documents(
            limit=self.config.max_merged_candidates, db_path=db_path
        )

        # Step 3: ChromaDB Semantic Search candidates
        semantic_scores: Dict[str, float] = {}
        semantic_doc_ids: List[str] = []
        if self.vector_store:
            try:
                sem_results = self.vector_store.search_semantic(
                    query,
                    limit=self.config.semantic_candidate_limit
                )
                for sr in sem_results:
                    if sr.document_id:
                        score = sr.similarity * 100.0
                        semantic_scores[sr.document_id] = max(
                            semantic_scores.get(sr.document_id, 0.0),
                            score
                        )
                        if sr.document_id not in semantic_doc_ids:
                            semantic_doc_ids.append(sr.document_id)
            except Exception:
                pass

        # Step 4: Merge candidate sets by canonical doc_id
        merged_map: Dict[str, DocumentMetadata] = {}
        for doc in fts_candidates:
            merged_map[doc.doc_id] = doc
        for doc in all_docs:
            if doc.doc_id not in merged_map:
                merged_map[doc.doc_id] = doc

        # Inject semantic candidates from SQLite if not already present
        for s_id in semantic_doc_ids:
            if s_id not in merged_map:
                s_doc = get_document_by_id(s_id, db_path=db_path)
                if s_doc:
                    merged_map[s_id] = s_doc

        candidate_list = list(merged_map.values())

        # Step 5: Multi-signal ranking
        ranked_list = self.rank_candidates(
            query=query,
            candidates=candidate_list,
            fts_doc_ids=fts_doc_ids,
            semantic_scores=semantic_scores,
            extension_filter=extension_filter,
            folder_constraint=folder_constraint,
            date_constraint=date_constraint,
        )

        # Filter by extension if explicitly provided
        if extension_filter:
            target_ext = extension_filter.strip().lower()
            if not target_ext.startswith("."):
                target_ext = f".{target_ext}"
            ranked_list = [c for c in ranked_list if c.extension.lower() == target_ext]

        # Filter candidates below min_score_cutoff
        ranked_list = [c for c in ranked_list if c.score >= self.config.min_score_cutoff]

        # Step 6: Confidence & Ambiguity evaluation
        top_candidate = ranked_list[0] if ranked_list else None
        confidence = ConfidenceLevel.LOW

        if top_candidate:
            top_score = top_candidate.score
            if top_score < self.config.low_confidence_threshold:
                confidence = ConfidenceLevel.LOW
            elif top_score >= self.config.high_confidence_threshold:
                if len(ranked_list) > 1:
                    second_score = ranked_list[1].score
                    if (top_score - second_score) < self.config.ambiguity_margin:
                        confidence = ConfidenceLevel.AMBIGUOUS
                    else:
                        confidence = ConfidenceLevel.HIGH
                else:
                    confidence = ConfidenceLevel.HIGH
            else:
                # Top score between low (40) and high (70)
                if len(ranked_list) > 1:
                    second_score = ranked_list[1].score
                    if (top_score - second_score) < self.config.ambiguity_margin:
                        confidence = ConfidenceLevel.AMBIGUOUS
                    else:
                        confidence = ConfidenceLevel.HIGH
                else:
                    confidence = ConfidenceLevel.HIGH

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return SearchResult(
            query=query,
            candidates=ranked_list[:limit],
            top_candidate=top_candidate,
            confidence=confidence,
            total_candidates_evaluated=len(candidate_list),
            execution_time_ms=elapsed_ms,
        )
