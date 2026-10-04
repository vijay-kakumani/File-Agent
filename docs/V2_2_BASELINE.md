# Phase V2.2 — Baseline Diagnostic Report

**Execution Date**: 2026-10-04  
**Benchmark Target**: Search & Document Intelligence v2 (Query Understanding + Target Resolution + Search Accuracy)  
**Existing Test Suite Baseline**: **129/129 PASSED** (0 failures, 0 errors, 36.25s)  
**200-Case V2 Benchmark Baseline**: **149/200 PASSED (74.5%)**  
- Search Overall Accuracy: **53.0%** (53/100)
- Search Wrong-Document Rate: **22.0%** (22 cases)
- Search Intent Accuracy: **95.0%** (95/100)
- Document QA Accuracy: **96.0%** (96/100)
- QA Not-Found Accuracy: **100.0%**
- Cross-Document Contamination: **0 cases**
- Mean Search Latency: **197.11 ms**
- Mean QA Retrieval Latency: **16.78 ms**

---

## 1. Existing Test Suite Results

The full application regression suite was executed via pytest:
```
backend/tests/test_agent_integration.py .......... [  7%]
backend/tests/test_db_fts.py ............          [ 17%]
backend/tests/test_document_qa.py ..............   [ 27%]
backend/tests/test_fuzzy_search.py ...........     [ 36%]
backend/tests/test_incremental_indexing.py ....... [ 41%]
backend/tests/test_intent_parser.py .............  [ 61%]
backend/tests/test_opening_behavior.py ......      [ 65%]
backend/tests/test_ranker.py ...................   [ 80%]
backend/tests/test_summarizer.py ...........       [ 89%]
backend/tests/test_vector_store.py ..............  [100%]
====================== 129 passed, 3 warnings in 36.25s =======================
```
All existing core features remain completely intact and functional.

---

## 2. 200-Case V2 Benchmark Baseline Breakdown

### 2.1 Search Benchmark Breakdown (100 Cases across 25 Categories)

| Category | Total | Correct | Wrong Doc | No Match / Ambiguous | Accuracy |
|---|:---:|:---:|:---:|:---:|:---:|
| `EXACT_FILENAME` | 4 | 4 | 0 | 0 | 100.0% |
| `PARTIAL_FILENAME` | 4 | 4 | 0 | 0 | 100.0% |
| `FILENAME_TYPO` | 4 | 1 | 1 | 2 | 25.0% |
| `MISSING_CHARACTER` | 4 | 2 | 1 | 1 | 50.0% |
| `EXTRA_CHARACTER` | 4 | 2 | 0 | 2 | 50.0% |
| `TRANSPOSED_CHARACTERS` | 4 | 1 | 2 | 1 | 25.0% |
| `BAD_GRAMMAR` | 4 | 0 | 2 | 2 | 0.0% |
| `SHORTHAND` | 4 | 2 | 2 | 0 | 50.0% |
| `CONVERSATIONAL_LANGUAGE` | 4 | 2 | 1 | 1 | 50.0% |
| `FILLER_HEAVY_LANGUAGE` | 4 | 0 | 2 | 2 | 0.0% |
| `VAGUE_MEMORY` | 4 | 0 | 2 | 2 | 0.0% |
| `CONTENT_DESCRIPTION` | 4 | 2 | 0 | 2 | 50.0% |
| `FOLDER_CONSTRAINED` | 4 | 4 | 0 | 0 | 100.0% |
| `C_DRIVE_CONSTRAINT` | 4 | 4 | 0 | 0 | 100.0% |
| `D_DRIVE_CONSTRAINT` | 4 | 2 | 1 | 1 | 50.0% |
| `DEEP_NESTED_FOLDER` | 4 | 2 | 1 | 1 | 50.0% |
| `FILE_TYPE_CONSTRAINT` | 4 | 3 | 0 | 1 | 75.0% |
| `MULTIPLE_CONSTRAINTS` | 4 | 3 | 1 | 0 | 75.0% |
| `SEMANTIC_WORDING_VARIATION` | 4 | 1 | 0 | 3 | 25.0% |
| `WHERE_DID_I_SAVE` | 4 | 0 | 2 | 2 | 0.0% |
| `SEARCH_PLUS_OPEN` | 4 | 3 | 1 | 0 | 75.0% |
| `SEARCH_PLUS_LOCATION` | 4 | 0 | 2 | 2 | 0.0% |
| `SEARCH_PLUS_SUMMARIZE` | 4 | 3 | 1 | 0 | 75.0% |
| `AMBIGUOUS_SEARCH` | 4 | 4 | 0 | 0 | 100.0% |
| `NO_RESULT_SEARCH` | 4 | 4 | 0 | 0 | 100.0% |

