import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from ollama import chat

from app.config import (
    OLLAMA_MODEL,
    SUPPORTED_EXTENSIONS,
    SUMMARIZATION_DIRECT_CHAR_LIMIT,
    SUMMARIZATION_CHUNK_SIZE,
    SUMMARIZATION_CHUNK_OVERLAP,
    SUMMARIZATION_REDUCE_GROUP_SIZE,
    SUMMARIZATION_MAX_REDUCE_LEVELS,
)
from app.documents.extractor import extract_text


@dataclass
class SummarizeResult:
    summary: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    mode: str = "DIRECT"  # "DIRECT" or "MAP_REDUCE"
    map_call_count: int = 0
    reduce_call_count: int = 0
    total_ollama_calls: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "mode": self.mode,
            "map_call_count": self.map_call_count,
            "reduce_call_count": self.reduce_call_count,
            "total_ollama_calls": self.total_ollama_calls,
            "error": self.error,
        }


def _split_text_for_map(text: str, chunk_size: int = SUMMARIZATION_CHUNK_SIZE, overlap: int = SUMMARIZATION_CHUNK_OVERLAP) -> List[str]:
    """
    Splits document text into clean paragraphs/sections for Map summarization pass.
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

    # Secondary fallback slicing for monolithic text without paragraphs
    final_chunks = []
    for c in chunks:
        if len(c) > chunk_size * 2:
            step = max(100, chunk_size - overlap)
            for i in range(0, len(c), step):
                sub = c[i:i + chunk_size]
                if sub:
                    final_chunks.append(sub)
        else:
            final_chunks.append(c)

    return final_chunks if final_chunks else [text[:chunk_size]]


class DocumentSummarizer:
    """
    Phase 8 Size-Aware Map-Reduce Document Summarizer.
    - Small documents (<= direct_char_limit): Single-pass grounded direct summary.
    - Large documents (> direct_char_limit): Map-Reduce hierarchical summarization.
      MAP: Summarizes chunks independently into intermediate summaries.
      REDUCE: Combines intermediate summaries hierarchically until manageable context size, then produces final summary.
    """

    def __init__(
        self,
        direct_char_limit: int = SUMMARIZATION_DIRECT_CHAR_LIMIT,
        chunk_size: int = SUMMARIZATION_CHUNK_SIZE,
        group_size: int = SUMMARIZATION_REDUCE_GROUP_SIZE,
        model_name: str = OLLAMA_MODEL,
    ):
        self.direct_char_limit = direct_char_limit
        self.chunk_size = chunk_size
        self.group_size = group_size
        self.model_name = model_name

    def summarize_text(
        self,
        text: str,
        doc_name: str = "document",
        style: str = "standard",
    ) -> SummarizeResult:
        # 1. Empty document check
        if not text or not text.strip():
            return SummarizeResult(
                summary="Document is empty.",
                document_name=doc_name,
                mode="DIRECT",
                total_ollama_calls=0,
                error="Empty document",
            )

        clean_text = text.strip()

        # 2. Small Document: Direct Single-Pass Summarization
        if len(clean_text) <= self.direct_char_limit:
            return self._summarize_direct(clean_text, doc_name=doc_name)

        # 3. Large Document: Map-Reduce Summarization
        return self._summarize_map_reduce(clean_text, doc_name=doc_name)

    def summarize_file(
        self,
        file_path: Path,
        style: str = "standard",
    ) -> SummarizeResult:
        if not file_path.exists():
            return SummarizeResult(
                summary="File does not exist.",
                document_name=file_path.name,
                mode="DIRECT",
                error="File not found",
            )

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return SummarizeResult(
                summary="Unsupported document type.",
                document_name=file_path.name,
                mode="DIRECT",
                error="Unsupported file type",
            )

        try:
            text = extract_text(file_path)
            if not text or not text.strip():
                return SummarizeResult(
                    summary="Document is empty.",
                    document_name=file_path.name,
                    mode="DIRECT",
                    error="Empty document content",
                )
            return self.summarize_text(text, doc_name=file_path.name, style=style)
        except Exception as err:
            return SummarizeResult(
                summary=f"Could not read document: {err}",
                document_name=file_path.name,
                mode="DIRECT",
                error=str(err),
            )

    def _summarize_direct(self, text: str, doc_name: str) -> SummarizeResult:
        system_prompt = """You are a precise, grounded document summarizer.
Summarize the provided document text accurately and concisely.

