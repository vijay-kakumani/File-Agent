import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from app.db import initialize_database, upsert_document, get_all_documents
from app.models import DocumentMetadata, generate_canonical_doc_id
from app.search import FuzzyEngine
from file_search import search_files


def run_search_benchmark():
    print("==================================================")
    print("PHASE 4 BENCHMARK: RAPIDFUZZ SEARCH PERFORMANCE")
    print("==================================================")

    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "benchmark_fuzzy.db"
    initialize_database(db_path)

    # 1. Create 120 mock document metadata entries
    mock_docs = []
    folders = ["Documents", "Downloads", "Desktop", "College", "Projects", "Archive"]

    for i in range(120):
        folder = folders[i % len(folders)]
        if i == 15:
            filename = "Nikhil CS Resume.pdf"
        elif i == 42:
            filename = "Agile Methodologies and Scrum Guide.docx"
        elif i == 88:
            filename = "College Internship Report 2026.pdf"
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
            content=f"Sample text content for document {i}",
        )
        mock_docs.append(doc)
        upsert_document(doc, db_path=db_path)

    docs = get_all_documents(limit=1000, db_path=db_path)
    print(f"Database initialized with {len(docs)} document candidates.\n")

    engine = FuzzyEngine()
    test_queries = [
        "Nikil CS",                   # 1-char typo
        "resme",                      # missing char
        "Agile metodologies",         # transposed char in multi-word
        "college internship",         # folder fuzzy query
        "Project_Document_50",        # partial match
    ]

    # 2. Benchmark RapidFuzz Search Latency over 100 iterations per query
    iterations = 100
    print(f"Running {iterations} iterations per query over {len(docs)} indexed candidates...")

    total_fuzzy_time = 0.0
    for query in test_queries:
        start_t = time.perf_counter()
        for _ in range(iterations):
            results = engine.search_candidates(query, docs)
        elapsed = time.perf_counter() - start_t
        total_fuzzy_time += elapsed
        avg_ms = (elapsed / iterations) * 1000
        top_match = results[0].document.name if results else "None"
        top_score = results[0].overall_score if results else 0.0
        print(f"Query: '{query:<22}' | Top Match: '{top_match:<40}' | Score: {top_score:>5.1f} | Avg: {avg_ms:.4f} ms")

    total_queries_run = len(test_queries) * iterations
    avg_query_latency_ms = (total_fuzzy_time / total_queries_run) * 1000

    print("\n--------------------------------------------------")
    print(f"Total queries executed : {total_queries_run}")
    print(f"Total execution time   : {total_fuzzy_time:.4f} s")
    print(f"Average query latency  : {avg_query_latency_ms:.4f} ms")
    print("--------------------------------------------------")

    # 3. Instrumented proof of 0 text extractions during search
    with patch("file_search.read_file") as mock_read_file, \
         patch("app.db.get_all_documents", return_value=docs):

        for query in test_queries:
            search_files(query)

        print(f"Disk read / text extraction calls during search: {mock_read_file.call_count}")

    temp_dir.cleanup()
    print("==================================================")


if __name__ == "__main__":
    run_search_benchmark()
