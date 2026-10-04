import sys
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add current directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent import DocumentAgentService
from app.models import AgentResult, DocumentInfo
from app.services import (
    state_service,
    document_service,
    search_service,
    indexing_service,
    health_service,
)
import file_search  # Backwards compatibility facade module load

app = FastAPI(title="Local AI Document Agent API", version="2.0.0")

# Enable CORS for frontend interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Initializes SQLite schema immediately, then builds index asynchronously in background."""
    import threading
    from app.db import initialize_database

    try:
        initialize_database()
    except Exception as err:
        print(f"[STARTUP] Database initialization notice: {err}")

    def bg_index():
        try:
            count = indexing_service.build_file_index()
            print(f"[INDEXING] File index ready: {count} documents.")
        except Exception as err:
            print(f"[INDEXING] Background indexing notice: {err}")

    thread = threading.Thread(target=bg_index, daemon=True)
    thread.start()


class ChatRequest(BaseModel):
    message: str


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    success: bool
    intent: str
    message: str
    results: List[Dict[str, Any]]
    action: str
    current_document: Optional[Dict[str, Any]] = None
    ambiguous: bool = False
    document_count: Optional[int] = None


class SelectDocumentRequest(BaseModel):
    path: str
    open_file_flag: Optional[bool] = False


@app.get("/health")
@app.get("/api/health")
def health_check():
    """Diagnostic health check endpoint for SQLite, ChromaDB, Ollama, and active search roots."""
    try:
        status = health_service.check_health()
        res = status.to_dict()
        res["agent_ready"] = True
        return res
    except Exception as err:
        return {"status": "error", "agent_ready": False, "error": str(err)}


@app.get("/api/current-document")
def get_current_document():
    """Returns metadata for the currently active document."""
    active_info = state_service.get_active_document_info()
    return {"current_document": active_info}


@app.get("/api/documents")
def get_documents(query: Optional[str] = None):
    """Lists indexed documents or performs candidate search."""
    if query and query.strip():
        res = search_service.search_candidates(query=query, limit=20)
        docs = [
            DocumentInfo.from_path(c.path).to_dict()
            for c in res.candidates
        ]
        return {"documents": docs, "total_count": len(docs)}

    docs = indexing_service.get_indexed_documents(limit=100)
    return {"documents": docs, "total_count": indexing_service.get_count()}


@app.post("/api/refresh")
def refresh_index():
    """Triggers an incremental filesystem rescan and index update."""
    count = indexing_service.build_file_index()
    return {
        "message": f"File index refreshed. {count} documents found.",
        "document_count": count,
    }


@app.post("/api/select-document")
def select_document(req: SelectDocumentRequest):
    """Explicitly selects an active document and optionally opens it in Windows default app."""
    target_path = Path(req.path)
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="File does not exist")

    state_service.set_active_document(target_path)
    open_status = None
    if req.open_file_flag:
        open_status = document_service.open_native_file(target_path)

    return {
        "message": f"Selected document: {target_path.name}",
        "current_document": state_service.get_active_document_info(),
        "open_status": open_status,
    }


@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    """
    Primary agent interaction endpoint.
    Processes natural-language messages through DocumentAgentService orchestrator.
    """
    msg = req.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        agent_svc = DocumentAgentService()
        result = agent_svc.process_message(msg)

        # Convert AgentResult to clean standardized JSON response contract
        if isinstance(result, AgentResult):
            resp_text = result.message
            intent_str = result.intent
            ambiguous_flag = result.ambiguous
            candidates = result.search_candidates
            success_flag = result.success
        elif isinstance(result, dict):
            resp_text = result.get("open_status") or result.get("selected") or str(result)
            intent_str = "FIND"
            ambiguous_flag = False
            candidates = [{"path": m, "name": Path(m).name} for m in result.get("matches", [])]
            success_flag = True
        else:
            resp_text = str(result)
            intent_str = "UNKNOWN"
            ambiguous_flag = False
            candidates = []
            success_flag = True

        return {
            "success": success_flag,
            "response": resp_text,
            "intent": intent_str,
            "ambiguous": ambiguous_flag,
            "current_document": state_service.get_active_document_info(),
            "search_results": candidates,
            "document_count": indexing_service.get_count(),
        }

    except Exception as err:
        return {
            "success": False,
            "response": f"An error occurred while processing your request: {err}",
            "intent": "UNKNOWN",
            "ambiguous": False,
            "current_document": state_service.get_active_document_info(),
            "search_results": [],
            "document_count": indexing_service.get_count(),
            "error": str(err),
        }