### 2.2 Document QA Benchmark Breakdown (100 Cases across 18 Categories)

| Category | Total | Correct | Wrong / Error | Contamination | Accuracy |
|---|:---:|:---:|:---:|:---:|:---:|
| `DIRECT_FACT` | 6 | 6 | 0 | 0 | 100.0% |
| `INFORMAL_FACT` | 6 | 6 | 0 | 0 | 100.0% |
| `LIST_EXTRACTION` | 6 | 6 | 0 | 0 | 100.0% |
| `YES_NO_VERIFICATION` | 6 | 6 | 0 | 0 | 100.0% |
| `EXPLANATION` | 6 | 6 | 0 | 0 | 100.0% |
| `SUMMARY` | 6 | 6 | 0 | 0 | 100.0% |
| `TARGETED_SUMMARY` | 6 | 6 | 0 | 0 | 100.0% |
| `INFORMATION_LOCATION` | 6 | 6 | 0 | 0 | 100.0% |
| `COUNTING` | 6 | 6 | 0 | 0 | 100.0% |
| `FILTERING` | 6 | 6 | 0 | 0 | 100.0% |
| `TOPIC_SYNTHESIS` | 6 | 6 | 0 | 0 | 100.0% |
| `PROCEDURAL_QUESTION` | 6 | 6 | 0 | 0 | 100.0% |
| `FOLLOW_UP_QUESTION` | 6 | 6 | 0 | 0 | 100.0% |
| `PRONOUN_CONTEXT_QUESTION` | 6 | 6 | 0 | 0 | 100.0% |
| `NOT_FOUND_QUESTION` | 6 | 6 | 0 | 0 | 100.0% |
| `MULTI_STEP_CONVERSATION` | 4 | 3 | 1 | 0 | 75.0% |
| `CROSS_DOCUMENT_ISOLATION` | 3 | 3 | 0 | 0 | 100.0% |
| `DOCUMENT_TARGET_REFERENCES` | 3 | 0 | 3 | 0 | **0.0%** |

---

## 3. Analysis of Target-Resolution & QA Failures

### 3.1 Loss of Document Reference in QA (`DOCUMENT_TARGET_REFERENCES` = 0%)
- **Failing Case `QA-GOLD-01`**: *"What tech I used in resume?"*
- **Failing Case `Q099`**: *"What was the duration in the internship report?"*
- **Failing Case `Q100`**: *"In Agile methodologies, what is Scrum?"*
- **Root Cause**:
  In `backend/app/agent/service.py`:
  ```python
  if parsed.intent == IntentType.ASK:
      if current_doc is None:
          return AgentResult(
              success=False,
              intent="ASK",
              message="No active document selected. Please select or find a document first.",
              error="No active document",
          )
  ```
  The system blindly demanded that an active document already be selected in `StateService`. It failed to inspect the user's question for named document references (`"in resume"`, `"in the internship report"`, `"In Agile methodologies"`). Because target resolution did not exist, the document reference was never resolved, leaving `current_doc` as `None` and immediately failing.

### 3.2 Conversational Filler & Shorthand Dilution in Search
- **Failing Case `S-GOLD-02`**: *"I have a PDF somewhere in Downloads about my internship, can you find it?"*
  - The query parser extracted query as `"internship"`, but folder constraint failed to handle nested directory and multiple matching files properly.