RULES:
- Rely strictly on the text provided below.
- Do NOT invent facts, speculate, or use outside knowledge.
- Preserve key names, numbers, dates, main findings, and conclusions.
- Keep the summary clean, cohesive, and concise."""

        user_prompt = f"DOCUMENT ({doc_name}):\n{text}"

        try:
            response = chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            summary_out = response.message.content.strip()

            if not summary_out:
                return SummarizeResult(
                    summary="Model returned an empty summary.",
                    document_name=doc_name,
                    mode="DIRECT",
                    total_ollama_calls=1,
                    error="Empty model response",
                )

            return SummarizeResult(
                summary=summary_out,
                document_name=doc_name,
                mode="DIRECT",
                map_call_count=0,
                reduce_call_count=1,
                total_ollama_calls=1,
            )

        except Exception as err:
            err_str = str(err)
            if "ConnectError" in err_str or "Connection refused" in err_str or "failed to connect" in err_str.lower() or "10061" in err_str:
                msg = "Ollama is not running. Please start Ollama locally to enable summarization."
            elif "not found" in err_str.lower() or "404" in err_str:
                msg = f"Ollama model '{self.model_name}' was not found. Please run 'ollama pull {self.model_name}'."
            else:
                msg = f"Error generating summary: {err}"

            return SummarizeResult(
                summary=msg,
                document_name=doc_name,
                mode="DIRECT",
                error=str(err),
            )

    def _summarize_map_reduce(self, text: str, doc_name: str) -> SummarizeResult:
        chunks = _split_text_for_map(text, chunk_size=self.chunk_size)
        if not chunks:
            return self._summarize_direct(text[:self.direct_char_limit], doc_name)

        # STAGE 1: MAP PASS
        intermediate_summaries = []
        map_calls = 0

        map_system_prompt = """You are a section summarizer for a large document.
Summarize the section below concisely, preserving all key facts, names, numbers, dates, and metrics."""

        for i, chunk in enumerate(chunks):
            try:
                map_resp = chat(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": map_system_prompt},
                        {"role": "user", "content": f"SECTION {i + 1}:\n{chunk}"},
                    ],
                )
                map_calls += 1
                content = map_resp.message.content.strip()
                if content:
                    intermediate_summaries.append(content)
            except Exception as err:
                print(f"Warning: Map chunk {i} failed: {err}")
                continue

        if not intermediate_summaries:
            return SummarizeResult(
                summary="Map stage failed to produce section summaries.",
                document_name=doc_name,
                mode="MAP_REDUCE",
                map_call_count=map_calls,
                reduce_call_count=0,
                total_ollama_calls=map_calls,
                error="Map stage failure",
            )

        # STAGE 2: REDUCE PASS (Hierarchical if necessary)
        reduce_calls = 0
        current_summaries = intermediate_summaries
        level = 0

        reduce_system_prompt = """You are a document summarizer synthesizing section summaries into a single cohesive final document summary.

