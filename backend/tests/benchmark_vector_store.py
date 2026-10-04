import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from app.models import DocumentMetadata, generate_canonical_doc_id
from app.rag import VectorStore
from app.indexing import IncrementalIndexer


def run_vector_store_benchmark():
    print("==================================================")
    print("PHASE 6 BENCHMARK: PERSISTENT VECTOR STORE & RAG")
    print("==================================================")

    temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    root_dir = Path(temp_dir.name) / "test_docs"
    root_dir.mkdir(parents=True, exist_ok=True)

    chroma_dir = Path(temp_dir.name) / "benchmark_chroma"
    db_path = Path(temp_dir.name) / "benchmark_db.db"

    # 1. Create 30 test files with realistic text content
    print("Creating 30 test documents on disk...")
    topics = [
        ("Vijay_Resume.txt", "Resume CV for Vijay Kakumani. Experienced Python software developer with expertise in machine learning, FastAPI, SQLite, and computer science degree."),
        ("Agile_Scrum_Guide.txt", "Complete guide to Agile methodologies, Scrum framework, daily standups, sprint backlog planning, and product backlog management."),
        ("College_Internship_Report.txt", "Final college internship report on deep learning, computer vision, and neural network architectures."),
        ("Financial_Report_2026.txt", "Quarterly financial breakdown of revenue, operating expenditure, investments, and corporate tax reports."),
        ("Machine_Learning_Notes.txt", "Study notes on linear regression, decision trees, random forests, vector embeddings, and cosine similarity metrics."),
    ]

    for i in range(30):
        name, base_text = topics[i % len(topics)]
        file_path = root_dir / f"Doc_{i}_{name}"
        file_path.write_text(f"Document #{i}: {base_text}\nAdditional details for doc {i}.", encoding="utf-8")

    # 2. Benchmark First Indexing Pass (Embedding Generation)
    print("\n--------------------------------------------------")
    print("PASS 1: First Indexing Pass (New Documents)")
    print("--------------------------------------------------")
    indexer = IncrementalIndexer(db_path=db_path, chroma_dir=chroma_dir, enable_vectors=True)

    start_pass1 = time.perf_counter()
    res1 = indexer.scan_and_index(custom_roots=[root_dir])
    elapsed_pass1 = time.perf_counter() - start_pass1

    print(f"Newly Indexed Documents : {res1['newly_indexed']}")
    print(f"Total Discovered        : {res1['total_discovered']}")
    print(f"Pass 1 Execution Time   : {elapsed_pass1:.4f} s")

    # 3. Benchmark Second Indexing Pass (Unchanged Documents)
    print("\n--------------------------------------------------")
    print("PASS 2: Second Indexing Pass (Unchanged Documents)")
    print("--------------------------------------------------")
    start_pass2 = time.perf_counter()
    with patch.object(indexer.vector_store.model, "encode") as mock_encode, \
         patch("app.indexing.incremental_indexer.extract_text") as mock_extract:

        res2 = indexer.scan_and_index(custom_roots=[root_dir])
        elapsed_pass2 = time.perf_counter() - start_pass2

        print(f"Skipped Documents       : {res2['skipped']}")
        print(f"Pass 2 Execution Time   : {elapsed_pass2:.4f} s")
        print(f"Embedding Calls Count   : {mock_encode.call_count}")
        print(f"Text Extraction Count   : {mock_extract.call_count}")

    # 4. Benchmark Semantic Query Latency over 100 iterations
    print("\n--------------------------------------------------")
    print("SEMANTIC QUERY BENCHMARK")
    print("--------------------------------------------------")
    vector_store = indexer.vector_store
    queries = [
        "my CV and resume",
        "agile methodologies and scrum",
        "machine learning embeddings",
        "financial tax reports",
    ]

    iterations = 50
    total_query_time = 0.0
    for query in queries:
        start_q = time.perf_counter()
        for _ in range(iterations):
            results = vector_store.search_semantic(query, limit=3)
        elapsed_q = time.perf_counter() - start_q
        total_query_time += elapsed_q

        avg_ms = (elapsed_q / iterations) * 1000.0
        top_name = results[0].document_name if results else "None"
        top_sim = results[0].similarity if results else 0.0
        print(f"Query: '{query:<30}' | Top Result: '{top_name:<35}' | Sim: {top_sim:.4f} | Avg: {avg_ms:.4f} ms")

    avg_latency = (total_query_time / (len(queries) * iterations)) * 1000.0
    print(f"\nAverage Semantic Query Latency: {avg_latency:.4f} ms")

    # 5. Application Restart Persistence Benchmark
    print("\n--------------------------------------------------")
    print("RESTART PERSISTENCE VERIFICATION")
    print("--------------------------------------------------")
    del indexer
    del vector_store

    reopened_store = VectorStore(chroma_dir=chroma_dir)
    res_reopen = reopened_store.search_semantic("my CV", limit=1)
    if res_reopen:
        print(f"SUCCESS: Persistent ChromaDB reloaded! Top match: '{res_reopen[0].document_name}'")
    else:
        print("FAILURE: Vectors were lost on process restart!")

    try:
        temp_dir.cleanup()
    except Exception:
        pass
    print("==================================================")


if __name__ == "__main__":
    run_vector_store_benchmark()
