import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(r"D:\one piece\jimbe\FA\backend").resolve()
sys.path.insert(0, str(backend_dir))

os.environ["DOCUMENT_AGENT_DATA_DIR"] = r"D:\one piece\jimbe\FA\data"

from app.agent.service import DocumentAgentService
from app.agent.intent_parser import IntentParser
from app.services import state_service, search_service
from app.rag.qa import DocumentQAService
from app.rag.summarizer import DocumentSummarizer

print("=" * 60)
print("PHASE V5.5 PERFORMANCE MEASUREMENT SUITE")
print("=" * 60)

# 1. SEARCH LATENCY
print("\n--- 1. Search Latency ---")
queries = [
    "internship report",
    "normalization",
    "DBMS",
    "agile methodologies",
    "machine learning"
]

cold_search_latencies = []
for q in queries:
    t0 = time.perf_counter()
    res = search_service.search_candidates(query=q, limit=5)
    t_ms = (time.perf_counter() - t0) * 1000
    cold_search_latencies.append(t_ms)

warm_search_latencies = []
for q in queries:
    t0 = time.perf_counter()
    res = search_service.search_candidates(query=q, limit=5)
    t_ms = (time.perf_counter() - t0) * 1000
    warm_search_latencies.append(t_ms)

print(f"Mean Cold Search Latency: {sum(cold_search_latencies)/len(cold_search_latencies):.2f} ms")
print(f"Mean Warm Search Latency: {sum(warm_search_latencies)/len(warm_search_latencies):.2f} ms")

# Select a test document from corpus or data
from app.db import get_all_documents
docs = get_all_documents()
test_doc = None
if docs:
    for d in docs:
        p = Path(d.path)
        if p.exists() and p.suffix.lower() in [".txt", ".pdf", ".docx", ".md"]:
            test_doc = p
            break

if not test_doc:
    test_doc = Path(r"D:\one piece\jimbe\FA\scratch\sample_doc.txt")
    test_doc.write_text("This document describes database normalization, first normal form (1NF), second normal form (2NF), and third normal form (3NF). Normalization eliminates data redundancy and prevents update anomalies. Key technologies include PostgreSQL, SQLite, and MySQL.")

print(f"Test Document for RAG/QA: {test_doc}")
state_service.set_active_document(test_doc)

# 2. Q&A MEASUREMENTS (COLD & WARM, FIRST TOKEN, COMPLETION)
print("\n--- 2. Q&A Latency & Streaming ---")
qa_svc = DocumentQAService()
question = "What does this document discuss about normalization?"

# Cold QA
t0 = time.perf_counter()
first_token_time = None
tokens = []
try:
    for ev in qa_svc.ask_stream(question=question, document_path=test_doc):
        if ev.get("type") == "token" and first_token_time is None:
            first_token_time = time.perf_counter()
        if ev.get("type") == "token":
            tokens.append(ev.get("content", ""))
    t_total_cold = (time.perf_counter() - t0) * 1000
    ttft_cold = ((first_token_time - t0) * 1000) if first_token_time else t_total_cold
    print(f"Cold QA TTFT (First Token): {ttft_cold:.2f} ms")
    print(f"Cold QA Total Completion: {t_total_cold:.2f} ms")
except Exception as e:
    print(f"QA execution notice (Ollama check): {e}")

# Warm QA
t0 = time.perf_counter()
first_token_time = None
tokens = []
try:
    for ev in qa_svc.ask_stream(question=question, document_path=test_doc):
        if ev.get("type") == "token" and first_token_time is None:
            first_token_time = time.perf_counter()
        if ev.get("type") == "token":
            tokens.append(ev.get("content", ""))
    t_total_warm = (time.perf_counter() - t0) * 1000
    ttft_warm = ((first_token_time - t0) * 1000) if first_token_time else t_total_warm
    print(f"Warm QA TTFT (First Token): {ttft_warm:.2f} ms")
    print(f"Warm QA Total Completion: {t_total_warm:.2f} ms")
except Exception as e:
    print(f"QA execution notice (Ollama check): {e}")

# 3. SUMMARIZATION MEASUREMENTS
print("\n--- 3. Summarization Latency & Streaming ---")
sum_svc = DocumentSummarizer()

t0 = time.perf_counter()
first_token_time = None
try:
    for ev in sum_svc.summarize_file_stream(test_doc):
        if ev.get("type") == "token" and first_token_time is None:
            first_token_time = time.perf_counter()
    t_total_sum = (time.perf_counter() - t0) * 1000
    ttft_sum = ((first_token_time - t0) * 1000) if first_token_time else t_total_sum
    print(f"Summarization TTFT (First Token): {ttft_sum:.2f} ms")
    print(f"Summarization Total Completion: {t_total_sum:.2f} ms")
except Exception as e:
    print(f"Summarization notice (Ollama check): {e}")

print("\nPerformance measurement complete.")
