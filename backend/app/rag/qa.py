import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from ollama import chat

from app.config import (
    OLLAMA_MODEL,
    QA_TOP_K,
    QA_DISTANCE_THRESHOLD,
)
from app.models import generate_canonical_doc_id
from app.rag.vector_store import VectorStore, VectorSearchResult


@dataclass
class DocumentQAResult:
    answer: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    source_chunks: List[Dict[str, Any]] = field(default_factory=list)
    grounded: bool = False
    not_found: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "source_chunks": self.source_chunks,
            "grounded": self.grounded,
            "not_found": self.not_found,
            "error": self.error,
        }


class DocumentQAService:
    """
    Phase 8 Grounded Document Q&A Service.
    Retrieves relevant semantic chunks ONLY from the active document, filters against distance thresholds,
    and queries local Ollama (qwen2.5:1.5b) using a strict grounding prompt.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        top_k: int = QA_TOP_K,
        distance_threshold: float = QA_DISTANCE_THRESHOLD,
        model_name: str = OLLAMA_MODEL,
    ):
        self.vector_store = vector_store or VectorStore()
        self.top_k = top_k
        self.distance_threshold = distance_threshold
        self.model_name = model_name

    def ask(
        self,
        question: str,
        document_path: Optional[Path] = None,
        document_id: Optional[str] = None,
    ) -> DocumentQAResult:
        # 1. Question validation
        if not question or not question.strip():
            return DocumentQAResult(
                answer="Empty question provided.",
                not_found=True,
                grounded=False,
            )

        # 2. Active document validation (ACTIVE DOCUMENT SAFETY)
        if not document_path and not document_id:
            return DocumentQAResult(
                answer="No active document selected. Please select or find a document first.",
                not_found=True,
                grounded=False,
            )

        # Resolve doc_id and doc_name
        doc_id = document_id
        doc_name = "Document"
        if document_path:
            resolved_path = document_path.resolve() if document_path.is_absolute() else document_path
            doc_id = doc_id or generate_canonical_doc_id(resolved_path)
            doc_name = document_path.name

        # 3. Document-Specific Semantic Retrieval (STRICT DOCUMENT FILTERING)
        results: List[VectorSearchResult] = self.vector_store.search_semantic(
            query=question,
            document_id=doc_id,
            limit=self.top_k,
        )

        # 4. Evidence Filtering against Distance Threshold
        valid_chunks = [res for res in results if res.distance <= self.distance_threshold]

        if not valid_chunks:
            return DocumentQAResult(
                answer="I couldn't find that information in the document.",
                document_id=doc_id,
                document_name=doc_name,
                not_found=True,
                grounded=False,
            )

        # 5. Context Construction
        context_parts = []
        source_chunks = []
        for idx, res in enumerate(valid_chunks):
            context_parts.append(f"[Chunk {idx + 1} - Index {res.chunk_index}]\n{res.text}")
            source_chunks.append({
                "chunk_index": res.chunk_index,
                "text": res.text,
                "distance": res.distance,
                "similarity": res.similarity,
            })

        grounded_context = "\n\n".join(context_parts)

        # 6. Grounded Ollama Generation Prompt
        system_prompt = """You are a grounded document question-answering assistant.
Answer the user's question using ONLY the provided CONTEXT below.

RULES:
- Answer ONLY using information explicitly supported by CONTEXT.
- Do NOT invent, speculate, or use outside knowledge.
- If the answer is not supported by CONTEXT, state clearly that it was not found in the document.
- Keep the answer concise and directly answer the question."""

        user_prompt = f"""CONTEXT:
{grounded_context}

