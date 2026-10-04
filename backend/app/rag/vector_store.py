import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

import chromadb
from sentence_transformers import SentenceTransformer

from app.config.settings import (
    CHROMA_DB_DIR,
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_PATH,
    resolve_embedding_model_path,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)
from app.models.document import DocumentMetadata


@dataclass
class VectorSearchResult:
    document_id: str
    document_name: str
    path: str
    chunk_index: int
    text: str
    distance: float
    similarity: float
    metadata: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "path": self.path,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "distance": round(self.distance, 4),
            "similarity": round(self.similarity, 4),
            "metadata": self.metadata,
        }


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Splits document text into chunks of chunk_size with overlap using paragraph boundaries.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 <= chunk_size:
            current_chunk = (current_chunk + "\n\n" + p).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = p

    if current_chunk:
        chunks.append(current_chunk)

    final_chunks = []
    for c in chunks:
        if len(c) > chunk_size * 2:
            for i in range(0, len(c), chunk_size - overlap):
                sub = c[i:i + chunk_size]
                if sub:
                    final_chunks.append(sub)
        else:
            final_chunks.append(c)

    return final_chunks if final_chunks else [text[:chunk_size]]


class VectorStore:
    """
    Persistent ChromaDB Vector Store for local document semantic search.
    Persists embeddings across application restarts using PersistentClient.
    Integrates with incremental indexing via stable document_id and chunk keys.
    """

    def __init__(self, chroma_dir: Optional[Path] = None, model_name: Optional[str] = None):
        self.chroma_dir = chroma_dir or CHROMA_DB_DIR
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self._collection = self._client.get_or_create_collection(name="documents")
        except Exception as err:
            import logging
            logging.error(f"ChromaDB initialization encountered: {err}")
            self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self._collection = self._client.get_or_create_collection(name="documents")

        target_model = model_name or EMBEDDING_MODEL_PATH
        self._model_name = resolve_embedding_model_path(target_model)
        self._model = None  # Lazy load embedding model

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def delete_document_vectors(self, doc_id: str) -> bool:
        """
        Removes all vector chunks belonging to a document_id.
        """
        if not doc_id:
            return False
        try:
            self._collection.delete(where={"document_id": doc_id})
            return True
        except Exception:
            return False

    def upsert_document_vectors(self, doc: DocumentMetadata, text: Optional[str] = None) -> int:
        """
        Chunks and embeds document text into persistent ChromaDB.
        Removes existing vectors for this document_id first to prevent stale chunks.
        """
        if not doc or not doc.doc_id:
            return 0

        # Always remove old chunks for this document first to maintain consistency
        self.delete_document_vectors(doc.doc_id)

        content = text if text is not None else doc.content
        if not content or not content.strip():
            return 0

        chunks = chunk_text(content)
        if not chunks:
            return 0

        # Stable chunk IDs: <document_id>_chunk_<index>
        chunk_ids = [f"{doc.doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "document_id": doc.doc_id,
                "document_name": doc.name,
                "absolute_path": doc.path,
                "folder": doc.folder,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        try:
            embeddings = self.model.encode(chunks)
            embeddings_list = embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings

            self._collection.add(
                ids=chunk_ids,
                embeddings=embeddings_list,
                documents=chunks,
                metadatas=metadatas,
            )
            return len(chunks)
        except Exception as err:
            print(f"Error embedding document {doc.name}: {err}")
            return 0

    def search_semantic(
        self,
        query: str,
        document_id: Optional[str] = None,
        limit: int = 5
    ) -> List[VectorSearchResult]:
        if not query or not query.strip():
            return []

        try:
            query_embedding = self.model.encode([query])
            query_list = query_embedding.tolist() if hasattr(query_embedding, "tolist") else query_embedding

            where_clause = {"document_id": document_id} if document_id else None

            results = self._collection.query(
                query_embeddings=query_list,
                n_results=limit,
                where=where_clause,
            )

            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            output = []
            for i in range(len(documents)):
                meta = metadatas[i] if i < len(metadatas) else {}
                dist = float(distances[i]) if i < len(distances) else 0.0
                sim = max(0.0, 1.0 - (dist / 2.0))

                output.append(
                    VectorSearchResult(
                        document_id=meta.get("document_id", ""),
                        document_name=meta.get("document_name", ""),
                        path=meta.get("absolute_path", ""),
                        chunk_index=meta.get("chunk_index", i),
                        text=documents[i],
                        distance=dist,
                        similarity=sim,
                        metadata=meta,
                    )
                )

            return output
        except Exception as err:
            print(f"Error executing semantic search: {err}")
            return []

    def get_document_chunk_count(self, doc_id: str) -> int:
        try:
            res = self._collection.get(where={"document_id": doc_id})
            return len(res.get("ids", []))
        except Exception:
            return 0
