import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.intent_parser import IntentParser
from app.search.ranker import MultiSignalRanker
from app.db import initialize_database, get_all_documents, search_all_fts

RESULTS_FILE = Path("backend/tests/results/v2_2_benchmark_results.json")

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.intent_parser import IntentParser
from app.search.ranker import MultiSignalRanker
from app.db import initialize_database, get_all_documents
from app.indexing import IncrementalIndexer
from tests.fixtures.v2_benchmark.generate_corpus import generate_benchmark_corpus

RESULTS_FILE = Path("backend/tests/results/v2_2_benchmark_results.json")
CORPUS_DIR = Path("backend/tests/fixtures/v2_benchmark/corpus")

def audit():
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    search_cases = data["search_cases"]
    failed = [c for c in search_cases if not c["is_correct"]]
    
    print(f"============================================================")
    print(f"TOTAL FAILED SEARCH CASES: {len(failed)}")
    print(f"============================================================")

    # Setup isolated test db for tracing
    temp_dir = Path("backend/tests/fixtures/v2_benchmark/audit_env")
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / "audit_index.db"
    chroma_dir = temp_dir / "audit_chroma"
    initialize_database(db_path)
    generate_benchmark_corpus(CORPUS_DIR)

    search_roots = [
        CORPUS_DIR / "C_drive_sim",
        CORPUS_DIR / "D_drive_sim",
    ]
    indexer = IncrementalIndexer(db_path=db_path, chroma_dir=chroma_dir, enable_vectors=True)
    indexer.scan_and_index(custom_roots=search_roots, extract_content=True)

    parser = IntentParser()
    ranker = MultiSignalRanker()

    for idx, c in enumerate(failed, 1):
        print(f"\n============================================================")
        print(f"CASE {idx}/{len(failed)}: [{c['id']}] - Category: {c['category']}")
        print(f"============================================================")
        print(f"Query:              '{c['query']}'")
        print(f"Expected Document:  {c['expected_document']}")
        print(f"Actual Document:    {c['actual_document']}")
        print(f"Status:             {c['status']}")
        print(f"Expected Behavior:  {c['expected_behavior']} | Actual: {c['actual_behavior']}")

        parsed = parser.parse(c['query'])
        print(f"Parsed Intent:      {parsed.intent.value} (Confidence: {parsed.confidence.value})")
        print(f"Parsed Query:       '{parsed.query}'")
        print(f"Folder Constraint:  {parsed.folder_constraint}")
        print(f"Extension Filter:   {parsed.extension_filter}")
        print(f"Follow-up Action:   {parsed.follow_up_action.value if parsed.follow_up_action else None}")
        print(f"Date Constraint:    {parsed.date_constraint}")

        res = ranker.search(
            query=parsed.query or c['query'],
            extension_filter=parsed.extension_filter,
            folder_constraint=parsed.folder_constraint,
            db_path=db_path
        )

        print(f"Ranker Confidence:  {res.confidence.value}")
        print(f"Total Evaluated:    {res.total_candidates_evaluated}")
        print(f"Top 5 Candidates:")
        for rank, cand in enumerate(res.candidates[:5], 1):
            sig = cand.signals
            is_expected = False
            if isinstance(c['expected_document'], list):
                is_expected = cand.name in c['expected_document']
            else:
                is_expected = cand.name == c['expected_document']
            marker = " *** EXPECTED ***" if is_expected else ""
            print(f"  #{rank}: {cand.name} (Score: {cand.score}) [Folder: {cand.folder}]{marker}")
            print(f"      Signals: FTS={sig.fts_score}, Name={sig.filename_score}, Stem={sig.stem_score}, Folder={sig.folder_score}, Ext={sig.extension_score}")
            print(f"      Matches: ExactName={sig.exact_filename_match}, ExactStem={sig.exact_stem_match}, ExactFolder={sig.exact_folder_match}")

        # Check why expected document lost or was missing
        expected_docs = c['expected_document'] if isinstance(c['expected_document'], list) else [c['expected_document']]
        found_in_cands = [cand for cand in res.candidates if cand.name in expected_docs]
        if not found_in_cands:
            print(f"  >>> Expected doc was NOT in returned candidates at all!")
        else:
            exp_cand = found_in_cands[0]
            print(f"  >>> Expected doc '{exp_cand.name}' ranked below top because Score {exp_cand.score} < {res.top_candidate.score if res.top_candidate else 0}")

    # Cleanup audit env
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    audit()