RULES:
- Stay strictly grounded in the provided section summaries.
- Avoid repetition and remove minor details.
- Preserve key names, dates, metrics, and core conclusions."""

        while len("\n\n".join(current_summaries)) > self.direct_char_limit and level < SUMMARIZATION_MAX_REDUCE_LEVELS and len(current_summaries) > 1:
            level += 1
            next_summaries = []
            # Group into batches of self.group_size
            for idx in range(0, len(current_summaries), self.group_size):
                batch = current_summaries[idx:idx + self.group_size]
                batch_text = "\n---\n".join(batch)
                try:
                    group_resp = chat(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": reduce_system_prompt},
                            {"role": "user", "content": f"COMBINED SECTION SUMMARIES:\n{batch_text}"},
                        ],
                    )
                    reduce_calls += 1
                    res_text = group_resp.message.content.strip()
                    if res_text:
                        next_summaries.append(res_text)
                except Exception as err:
                    print(f"Warning: Reduce level {level} batch failed: {err}")
                    next_summaries.extend(batch)

            current_summaries = next_summaries if next_summaries else current_summaries

        # FINAL REDUCE STEP
        combined_text = "\n---\n".join(current_summaries)
        try:
            final_resp = chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": reduce_system_prompt},
                    {"role": "user", "content": f"SECTION SUMMARIES:\n{combined_text}"},
                ],
            )
            reduce_calls += 1
            final_summary = final_resp.message.content.strip()

            if not final_summary:
                final_summary = combined_text

            return SummarizeResult(
                summary=final_summary,
                document_name=doc_name,
                mode="MAP_REDUCE",
                map_call_count=map_calls,
                reduce_call_count=reduce_calls,
                total_ollama_calls=map_calls + reduce_calls,
            )

        except Exception as err:
            err_str = str(err)
            if "ConnectError" in err_str or "Connection refused" in err_str or "failed to connect" in err_str.lower() or "10061" in err_str:
                msg = "Ollama is not running. Please start Ollama locally to enable summarization."
            elif "not found" in err_str.lower() or "404" in err_str:
                msg = f"Ollama model '{self.model_name}' was not found. Please run 'ollama pull {self.model_name}'."
            else:
                msg = f"Error in reduce stage: {err}"

            return SummarizeResult(
                summary=msg,
                document_name=doc_name,
                mode="MAP_REDUCE",
                map_call_count=map_calls,
                reduce_call_count=reduce_calls,
                total_ollama_calls=map_calls + reduce_calls,
                error=str(err),
            )

    def summarize_file_stream(
        self,
        file_path: Path,
        style: str = "standard",
    ):
        """
        Streaming generator for file summarization.
        """
        if not file_path.exists():
            res = SummarizeResult(
                summary="File does not exist.",
                document_name=file_path.name,
                mode="DIRECT",
                error="File not found",
            )
            yield {"type": "token", "content": res.summary}
            yield {"type": "done", "result": res}
            return

        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            res = SummarizeResult(
                summary="Unsupported document type.",
                document_name=file_path.name,
                mode="DIRECT",
                error="Unsupported file type",
            )
            yield {"type": "token", "content": res.summary}
            yield {"type": "done", "result": res}
            return

        try:
            text = extract_text(file_path)
            if not text or not text.strip():
                res = SummarizeResult(
                    summary="Document is empty.",
                    document_name=file_path.name,
                    mode="DIRECT",
                    error="Empty document content",
                )
                yield {"type": "token", "content": res.summary}
                yield {"type": "done", "result": res}
                return
            for event in self.summarize_text_stream(text, doc_name=file_path.name, style=style):
                yield event
        except Exception as err:
            res = SummarizeResult(
                summary=f"Could not read document: {err}",
                document_name=file_path.name,
                mode="DIRECT",
                error=str(err),
            )
            yield {"type": "token", "content": res.summary}
            yield {"type": "done", "result": res}

    def summarize_text_stream(
        self,
        text: str,
        doc_name: str = "document",
        style: str = "standard",
    ):
        """
        Streaming generator for text summarization.
        """
        if not text or not text.strip():
            res = SummarizeResult(
                summary="Document is empty.",
                document_name=doc_name,
                mode="DIRECT",
                total_ollama_calls=0,
                error="Empty document",
            )
            yield {"type": "token", "content": res.summary}
            yield {"type": "done", "result": res}
            return

        clean_text = text.strip()

        # Direct Single-Pass Summarization Stream
        if len(clean_text) <= self.direct_char_limit:
            system_prompt = """You are a precise, grounded document summarizer.
Summarize the provided document text accurately and concisely.

RULES:
- Rely strictly on the text provided below.
- Do NOT invent facts, speculate, or use outside knowledge.
- Preserve key names, numbers, dates, main findings, and conclusions.
- Keep the summary clean, cohesive, and concise."""

            user_prompt = f"DOCUMENT ({doc_name}):\n{clean_text}"

            yield {
                "type": "meta",
                "data": {
                    "document_name": doc_name,
                    "mode": "DIRECT",
                }
            }

            full_tokens = []
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
                        full_tokens.append(token)
                        yield {"type": "token", "content": token}

                summary_out = "".join(full_tokens).strip()
                if not summary_out:
                    summary_out = "Model returned an empty summary."
                    err = "Empty model response"
                else:
                    err = None

                res = SummarizeResult(
                    summary=summary_out,
                    document_name=doc_name,
                    mode="DIRECT",
                    map_call_count=0,
                    reduce_call_count=1,
                    total_ollama_calls=1,
                    error=err,
                )
                yield {"type": "done", "result": res}
                return
            except Exception as err:
                err_str = str(err)
                if "ConnectError" in err_str or "Connection refused" in err_str or "failed to connect" in err_str.lower() or "10061" in err_str:
                    msg = "Ollama is not running. Please start Ollama locally to enable summarization."
                elif "not found" in err_str.lower() or "404" in err_str:
                    msg = f"Ollama model '{self.model_name}' was not found. Please run 'ollama pull {self.model_name}'."
                else:
                    msg = f"Error generating summary: {err}"
                res = SummarizeResult(
                    summary=msg,
                    document_name=doc_name,
                    mode="DIRECT",
                    error=str(err),
                )
                yield {"type": "token", "content": msg}
                yield {"type": "done", "result": res}
                return

        # Large Document: Map-Reduce mode
        yield {"type": "status", "content": "Large document detected. Running section analysis..."}
        res = self._summarize_map_reduce(clean_text, doc_name=doc_name)
        yield {"type": "token", "content": res.summary}
        yield {"type": "done", "result": res}
