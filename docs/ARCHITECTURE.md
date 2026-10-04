# Local AI Document Agent Backend Architecture

This document describes the canonical backend service architecture, module responsibilities, state ownership, data flow, API contracts, and indexing lifecycle for the Local AI Document Agent.

---

## 1. High-Level Architecture Diagram

```
FastAPI REST Endpoints (backend/main.py)
   │
   ▼
DocumentAgentService (backend/app/agent/service.py) ── [Orchestrator]
   │
   ├── IntentParser (backend/app/agent/intent_parser.py)
   │
   ├── SearchService (backend/app/services/search_service.py)
   │     ├── SQLite/FTS5 Index (backend/app/db/)
   │     ├── RapidFuzz Matcher (backend/app/search/fuzzy_engine.py)
   │     ├── MultiSignalRanker (backend/app/search/ranker.py)
   │     └── Persistent ChromaDB (backend/app/rag/vector_store.py)
   │
   ├── StateService (backend/app/services/state_service.py) ── [Active Document State]
   │
   ├── DocumentService (backend/app/services/document_service.py) ── [Win32 os.startfile]
   │
   ├── DocumentQAService (backend/app/rag/qa.py) ── [Grounded RAG Q&A]
   │
   └── DocumentSummarizer (backend/app/rag/summarizer.py) ── [Map-Reduce Summarizer]
```

---

## 2. Service Responsibilities & Boundaries

### A. Application Orchestrator
- **`DocumentAgentService`** (`backend/app/agent/service.py`):
  - Primary application-level entry point.
  - Consumes `ParsedRequest` models from `IntentParser` and delegates action execution to domain services.
  - Manages search candidate ranking, ambiguity resolution, and follow-up action execution.

### B. Core Domain Services
- **`StateService`** (`backend/app/services/state_service.py`):
  - Centralized singleton maintaining active document state (`active_document_path`, `active_doc_id`).
  - Ensures all modules (`main.py`, `file_search.py`, `DocumentAgentService`, `qa.py`, `summarizer.py`) share identical active document context.

- **`DocumentService`** (`backend/app/services/document_service.py`):
  - Responsible for document reading, location reporting, and Win32 file opening.
  - Contains the **single canonical implementation of native file opening** (`os.startfile()`).

- **`SearchService`** (`backend/app/services/search_service.py`):
  - Unified search boundary coordinating SQLite FTS5 lexical search, RapidFuzz fuzzy matching, `MultiSignalRanker`, and ChromaDB semantic retrieval.

- **`IndexingService`** (`backend/app/services/indexing_service.py`):
  - Canonical ownership of file indexing lifecycle. Wraps `IncrementalIndexer` to update SQLite/FTS5 metadata and synchronize ChromaDB vector collections.

- **`HealthService`** (`backend/app/services/health_service.py`):
  - Provides diagnostic probes for API status, SQLite DB connection, ChromaDB vector store directory, Ollama model reachability, and active search root counts.

### C. Intelligence & RAG Services
- **`DocumentQAService`** (`backend/app/rag/qa.py`):
  - Grounded question-answering service. Queries ChromaDB filtered strictly by `document_id`, applies L2 distance thresholds, and enforces grounding rules via Ollama (`qwen2.5:1.5b`).

- **`DocumentSummarizer`** (`backend/app/rag/summarizer.py`):
  - Size-aware summarization engine. Uses single-pass direct summarization for small documents ($\le 4000$ chars) and hierarchical Map-Reduce summarization for large documents.

---

## 3. Data Flow Execution Sequence

### Standard Request Flow
1. User sends message via `POST /api/chat`.
2. `FastAPI` routes message to `DocumentAgentService.process_message()`.
3. `IntentParser` evaluates deterministic rules $\rightarrow$ falls back to Ollama `chat()` if confidence is low $\rightarrow$ produces `ParsedRequest`.
4. `DocumentAgentService` invokes domain services based on `intent`:
   - `FIND`: `SearchService` $\rightarrow$ sets `StateService` active document $\rightarrow$ executes follow-up action.
   - `ASK`: `DocumentQAService` $\rightarrow$ retrieves chunks for `active_doc_id` $\rightarrow$ calls Ollama grounding prompt.
   - `SUMMARIZE`: `DocumentSummarizer` $\rightarrow$ Direct or Map-Reduce pass $\rightarrow$ returns summary.
   - `OPEN`: `DocumentService.open_native_file()` $\rightarrow$ calls Win32 `os.startfile()`.
5. `DocumentAgentService` wraps response into `AgentResult`.
6. `FastAPI` returns standardized JSON object (`success`, `intent`, `response`, `current_document`, `search_results`).

---

## 4. API Endpoints Contract

