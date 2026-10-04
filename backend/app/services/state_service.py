from pathlib import Path
from typing import Optional, Dict, Any

from app.models import generate_canonical_doc_id, DocumentInfo


class StateService:
    """
    Phase 9 Centralized Active Document State Service.
    Maintains canonical active document state across application layers and requests.
    Prevents conflicting active document state between modules.
    """

    _instance: Optional["StateService"] = None

    def __new__(cls) -> "StateService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active_document_path = None
            cls._instance._active_doc_id = None
            cls._instance._last_search_candidates = []
            cls._instance._last_search_query = None
        return cls._instance

    @property
    def active_document_path(self) -> Optional[Path]:
        return self._active_document_path

    @property
    def active_doc_id(self) -> Optional[str]:
        return self._active_doc_id

    def set_active_document(self, path: Optional[Path]) -> Optional[Path]:
        if path is None:
            self._active_document_path = None
            self._active_doc_id = None
            return None

        resolved = path.resolve() if path.is_absolute() else path
        self._active_document_path = resolved
        self._active_doc_id = generate_canonical_doc_id(resolved)
        return self._active_document_path

    def clear_active_document(self) -> None:
        self._active_document_path = None
        self._active_doc_id = None

    def set_last_search(self, query: str, candidates: list) -> None:
        self._last_search_query = query
        self._last_search_candidates = list(candidates) if candidates else []

    def get_last_search_candidates(self) -> list:
        return list(self._last_search_candidates)

    def get_last_search_query(self) -> Optional[str]:
        return self._last_search_query

    def get_other_candidate(self, extension_filter: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves the next viable candidate from the previous search
        that is NOT the currently active document.
        """
        active_str = str(self._active_document_path).lower() if self._active_document_path else ""
        target_ext = extension_filter.strip().lower() if extension_filter else None
        if target_ext and not target_ext.startswith("."):
            target_ext = f".{target_ext}"

        for cand in self._last_search_candidates:
            c_path = str(cand.get("path") or cand.get("path", "")).lower()
            c_ext = str(cand.get("extension") or Path(c_path).suffix).lower()
            if c_path != active_str:
                if target_ext and c_ext != target_ext:
                    continue
                return cand

        # Fallback if all remaining candidates lacked the extension filter
        if target_ext:
            for cand in self._last_search_candidates:
                c_path = str(cand.get("path") or "").lower()
                if c_path != active_str:
                    return cand

        return None

    def get_active_document_info(self) -> Optional[Dict[str, Any]]:
        if self._active_document_path is not None:
            info = DocumentInfo.from_path(self._active_document_path)
            data = info.to_dict()
            data["document_id"] = self._active_doc_id
            return data
        return None


# Global singleton instance
state_service = StateService()
