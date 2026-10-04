import os
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import SUPPORTED_EXTENSIONS
from app.documents.extractor import extract_text
from app.services.state_service import state_service


class DocumentService:
    """
    Phase 9 Canonical Document Operation Service.
    Responsible for reading documents, reporting location, and single controlled Win32 native file opening via os.startfile().
    """

    def read_document(self, file_path: Path) -> str:
        if not file_path.exists():
            return "File does not exist."

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return "Unsupported file type."

        try:
            text = extract_text(file_path)
            if not text:
                return "The document is empty."
            return text
        except Exception as err:
            return f"Could not read file: {err}"

    def open_native_file(self, file_path: Path) -> str:
        """
        SINGLE CANONICAL IMPLEMENTATION OF NATIVE WINDOWS FILE OPENING.
        Uses os.startfile() on resolved absolute path.
        """
        if not file_path.exists():
            return "File does not exist."

        try:
            resolved = file_path.resolve()
            os.startfile(str(resolved))
            # Establish active document state
            state_service.set_active_document(resolved)
            return f"Opened: {file_path.name}"
        except Exception as err:
            return f"Could not open file: {err}"

    def get_document_location(self, file_path: Path) -> str:
        if not file_path.exists():
            return "File does not exist."
        resolved = file_path.resolve()
        return f"Location: {resolved}"


# Global singleton instance
document_service = DocumentService()