def _determine_action(result: AgentResult, user_message: str) -> str:
    intent = (getattr(result, "intent", None) or "").upper()
    msg = (getattr(result, "message", None) or "").lower()
    user_lower = user_message.lower()

    if intent == "FIND":
        if "open" in user_lower or msg.startswith("opened:"):
            return "search_open"
        if "summariz" in user_lower or "overview" in user_lower:
            return "search_summarize"
        if "where" in user_lower or "location" in user_lower:
            return "search_location"
        return "search"
    elif intent == "OPEN":
        return "open"
    elif intent == "LOCATION":
        return "location"
    elif intent == "SUMMARIZE":
        return "summarize"
    elif intent == "ASK":
        return "ask"
    elif intent == "READ":
        return "read"
    elif intent == "REFRESH":
        return "refresh"
    return "unknown"


@app.post("/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest):
    """
    Primary V3 structured natural-language query endpoint.
    Processes queries through DocumentAgentService and returns structured response.
    """
    msg = req.query.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        agent_svc = DocumentAgentService()
        result = agent_svc.process_message(msg)

        if isinstance(result, AgentResult):
            resp_text = result.message
            intent_str = result.intent
            ambiguous_flag = result.ambiguous
            candidates = result.search_candidates or []
            success_flag = result.success
            action_str = _determine_action(result, msg)
            active_doc = result.active_document or state_service.get_active_document_info()
        elif isinstance(result, dict):
            resp_text = result.get("open_status") or result.get("selected") or str(result)
            intent_str = "FIND"
            ambiguous_flag = False
            candidates = [{"path": m, "name": Path(m).name} for m in result.get("matches", [])]
            success_flag = True
            action_str = "search_open" if "open" in msg.lower() else "search"
            active_doc = state_service.get_active_document_info()
        else:
            resp_text = str(result)
            intent_str = "UNKNOWN"
            ambiguous_flag = False
            candidates = []
            success_flag = True
            action_str = "unknown"
            active_doc = state_service.get_active_document_info()

        # Build clean results list
        results_list = []
        if candidates:
            for c in candidates:
                if isinstance(c, dict):
                    results_list.append({
                        "name": c.get("name") or Path(c.get("path", "")).name,
                        "path": c.get("path", ""),
                        "score": c.get("score", 1.0),
                        "folder": c.get("folder", ""),
                        "extension": c.get("extension", ""),
                    })
                else:
                    results_list.append({
                        "name": str(c),
                        "path": str(c),
                        "score": 1.0,
                        "folder": "",
                        "extension": "",
                    })
        elif active_doc and isinstance(active_doc, dict):
            results_list.append({
                "name": active_doc.get("name", ""),
                "path": active_doc.get("path", ""),
                "score": 1.0,
                "folder": active_doc.get("folder", ""),
                "extension": active_doc.get("extension", ""),
            })

        return QueryResponse(
            success=success_flag,
            intent=intent_str,
            message=resp_text,
            results=results_list,
            action=action_str,
            current_document=active_doc,
            ambiguous=ambiguous_flag,
            document_count=indexing_service.get_count(),
        )

    except Exception as err:
        return QueryResponse(
            success=False,
            intent="UNKNOWN",
            message=f"I couldn't complete that request: {err}",
            results=[],
            action="unknown",
            current_document=state_service.get_active_document_info(),
            ambiguous=False,
            document_count=indexing_service.get_count(),
        )


@app.post("/query/stream")
@app.post("/api/query/stream")
def query_stream_endpoint(req: QueryRequest):
    """
    Primary V5.3 real-time streaming endpoint.
    Streams incremental tokens as they are generated by Ollama.
    Preserves full compatibility with /query data models.
    """
    msg = req.query.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    agent_svc = DocumentAgentService()

    def event_stream():
        try:
            for event in agent_svc.process_message_stream(msg):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as err:
            err_payload = {"type": "error", "error": str(err)}
            yield f"data: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


if __name__ == "__main__":
    import multiprocessing
    import uvicorn
    multiprocessing.freeze_support()
    port = int(os.environ.get("DOCUMENT_AGENT_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
