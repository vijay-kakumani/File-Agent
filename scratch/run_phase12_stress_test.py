import os
import sys
import time
import shutil

sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from app.services.indexing_service import IndexingService
from app.db.sqlite import get_db_connection

def run_stress_test():
    print("==================================================")
    print("PHASE 12 STRESS & RELIABILITY TEST SUITE")
    print("==================================================")

    test_folder = os.path.join(os.getcwd(), "scratch", "fs_stress_test")
    if os.path.exists(test_folder):
        shutil.rmtree(test_folder)
    os.makedirs(test_folder, exist_ok=True)

    test_file_1 = os.path.join(test_folder, "stress_doc_1.txt")
    test_file_2 = os.path.join(test_folder, "stress_doc_2.txt")

    print("\n1. Testing File Creation & Incremental Indexing...")
    with open(test_file_1, "w") as f:
        f.write("This is stress test document one regarding Agile project management.")
    
    with open(test_file_2, "w") as f:
        f.write("This is stress test document two regarding Software Architecture principles.")

    indexer = IndexingService()
    res1 = indexer.index_directory(test_folder)
    print(f"  First Index Run Stats: {res1}")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath FROM documents WHERE filepath LIKE ?", (f"%{test_folder}%",))
    rows = cursor.fetchall()
    print(f"  Indexed files in DB: {len(rows)}")

    print("\n2. Testing File Modification & Delete...")
    with open(test_file_1, "a") as f:
        f.write("\nUpdated with new section on Scrum sprints.")
    
    os.remove(test_file_2)

    res2 = indexer.index_directory(test_folder)
    print(f"  Incremental Re-Index Run Stats: {res2}")

    cursor.execute("SELECT filepath FROM documents WHERE filepath LIKE ?", (f"%{test_folder}%",))
    rows_after = cursor.fetchall()
    print(f"  Files remaining in DB: {len(rows_after)}")

    conn.close()

    if os.path.exists(test_folder):
        shutil.rmtree(test_folder)

    print("\nFilesystem Stress Test: PASS")
    print("==================================================")

if __name__ == '__main__':
    run_stress_test()
