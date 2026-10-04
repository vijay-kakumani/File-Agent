import json
import shutil
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.intent_parser import IntentParser
from app.search.ranker import MultiSignalRanker
from app.db import initialize_database
from app.indexing import IncrementalIndexer
from tests.fixtures.v2_benchmark.generate_corpus import generate_benchmark_corpus

temp_dir = Path("backend/tests/fixtures/v2_benchmark/audit_env_live")
temp_dir.mkdir(parents=True, exist_ok=True)
db_path = temp_dir / "audit_index.db"
chroma_dir = temp_dir / "audit_chroma"
initialize_database(db_path)
CORPUS_DIR = Path("backend/tests/fixtures/v2_benchmark/corpus")
generate_benchmark_corpus(CORPUS_DIR)
search_roots = [CORPUS_DIR / "C_drive_sim", CORPUS_DIR / "D_drive_sim"]
indexer = IncrementalIndexer(db_path=db_path, chroma_dir=chroma_dir, enable_vectors=True)
indexer.scan_and_index(custom_roots=search_roots, extract_content=True)

with open("backend/tests/fixtures/v2_benchmark/search_cases.json", "r", encoding="utf-8") as f:
    cases = json.load(f)

parser = IntentParser()
ranker = MultiSignalRanker()

failed = []
for c in cases:
    parsed = parser.parse(c["query"])
    res = ranker.search(
        parsed.query or c["query"],
        extension_filter=parsed.extension_filter,
        folder_constraint=parsed.folder_constraint,
        db_path=db_path
    )
    top_name = res.top_candidate.name if res.top_candidate else None
    exp = c["expected_document"]
    
    # Check behavior
    is_corr = False
    if c["expected_behavior"] == "AMBIGUOUS":
        if res.confidence.value == "AMBIGUOUS" or len(res.candidates) > 1:
            is_corr = True
        elif top_name and (top_name in exp if isinstance(exp, list) else top_name == exp):
            is_corr = True
    else:
        if top_name and (top_name in exp if isinstance(exp, list) else top_name == exp):
            is_corr = True

    if not is_corr:
        failed.append((c, parsed, res))

print(f"CURRENT DYNAMIC FAILED SEARCH CASES: {len(failed)}")
for idx, (c, p, r) in enumerate(failed, 1):
    top = r.top_candidate.name if r.top_candidate else "NONE"
    top_score = r.top_candidate.score if r.top_candidate else 0.0
    print(f"\n{idx}. [{c['id']}] {c['category']}")
    print(f"   Query:      '{c['query']}'")
    print(f"   Expected:   {c['expected_document']}")
    print(f"   Actual Top: {top} (Score: {top_score})")
    print(f"   Confidence: {r.confidence.value}")
    print(f"   Parsed:     Query='{p.query}', Folder='{p.folder_constraint}', Ext='{p.extension_filter}'")
    if r.candidates:
        print(f"   Top 3 Candidates:")
        for cand in r.candidates[:3]:
            print(f"     - {cand.name} (Score: {cand.score}) [Folder: {cand.folder}] | Signals: FTS={cand.signals.fts_score}, Name={cand.signals.filename_score}, Stem={cand.signals.stem_score}, Folder={cand.signals.folder_score}")

shutil.rmtree(temp_dir, ignore_errors=True)
