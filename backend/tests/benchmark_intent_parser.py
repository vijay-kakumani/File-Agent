import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.agent import IntentParser, DocumentAgentService
from app.db import initialize_database, upsert_document
from app.models import DocumentMetadata, generate_canonical_doc_id


def run_intent_parser_benchmark():
    print("==================================================")
    print("PHASE 7 BENCHMARK: INTENT PARSER & AGENT INTEGRATION")
    print("==================================================")

    temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = Path(temp_dir.name) / "benchmark_agent.db"
    chroma_dir = Path(temp_dir.name) / "benchmark_chroma"
    initialize_database(db_path)

    # Seed mock document in SQLite DB
    doc = DocumentMetadata(
        doc_id=generate_canonical_doc_id(Path("/downloads/Nikhil_CS_Resume.pdf")),
        name="Nikhil_CS_Resume.pdf",
        path=str(Path("/downloads/Nikhil_CS_Resume.pdf").resolve()),
        extension=".pdf",
        folder="downloads",
        size=2048,
        modified_time=1000.0,
        indexed_time=1000.0,
        content="Nikhil CS resume detailing Python, machine learning, and software development skills.",
    )
    upsert_document(doc, db_path=db_path)

    parser = IntentParser()

    test_queries = [
        "I have a pdf in downloads about agile methodologies, find it",
        "Find my resume in the desktop folder",
        "There is a document somewhere in my college folder about python internship, can you find it?",
        "I think I saved a file called Nikil CS in downloads",
        "Find the document about Agile and open it",
        "Where is my internship report?",
        "Find my internship report and tell me where it is",
        "Find my internship report and summarize it",
        "Open it",
        "Read it",
        "What technologies were used?",
        "Summarize this document",
    ]

    # 1. Deterministic Parsing Latency Benchmark over 1000 iterations
    iterations = 100
    print(f"\nRunning {iterations} iterations per query over {len(test_queries)} natural language requests...")

    deterministic_count = 0
    llm_count = 0
    total_det_time = 0.0

    with patch("app.agent.intent_parser.chat") as mock_chat:
        start_t = time.perf_counter()
        for q in test_queries:
            for _ in range(iterations):
                parsed = parser.parse(q)
                if parsed.parser_source == "DETERMINISTIC":
                    deterministic_count += 1
                else:
                    llm_count += 1
        total_det_time = time.perf_counter() - start_t

        llm_calls_made = mock_chat.call_count

    total_parses = len(test_queries) * iterations
    avg_det_ms = (total_det_time / total_parses) * 1000.0
    det_percentage = (deterministic_count / total_parses) * 100.0

    print("--------------------------------------------------")
    print(f"Total Requests Processed        : {total_parses}")
    print(f"Handled Deterministically       : {deterministic_count} ({det_percentage:.1f}%)")
    print(f"Ollama LLM Calls Made           : {llm_calls_made}")
    print(f"Total Parse Execution Time      : {total_det_time:.4f} s")
    print(f"Average Deterministic Latency   : {avg_det_ms:.4f} ms per request")
    print("--------------------------------------------------")

    # 2. End-to-End Request Execution Benchmark
    print("\n--------------------------------------------------")
    print("END-TO-END REQUEST EXECUTION SAMPLES")
    print("--------------------------------------------------")

    service = DocumentAgentService(parser=parser)
    with patch("file_search.os.startfile") as mock_startfile, \
         patch("app.search.ranker.get_all_documents", return_value=[doc]):

        sample_requests = [
            "I think I saved a file called Nikil CS in downloads",
            "Find the document about Agile and open it",
            "Where is my internship report?",
        ]

        for req in sample_requests:
            start_e2e = time.perf_counter()
            parsed = parser.parse(req)
            result = service.execute_request(parsed)
            elapsed_e2e = (time.perf_counter() - start_e2e) * 1000.0

            print(f"Request: '{req}'")
            print(f"  Parsed Intent : {parsed.intent.value}")
            print(f"  Extracted Query: '{parsed.query}'")
            print(f"  Folder        : {parsed.folder_constraint}")
            print(f"  Extension     : {parsed.extension_filter}")
            print(f"  Follow-Up     : {parsed.follow_up_action}")
            print(f"  Latency       : {elapsed_e2e:.2f} ms\n")

    try:
        temp_dir.cleanup()
    except Exception:
        pass
    print("==================================================")


if __name__ == "__main__":
    run_intent_parser_benchmark()
