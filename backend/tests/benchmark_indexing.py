import sys
import time
from pathlib import Path

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import initialize_database
from app.indexing.incremental_indexer import IncrementalIndexer

if __name__ == "__main__":
    print("=== PERFORMANCE BENCHMARK: INCREMENTAL INDEXING ===")
    
    bench_db_path = Path(__file__).resolve().parent / "bench_temp.db"
    if bench_db_path.exists():
        bench_db_path.unlink()

    indexer = IncrementalIndexer(db_path=bench_db_path)

    # First indexing run (Fresh Initial Indexing)
    print("\n[Run 1] Executing Fresh Initial Indexing Pass...")
    stats1 = indexer.scan_and_index()
    print(f"Discovered: {stats1['total_discovered']} files")
    print(f"Newly Indexed: {stats1['newly_indexed']} files")
    print(f"Updated: {stats1['updated']} files")
    print(f"Skipped: {stats1['skipped']} files")
    print(f"Deleted: {stats1['deleted']} files")
    print(f"Elapsed Time: {stats1['elapsed_seconds']} seconds")

    # Second indexing run (Unchanged Incremental Pass)
    print("\n[Run 2] Executing Incremental Pass 2 (No filesystem changes)...")
    stats2 = indexer.scan_and_index()
    print(f"Discovered: {stats2['total_discovered']} files")
    print(f"Newly Indexed: {stats2['newly_indexed']} files")
    print(f"Updated: {stats2['updated']} files")
    print(f"Skipped: {stats2['skipped']} files")
    print(f"Deleted: {stats2['deleted']} files")
    print(f"Elapsed Time: {stats2['elapsed_seconds']} seconds")

    # Clean up benchmark DB
    if bench_db_path.exists():
        try:
            bench_db_path.unlink()
        except Exception:
            pass
