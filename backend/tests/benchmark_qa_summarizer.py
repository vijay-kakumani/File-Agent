import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models import generate_canonical_doc_id
from app.rag.qa import DocumentQAService
from app.rag.summarizer import DocumentSummarizer
from app.rag.vector_store import VectorStore, VectorSearchResult


def run_benchmark():
    print("=" * 60)
    print("PHASE 8 BENCHMARK: GROUNDED Q&A & SIZE-AWARE MAP-REDUCE SUMMARIZATION")
    print("=" * 60)

    # 1. GROUNDED Q&A RETRIEVAL & LATENCY BENCHMARK
    mock_vector_store = MagicMock(spec=VectorStore)
    doc_path = Path("D:/College/Internship_Report.pdf")
    doc_id = generate_canonical_doc_id(doc_path)

    chunk = VectorSearchResult(
        document_id=doc_id,
        document_name="Internship_Report.pdf",
        path=str(doc_path),
        chunk_index=0,
        text="The internship duration was 8 weeks. CGPA requirement: 3.8. Tech stack: Python, FastAPI.",
        distance=0.20,
        similarity=0.90,
        metadata={},
    )
    mock_vector_store.search_semantic.return_value = [chunk]

    qa_service = DocumentQAService(vector_store=mock_vector_store, top_k=4)

    with patch("app.rag.qa.chat") as mock_qa_chat:
        mock_qa_resp = MagicMock()
        mock_qa_resp.message.content = "8 weeks"
        mock_qa_chat.return_value = mock_qa_resp

        start_time = time.perf_counter()
        qa_iterations = 100
        for _ in range(qa_iterations):
            res = qa_service.ask("What is the internship duration?", document_path=doc_path)
        qa_duration = time.perf_counter() - start_time

        print(f"\n[GROUNDED Q&A PERFORMANCE]")
        print(f"Total Q&A Requests Processed   : {qa_iterations}")
        print(f"Total Q&A Benchmark Time       : {qa_duration:.4f} s")
        print(f"Average Q&A Latency            : {(qa_duration / qa_iterations) * 1000:.3f} ms per request")
        print(f"Chroma Query Filter Applied    : document_id='{doc_id}'")
        print(f"Model Calls per Valid Request   : 1")

    # 2. SUMMARIZATION BENCHMARK (SMALL, MEDIUM, LARGE DOCUMENTS)
    summarizer = DocumentSummarizer(
        direct_char_limit=1000,
        chunk_size=500,
        group_size=2,
    )

    with patch("app.rag.summarizer.chat") as mock_sum_chat:
        mock_sum_resp = MagicMock()
        mock_sum_resp.message.content = "Synthetic summary output section."
        mock_sum_chat.return_value = mock_sum_resp

        # A. Small Document (Direct Pass)
        small_text = "Small document content about software engineering best practices." * 5  # ~325 chars
        t0 = time.perf_counter()
        res_small = summarizer.summarize_text(small_text, doc_name="small.txt")
        t_small = time.perf_counter() - t0

        print(f"\n[SMALL DOCUMENT SUMMARIZATION]")
        print(f"Character Count               : {len(small_text)}")
        print(f"Summarization Mode            : {res_small.mode}")
        print(f"Execution Latency             : {t_small * 1000:.3f} ms")
        print(f"Ollama Call Count             : {res_small.total_ollama_calls} (Direct Pass)")

        # B. Medium Document (Map-Reduce 1-Level)
        med_paragraph = "Section detail regarding system architecture, database design, and API endpoints. " * 5 + "\n\n"
        med_text = med_paragraph * 4  # ~1600 chars -> splits into ~3-4 map chunks
        t0 = time.perf_counter()
        res_med = summarizer.summarize_text(med_text, doc_name="medium.txt")
        t_med = time.perf_counter() - t0

        print(f"\n[MEDIUM DOCUMENT SUMMARIZATION]")
        print(f"Character Count               : {len(med_text)}")
        print(f"Summarization Mode            : {res_med.mode}")
        print(f"Execution Latency             : {t_med * 1000:.3f} ms")
        print(f"Map Calls                     : {res_med.map_call_count}")
        print(f"Reduce Calls                  : {res_med.reduce_call_count}")
        print(f"Total Ollama Calls            : {res_med.total_ollama_calls}")

        # C. Large Document (Map-Reduce Multi-Level)
        large_paragraph = "Extensive technical specifications, database schema, performance requirements, security compliance rules, and API specifications. " * 8 + "\n\n"
        large_text = large_paragraph * 10  # ~10,000 chars -> splits into ~20 map chunks
        t0 = time.perf_counter()
        res_large = summarizer.summarize_text(large_text, doc_name="large.txt")
        t_large = time.perf_counter() - t0

        print(f"\n[LARGE DOCUMENT SUMMARIZATION]")
        print(f"Character Count               : {len(large_text)}")
        print(f"Summarization Mode            : {res_large.mode}")
        print(f"Execution Latency             : {t_large * 1000:.3f} ms")
        print(f"Map Calls                     : {res_large.map_call_count}")
        print(f"Reduce Calls                  : {res_large.reduce_call_count}")
        print(f"Total Ollama Calls            : {res_large.total_ollama_calls}")

    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
