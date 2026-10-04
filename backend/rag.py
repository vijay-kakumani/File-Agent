from pathlib import Path
from typing import Optional

from app.rag import VectorStore, DocumentQAService, DocumentSummarizer
from app.models import DocumentMetadata, generate_canonical_doc_id

# Instantiate shared singletons
vector_store = VectorStore()
qa_service = DocumentQAService(vector_store=vector_store)
summarizer_service = DocumentSummarizer()


def index_document(text: str, doc_name: str, document_key: str):
    """
    Compatibility function for indexing document into persistent ChromaDB.
    """
    file_path = Path(document_key)
    doc_id = generate_canonical_doc_id(file_path)

    doc_meta = DocumentMetadata(
        doc_id=doc_id,
        name=doc_name,
        path=str(file_path.resolve() if file_path.is_absolute() else file_path),
        extension=file_path.suffix.lower(),
        folder=file_path.parent.name if file_path.parent else "",
        size=len(text.encode("utf-8")),
        modified_time=0.0,
        indexed_time=0.0,
        content=text,
    )
    return vector_store.upsert_document_vectors(doc_meta, text=text)


def ask_document(query: str, document_key: str) -> str:
    """
    Retrieves grounded semantic context chunks from persistent ChromaDB for document_key
    and queries local Ollama using DocumentQAService.
    """
    file_path = Path(document_key)
    result = qa_service.ask(question=query, document_path=file_path)
    return result.answer