QUESTION:
{question}"""

        try:
            response = chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            ans = response.message.content.strip()

            if not ans:
                return DocumentQAResult(
                    answer="I couldn't find that information in the document.",
                    document_id=doc_id,
                    document_name=doc_name,
                    source_chunks=source_chunks,
                    not_found=True,
                    grounded=False,
                )

            return DocumentQAResult(
                answer=ans,
                document_id=doc_id,
                document_name=doc_name,
                source_chunks=source_chunks,
                grounded=True,
                not_found=False,
            )

        except Exception as err:
            err_str = str(err)
            if "ConnectError" in err_str or "Connection refused" in err_str or "failed to connect" in err_str.lower() or "10061" in err_str:
                msg = "Ollama is not running. Please start Ollama locally to enable document Q&A."
            elif "not found" in err_str.lower() or "404" in err_str:
                msg = f"Ollama model '{self.model_name}' was not found. Please run 'ollama pull {self.model_name}'."
            else:
                msg = f"Error querying local AI model: {err}"

            return DocumentQAResult(
                answer=msg,
                document_id=doc_id,
                document_name=doc_name,
                source_chunks=source_chunks,
                grounded=False,
                not_found=False,
                error=str(err),
            )

    def ask_stream(
        self,
        question: str,
        document_path: Optional[Path] = None,
        document_id: Optional[str] = None,
    ):
        """
        Streaming generator for Grounded Document Q&A.
        Yields incremental SSE-friendly event dictionaries:
        - {"type": "meta", ...}
        - {"type": "token", "content": "..."}
        - {"type": "done", "result": DocumentQAResult}
        """
        # 1. Question validation
        if not question or not question.strip():
            res = DocumentQAResult(
                answer="Empty question provided.",
                not_found=True,
                grounded=False,
            )
            yield {"type": "meta", "data": res.to_dict()}
            yield {"type": "token", "content": res.answer}
            yield {"type": "done", "result": res}
            return

        # 2. Active document validation
        if not document_path and not document_id:
            res = DocumentQAResult(
                answer="No active document selected. Please select or find a document first.",
                not_found=True,
                grounded=False,
            )
            yield {"type": "meta", "data": res.to_dict()}
            yield {"type": "token", "content": res.answer}
            yield {"type": "done", "result": res}
            return

        doc_id = document_id
        doc_name = "Document"
        if document_path:
            resolved_path = document_path.resolve() if document_path.is_absolute() else document_path
            doc_id = doc_id or generate_canonical_doc_id(resolved_path)
            doc_name = document_path.name

        # 3. Document-Specific Semantic Retrieval
        results: List[VectorSearchResult] = self.vector_store.search_semantic(
            query=question,
            document_id=doc_id,
            limit=self.top_k,
        )

        # 4. Evidence Filtering against Distance Threshold
        valid_chunks = [res for res in results if res.distance <= self.distance_threshold]

        if not valid_chunks:
            res = DocumentQAResult(
                answer="I couldn't find that information in the document.",
                document_id=doc_id,
                document_name=doc_name,
                not_found=True,
                grounded=False,
            )
            yield {"type": "meta", "data": res.to_dict()}
            yield {"type": "token", "content": res.answer}
            yield {"type": "done", "result": res}
            return

        # 5. Context Construction
        context_parts = []
        source_chunks = []
        for idx, res in enumerate(valid_chunks):
            context_parts.append(f"[Chunk {idx + 1} - Index {res.chunk_index}]\n{res.text}")
            source_chunks.append({
                "chunk_index": res.chunk_index,
                "text": res.text,
                "distance": res.distance,
                "similarity": res.similarity,
            })

        grounded_context = "\n\n".join(context_parts)
        yield {
            "type": "meta",
            "data": {
                "document_id": doc_id,
                "document_name": doc_name,
                "source_chunks": source_chunks,
                "grounded": True,
                "not_found": False,
            }
        }

        # 6. Grounded Ollama Generation Prompt
        system_prompt = """You are a grounded document question-answering assistant.
Answer the user's question using ONLY the provided CONTEXT below.

RULES:
- Answer ONLY using information explicitly supported by CONTEXT.
- Do NOT invent, speculate, or use outside knowledge.
- If the answer is not supported by CONTEXT, state clearly that it was not found in the document.
- Keep the answer concise and directly answer the question."""

        user_prompt = f"""CONTEXT:
{grounded_context}

QUESTION:
{question}"""

        full_answer = []
        try:
            stream = chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
            )
            for chunk in stream:
                token = chunk.message.content
                if token:
                    full_answer.append(token)
                    yield {"type": "token", "content": token}

            ans = "".join(full_answer).strip()
            if not ans:
                ans = "I couldn't find that information in the document."
                not_found = True
                grounded = False
            else:
                not_found = False
                grounded = True

            final_res = DocumentQAResult(
                answer=ans,
                document_id=doc_id,
                document_name=doc_name,
                source_chunks=source_chunks,
                grounded=grounded,
                not_found=not_found,
            )
            yield {"type": "done", "result": final_res}

        except Exception as err:
            err_str = str(err)
            if "ConnectError" in err_str or "Connection refused" in err_str or "failed to connect" in err_str.lower() or "10061" in err_str:
                msg = "Ollama is not running. Please start Ollama locally to enable document Q&A."
            elif "not found" in err_str.lower() or "404" in err_str:
                msg = f"Ollama model '{self.model_name}' was not found. Please run 'ollama pull {self.model_name}'."
            else:
                msg = f"Error querying local AI model: {err}"

            final_res = DocumentQAResult(
                answer=msg,
                document_id=doc_id,
                document_name=doc_name,
                source_chunks=source_chunks,
                grounded=False,
                not_found=False,
                error=str(err),
            )
            yield {"type": "token", "content": msg}
            yield {"type": "done", "result": final_res}
