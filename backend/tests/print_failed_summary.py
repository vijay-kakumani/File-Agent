import json

with open('backend/tests/results/v2_2_benchmark_results.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

failed = [c for c in d['search_cases'] if not c['is_correct']]
print(f"EXACT FAILED CASES IN V2.2: {len(failed)}")
for idx, c in enumerate(failed, 1):
    print(f"\n{idx}. [{c['id']}] {c['category']} | Status: {c['status']} | Confidence: {c['confidence']}")
    print(f"   Query:             '{c['query']}'")
    print(f"   Expected:          {c['expected_document']}")
    print(f"   Actual:            {c['actual_document']}")
    print(f"   Parsed Query:      '{c['parser_query']}'")
    print(f"   Folder Constraint: {c['folder_constraint']}")
    print(f"   Extension Filter:  {c['extension_filter']}")
    print(f"   Behavior:          Expected: {c['expected_behavior']} | Actual: {c['actual_behavior']} (Matched: {c['behavior_matched']})")