- **Failing Case `S026` (`BAD_GRAMMAR`)**: *"where is campusconect report file"*
  - The typo `"campusconect"` was stripped or scored with low confidence (<40.0) by the ranker, resulting in `WRONG_NO_MATCH`.
- **Failing Case `S030` (`SHORTHAND`)**: *"cc report"*
  - Acronym shorthand has 0 lexical overlap with `CampusConnect_Report.pdf`, so FTS and RapidFuzz return 0. Without target reference aliases or semantic resolution, shorthand fails.
- **Failing Case `S038` (`FILLER_HEAVY_LANGUAGE`)**: *"um hey can you please find that document about agile methodologies for me"*
  - Conversational filler words contaminated the query string.

### 3.3 Deep Path Constraint Incompatibilities
- **Failing Case `S-GOLD-04`**: *"Find my internship report in D:\College\4th Year\Internship"*
  - Path separator mismatches (forward vs backslash) and incomplete folder string matching prevented the ranker from identifying `Internship_Report_External.pdf` under `D_drive_sim/College/4th_Year/Internship`.

---

## 4. Relevant Current Architecture

```
User Message
    ↓
IntentParser.parse()
    ├── _parse_deterministic()
    │     ├── Regex Intent (FIND, LOCATION, OPEN, READ, ASK, SUMMARIZE)
    │     ├── Regex Win Path Extraction
    │     ├── Regex Extension Extraction (.pdf, .docx, .txt, .md)
    │     ├── Regex Folder Extraction (Downloads, Desktop, Documents, etc.)
    │     └── Query Cleaning (_extract_clean_query)
    └── _parse_llm_fallback() (Ollama qwen2.5:1.5b)
    ↓
DocumentAgentService.execute_request()
    ├── ASK: Demands current_doc != None (fails if not set)
    ├── SUMMARIZE: Checks current_doc or calls search_service
    ├── FIND: Calls search_service
    └── OPEN: Calls search_service then os.startfile()
    ↓
SearchService.search_candidates()
    ├── MultiSignalRanker.search()
    │     ├── FTS5 Search (search_all_fts)
    │     ├── SQLite Metadata Candidates (get_all_documents)
    │     ├── FuzzyEngine Scoring (RapidFuzz)
    │     └── Weighted Scoring + Gate
    └── Substring folder filtering
```

### Architectural Gaps Identified
1. **No Target Resolution Phase**: No intermediate step between intent parsing and search/QA to determine whether the target is `CURRENT_DOCUMENT`, an explicit `DOCUMENT_REFERENCE` (e.g. "resume", "internship report"), `SEARCH`, or `MULTIPLE_DOCUMENTS`.
2. **Missing Document-Reference Extraction in QA**: The parser does not separate question content from target document reference (`"What tech I used in my resume?"` -> `question: "what tech I used"`, `target: "resume"`).
3. **Rigid Folder Constraint Matching**: Folders are matched via basic substring without path normalization or hierarchical tree matching.
4. **Shorthand & Synonym Blindness**: No alias mapping or semantic fallback for standard user references like "cv", "resume", "ml notes", "cc report".
5. **Loss of Ambiguity Nuance**: Confidence scoring collapses ambiguous multi-matches into arbitrary picks or low-confidence rejections.

---

## 5. Next Steps for Phase V2.2

1. Implement `TargetResolver` and enrich `ParsedRequest` with `TargetType.DOCUMENT_REFERENCE`, `document_reference`, cleaned query, and cleaned question.
2. Implement conversational filler cleaning and shorthand/alias normalization.
3. Enhance `search_service` and `ranker` with deep path hierarchical constraint evaluation.
4. Update `DocumentAgentService` and `DocumentQAService` to automatically resolve document references before QA execution.
5. Add unit and integration test suites: `backend/tests/test_target_resolution.py` and `backend/tests/test_query_understanding.py`.
6. Run the 129 existing regression tests + full 200-case V2 benchmark, reporting verified improvements.
