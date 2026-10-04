from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import time
from typing import Optional


def generate_canonical_doc_id(file_path: Path) -> str:
    """
    Generates a stable, canonical SHA256-based document ID from the lowercase
    absolute string path of the file. This handles duplicate filenames in
    different directories cleanly.
    """
    canonical_path = str(file_path.resolve()).lower().strip()
    return hashlib.sha256(canonical_path.encode('utf-8')).hexdigest()[:32]


@dataclass
class DocumentMetadata:
    doc_id: str
    name: str
    path: str
    extension: str
    folder: str
    size: int
    modified_time: float
    indexed_time: float = field(default_factory=time.time)
    content: Optional[str] = None

    @classmethod
    def from_file_path(cls, file_path: Path, content: Optional[str] = None) -> "DocumentMetadata":
        resolved = file_path.resolve()
        stat = resolved.stat()
        return cls(
            doc_id=generate_canonical_doc_id(resolved),
            name=resolved.name,
            path=str(resolved),
            extension=resolved.suffix.lower(),
            folder=resolved.parent.name,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            indexed_time=time.time(),
            content=content
        )

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "name": self.name,
            "path": self.path,
            "extension": self.extension,
            "folder": self.folder,
            "size": self.size,
            "modified_time": self.modified_time,
            "indexed_time": self.indexed_time,
            "has_content": bool(self.content)
        }
