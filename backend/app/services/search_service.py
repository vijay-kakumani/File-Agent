from pathlib import Path
from typing import List, Dict, Any, Optional

from app.search import MultiSignalRanker, SearchResult, RankedCandidate
from app.rag import VectorStore, VectorSearchResult
from app.agent.target_resolver import matches_path_hierarchy


class SearchService:
    """
    Phase V2.2 Canonical Search Service.
    Coordinates FTS5 retrieval, RapidFuzz fuzzy matching, MultiSignalRanker, and Chroma semantic search.
    Provides one unified search entry point across the application.
    """

    def __init__(self, ranker: Optional[MultiSignalRanker] = None, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()
        self.ranker = ranker or MultiSignalRanker(vector_store=self.vector_store)
        if not self.ranker.vector_store:
            self.ranker.vector_store = self.vector_store

    def search(
        self,
        query: str,
        extension_filter: Optional[str] = None,
        folder_constraint: Optional[str] = None,
        date_constraint: Optional[str] = None,
        limit: int = 10,
        db_path: Optional[Path] = None,
    ) -> SearchResult:
        return self.ranker.search(
            query=query,
            extension_filter=extension_filter,
            folder_constraint=folder_constraint,
            date_constraint=date_constraint,
            limit=limit,
            db_path=db_path,
        )

    def search_candidates(
        self,
        query: str,
        extension_filter: Optional[str] = None,
        folder_constraint: Optional[str] = None,
        date_constraint: Optional[str] = None,
        limit: int = 10,
    ) -> SearchResult:
        if not query or not query.strip():
            if not folder_constraint and not extension_filter and not date_constraint:
                return SearchResult(
                    query=query or "",
                    candidates=[],
                    top_candidate=None,
                    confidence=self.ranker.config.low_confidence_threshold,
                    total_candidates_evaluated=0,
                    execution_time_ms=0.0,
                )

        result = self.ranker.search(
            query=query,
            extension_filter=extension_filter,
            folder_constraint=folder_constraint,
            date_constraint=date_constraint,
            limit=limit,
        )

        return result

    def search_semantic_chunks(
        self,
        query: str,
        document_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[VectorSearchResult]:
        return self.vector_store.search_semantic(query=query, document_id=document_id, limit=limit)


# Global singleton instance
search_service = SearchService()