- `POST /api/chat`: Primary interaction endpoint. Returns `{"success": bool, "response": str, "intent": str, "ambiguous": bool, "current_document": dict, "search_results": list}`.
- `GET /api/current-document`: Returns active document metadata.
- `POST /api/select-document`: Explicitly selects active document path and optionally opens native file.
- `POST /api/refresh`: Triggers incremental rescan and re-indexing.
- `GET /api/health`: Diagnostic status endpoint.

---

## 5. Backwards Compatibility Facades

- **`backend/file_search.py`**: Legacy facade module delegating all active document, search, reading, indexing, and agent requests to `StateService`, `DocumentService`, `SearchService`, `IndexingService`, and `DocumentAgentService`.
- **`backend/rag.py`**: Legacy RAG facade delegating vector storage and document Q&A to `VectorStore` and `DocumentQAService`.

---

## 6. Native Tauri Desktop Shell & Windows Integration

```
┌───────────────────────────────────────────────────────────┐
│                    Tauri Desktop Shell                    │
│  (Rust native window: 1000x720, titlebar, Win32 frame)     │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                     React UI                        │  │
│  │     (Vite production build served locally)          │  │
│  │   ThinkingOrb | MetalFx | Search | Chat UI          │  │
│  └──────────────────────────┬──────────────────────────┘  │
└─────────────────────────────┼─────────────────────────────┘
                              │ HTTP / REST API Calls
                              ▼
┌───────────────────────────────────────────────────────────┐
│                 Localhost FastAPI Backend                 │
│                 (http://127.0.0.1:8000/api)               │
│                                                           │
│  DocumentAgentService -> SearchService -> DocumentService │
│                                                │          │
│                                           os.startfile()  │
└────────────────────────────────────────────────┬──────────┘
                                                 │ Win32 API
                                                 ▼
                                     Native Desktop Application
                                      (PDF Viewer / Word / etc)
```

### Desktop Shell & Communication Model
- **Tauri v2 Shell**: Custom Windows desktop app shell configured via `src-tauri/tauri.conf.json`. Window specifications: 1000x720 initial dimensions, centered, minimum 800x600, native Windows frame.
- **Frontend Layer**: Built using Vite (`npm run build` -> `frontend/dist`). Hosted locally by Tauri's webview engine. Communicates with local backend via standard REST HTTP fetch calls configured by `VITE_API_BASE_URL` (defaulting to `http://127.0.0.1:8000/api`).
- **Backend Service Layer**: FastAPI server running locally on `http://127.0.0.1:8000`. Handles document search, vector storage, RAG Q&A, and intent parsing.
- **Native File Execution**: `DocumentService.open_native_file()` uses Python's standard `os.startfile()` on Windows, allowing the native OS application to launch when the user asks to open a document or clicks "Open File". React UI invokes `POST /api/select-document` with `open_native=true` or `POST /api/chat` with open intent.

---

## 7. Real-World Performance & Reliability Baseline (Phase 12)

### Target Hardware Profile
- **OS**: Windows 11
- **CPU**: Intel 12th Generation Core i3
- **GPU**: Intel UHD Integrated Graphics (No dedicated GPU)
- **RAM**: 8 GB
- **Storage**: Local NVMe SSD

### Benchmark Performance Baseline
- **Exact Lexical Search** ("Find Nikhil CS.pdf"): `522 ms` (cold), `336 ms` (warm).
- **Typo-Tolerant Search** ("Find Nikil CS"): `73.9 ms` (cold), `65.7 ms` (warm).
- **Partial Stem Search** ("Find Nikhil"): `56.3 ms` (cold), `65.9 ms` (warm).
- **Folder-Constrained Search** ("Find my resume in Downloads"): `79.5 ms` (cold), `68.0 ms` (warm).
- **Drive-Constrained Search** ("Find my internship report in D:\College"): `65.9 ms` (cold), `73.9 ms` (warm).
- **Document Location Action**: `27.2 ms`.
- **Native Win32 File Open**: `190.0 ms`.
- **Grounded Q&A (Ollama `qwen2.5:1.5b`)**: `4,717.8 ms` (~4.7 seconds).
- **Absent Information Q&A**: `4,941.8 ms` (returns grounded absent-information notification).
- **Size-Aware Map-Reduce Summarization**: `144,254.3 ms` (~2.4 minutes on CPU for multi-pass hierarchical LLM summarization).
- **Incremental Rescan Baseline**: `216.9 ms` across 120 indexed files (0 unneeded extractions, 0 unneeded vector embeddings).

### Reliability & Verification Status
- **Filesystem Stress Test**: Verified dynamic sync for file creation, modification, and deletion (100% PASS).
- **Backend Unit Test Regression**: 123 / 123 tests passing (0 failures, 0 errors, 7.03s total suite runtime).


