import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path("backend").resolve()
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.intent_parser import IntentParser
from app.agent.service import DocumentAgentService
from app.services.state_service import state_service

def probe_queries():
    queries = [
        "Find the PDF about machine learning",
        "I remember a document about my internship",
        "Find the notes where I discussed normalization",
        "That report I saved last month",
        "The file from Downloads about agile",
        "Open the document we just found",
        "Where is the one I used for my project?",
        "Find the other PDF",
        "I don't remember the filename but it was about DBMS",
        "Find my assignment from yesterday",
        "That PDF from D drive",
        "Show me the document containing information about React",
        "Find the report I was working on recently",
        "Open my latest internship document",
        "Find something related to machine learning and open it"
    ]
    
    parser = IntentParser()
    svc = DocumentAgentService()
    
    print("--- PARSER PROBE ---")
    for q in queries:
        parsed = parser.parse(q)
        print(f"\nQuery: '{q}'")
        print(f"  -> Intent: {parsed.intent.value}, Target: {parsed.target.value if parsed.target else None}, FollowUp: {parsed.follow_up_action.value if parsed.follow_up_action else None}")
        print(f"  -> Ext: {parsed.extension_filter}, Folder: {parsed.folder_constraint}, Date: {parsed.date_constraint}")
        print(f"  -> Clean Query: '{parsed.query}'")

if __name__ == "__main__":
    probe_queries()
