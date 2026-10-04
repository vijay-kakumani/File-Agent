import os
import sys
import time
import json
import psutil
import urllib.request

def get_uvicorn_memory_mb():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmd)
            if 'uvicorn' in cmd_str or ('python' in cmd_str and 'main:app' in cmd_str):
                return proc.memory_info().rss / (1024 * 1024), proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return 0.0, None

def measure_api(endpoint, payload=None, method='GET'):
    url = f"http://127.0.0.1:8000/api/{endpoint}"
    t0 = time.perf_counter()
    headers = {'Content-Type': 'application/json'}
    if payload:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
    else:
        req = urllib.request.Request(url, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            elapsed = (time.perf_counter() - t0) * 1000
            return elapsed, json.loads(res_body)
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        return elapsed, {"error": str(e)}

def run_benchmarks():
    print("==================================================")
    print("PHASE 12 EMPIRICAL BENCHMARKING SUITE")
    print("==================================================")
    mem_initial, pid = get_uvicorn_memory_mb()
    print(f"Backend Server Process PID: {pid} | Initial Memory: {mem_initial:.2f} MB")

    # 1. Health check baseline
    health_ms, health_res = measure_api("health")
    print(f"\n1. GET /api/health: {health_ms:.2f} ms | Response: {health_res.get('status')}")

    # 2. Search Latency Matrix
    queries = [
        ("EXACT", "Find Nikhil CS.pdf"),
        ("TYPO", "Find Nikil CS"),
        ("PARTIAL", "Find Nikhil"),
        ("FOLDER", "Find my resume in Downloads"),
        ("D_DRIVE", "Find my internship report in D:\\College"),
        ("NATURAL", "I have a PDF somewhere in Downloads about Agile methodologies, find it"),
        ("SEMANTIC", "Find my CV"),
        ("CONTENT", "Find the document containing Agile methodologies")
    ]

    print("\n2. Search Latency Benchmarks:")
    search_results = []
    for qtype, qtext in queries:
        cold_ms, cold_res = measure_api("chat", {"message": qtext}, method='POST')
        warm_ms, warm_res = measure_api("chat", {"message": qtext}, method='POST')
        
        intent = cold_res.get('intent', 'UNKNOWN')
        doc_count = len(cold_res.get('search_results', []))
        is_ambiguous = cold_res.get('ambiguous', False)
        
        print(f"  [{qtype:9s}] \"{qtext}\" -> Intent: {intent:8s} | Cold: {cold_ms:6.2f} ms | Warm: {warm_ms:6.2f} ms | Results: {doc_count}")
        search_results.append({
            "type": qtype,
            "query": qtext,
            "intent": intent,
            "cold_ms": cold_ms,
            "warm_ms": warm_ms,
            "results_count": doc_count,
            "ambiguous": is_ambiguous
        })

    mem_after_search, _ = get_uvicorn_memory_mb()
    print(f"Memory after searches: {mem_after_search:.2f} MB")

    # 3. Actions & LLM Benchmarks
    print("\n3. Document Actions Benchmarks:")
    action_queries = [
        ("LOCATION", "Where is it?"),
        ("OPEN", "Open it"),
        ("QA_PRESENT", "What is mentioned in the document?"),
        ("QA_ABSENT", "What is the CEO's name?"),
        ("SUMMARIZE", "Summarize it")
    ]

    action_results = []
    for atype, atext in action_queries:
        ms, res = measure_api("chat", {"message": atext}, method='POST')
        intent = res.get('intent', 'UNKNOWN')
        resp_preview = str(res.get('response', ''))[:80].replace('\n', ' ')
        print(f"  [{atype:10s}] \"{atext}\" -> Intent: {intent:8s} | Latency: {ms:8.2f} ms | Preview: {resp_preview}...")
        action_results.append({
            "type": atype,
            "query": atext,
            "intent": intent,
            "latency_ms": ms,
            "response_preview": resp_preview
        })

    mem_after_actions, _ = get_uvicorn_memory_mb()
    print(f"Memory after actions: {mem_after_actions:.2f} MB")

    # 4. Incremental Indexing Benchmark
    print("\n4. Indexing Benchmark (Unchanged Re-index):")
    idx_ms, idx_res = measure_api("refresh", method='POST')
    stats = idx_res.get('stats', {})
    print(f"  Unchanged Re-indexing Latency: {idx_ms:.2f} ms | Stats: {stats}")

    mem_final, _ = get_uvicorn_memory_mb()
    print(f"\nFinal Memory: {mem_final:.2f} MB")
    print("==================================================")

if __name__ == '__main__':
    run_benchmarks()
