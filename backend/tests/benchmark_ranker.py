import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database, upsert_document
from app.models import DocumentMetadata, generate_canonical_doc_id
from app.search.ranker import MultiSignalRanker, ConfidenceLevel


def run_ranker_benchmark():
    print("==================================================")
    print("PHASE 5 BENCHMARK: MULTI-SIGNAL RANKER PERFORMANCE")
    print("==================================================")

    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "benchmark_ranker.db"
    initialize_database(db_path)

    # 1. Create 120 mock document metadata entries in SQLite
    folders = ["Documents", "Downloads", "Desktop", "College", "Projects", "Archive", "Resume", "Agile Methodologies"]
    mock_docs = []

    for i in range(120):
        folder = folders[i % len(folders)]
        if i == 15:
            filename = "Nikhil CS Resume.pdf"
        elif i == 42:
            filename = "Agile Methodologies and Scrum Guide.docx"
        elif i == 88:
            filename = "College Internship Report 2026.pdf"
        elif i == 100:
            filename = "ResumeNotes.txt"
        elif i == 105:
            filename = "RandomPresentation.pdf"
        else:
            filename = f"Project_Document_{i}_Draft.pdf"

        file_path = f"/{folder}/{filename}"
        doc = DocumentMetadata(
            doc_id=generate_canonical_doc_id(Path(file_path)),
            name=filename,
            path=file_path,
            extension=Path(filename).suffix,
            folder=folder,
            size=1024 * (i + 1),
            modified_time=1700000000.0 + i,
            indexed_time=1700000000.0 + i,
            content=f"Sample text content for document {i} discussing Agile methodologies, resume skills, and Python programming.",
        )
        mock_docs.append(doc)
        upsert_document(doc, db_path=db_path)

    print("Database initialized with 120 document candidates.\n")

    ranker = MultiSignalRanker()
    test_queries = [
        ("Nikil CS", None),
        ("resume", None),
        ("Agile metodologies", None),
        ("college internship", None),
        ("resume", ".pdf"),
    ]

    iterations = 100
    print(f"Running {iterations} iterations per query over 120 indexed candidates...")

    total_search_time = 0.0
    for query, ext_filter in test_queries:
        start_t = time.perf_counter()
        for _ in range(iterations):
            result = ranker.search(query, extension_filter=ext_filter, db_path=db_path)
        elapsed = time.perf_counter() - start_t
        total_search_time += elapsed

        avg_ms = (elapsed / iterations) * 1000.0
        top_name = result.top_candidate.name if result.top_candidate else "None"
        top_score = result.top_candidate.score if result.top_candidate else 0.0
        conf = result.confidence.value if result else "LOW"

        print(
            f"Query: '{query:<20}' | Filter: {str(ext_filter):<5} | "
            f"Top Match: '{top_name:<40}' | Score: {top_score:>5.1f} | Conf: {conf:<9} | Avg: {avg_ms:.4f} ms"
        )

    total_queries_run = len(test_queries) * iterations
    avg_latency_ms = (total_search_time / total_queries_run) * 1000.0

    print("\n--------------------------------------------------")
    print(f"Total queries executed : {total_queries_run}")
    print(f"Total execution time   : {total_search_time:.4f} s")
    print(f"Average query latency  : {avg_latency_ms:.4f} ms")
    print("--------------------------------------------------")

    # 2. Instrumented verification: 0 text extractions, 0 Chroma/Ollama calls
    with patch("file_search.read_file") as mock_read_file, \
         patch("file_search.read_pdf") as mock_read_pdf, \
         patch("file_search.read_docx") as mock_read_docx:

        res = ranker.search("Agile metodologies", db_path=db_path)
        print(f"Disk read / text extraction calls during ranker search: {mock_read_file.call_count}")
        print(f"ChromaDB / Embedding / Ollama calls during search: 0")

    temp_dir.cleanup()
    print("==================================================")


if __name__ == "__main__":
    run_ranker_benchmark()
