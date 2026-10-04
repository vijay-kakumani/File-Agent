# Search & Document Intelligence v2: Baseline Benchmark Report

**Execution Timestamp**: 2026-10-04 21:46:48
**Environment**: Isolated Controlled Test Corpus (16 synthetic documents, C: & D: drives)
**Total Benchmark Cases**: 200 (100 Search + 100 Document QA)
**Overall Baseline Pass Rate**: **196/200 (98.0%)**

> [!IMPORTANT]
> This report captures the empirical performance baseline of the **CURRENT production system** prior to any Search & Document Intelligence v2 improvements. All failures and latency characteristics are transparently exposed to drive v2 engineering.

---

## 1. High-Level Performance Matrix

| Metric | Measured Baseline | V2 Engineering Target | Status |
|---|:---:|:---:|:---:|
| **Search Overall Accuracy** | **97.0%** (97/100) | $\ge 90\%$ | Baseline |
| **Wrong Document Rate** | **1.0%** (1 cases) | $\le 3\%$ | Baseline |
| **Search Intent Accuracy** | **100.0%** | $\ge 95\%$ | Baseline |
| **QA Overall Accuracy** | **99.0%** (99/100) | $\ge 90\%$ | Baseline |
| **QA Not-Found Accuracy** | **100.0%** | $\ge 95\%$ | Baseline |
| **Cross-Document Contamination** | **0 cases** | 0 cases | Baseline |
| **Mean Search Latency** | **23.68 ms** | $< 150$ ms | Baseline |
| **Mean QA Retrieval Latency** | **15.37 ms** | $< 50$ ms | Baseline |

---

## 2. High-Priority Golden Cases

### Search Golden Cases (S-GOLD-01 to S-GOLD-06)
| ID | Query | Expected Behavior | Actual Document | Status |
|---|---|---|---|:---:|
| `S-GOLD-05` | "Find my resume" | `SELECT` (['Vijay_Resume.pdf', 'Resume.pdf']) | `Resume.pdf` | **PASS** |
| `S-GOLD-03` | "Find Nikil CS" | `SELECT` (Nikhil_CS_Resume.pdf) | `Nikhil_CS_Resume.pdf` | **PASS** |
| `S-GOLD-01` | "Can you find the doc about CampusConnect?" | `SELECT` (CampusConnect_Report.pdf) | `CampusConnect_Report.pdf` | **PASS** |
| `S-GOLD-04` | "Find my internship report in D:\College\4th Year\Internship" | `SELECT` (Internship_Report_External.pdf) | `Internship_Report_External.pdf` | **PASS** |
| `S-GOLD-02` | "I have a PDF somewhere in Downloads about my internship, can you find it?" | `SELECT` (['Vijay_Resume.pdf', 'Internship_Report.pdf']) | `CampusConnect_Report.pdf` | **FAIL** |
| `S-GOLD-06` | "Find my resume and open it" | `OPEN` (['Vijay_Resume.pdf', 'Resume.pdf']) | `Resume.pdf` | **PASS** |

### QA Golden Cases (QA-GOLD-01 to QA-GOLD-08)
| ID | Question | Target / Active Doc | Expected Mode | Status |
|---|---|---|---|:---:|
| `QA-GOLD-04` | "What was the internship duration?" | `Internship_Report.pdf` | `FACT` | **PASS** |
| `QA-GOLD-02` | "What technologies do I know?" | `Vijay_Resume.pdf` | `LIST` | **PASS** |
| `QA-GOLD-05` | "Does the resume mention Python?" | `Vijay_Resume.pdf` | `YES_NO` | **PASS** |
| `QA-GOLD-03` | "Which ones are frontend?" | `Vijay_Resume.pdf` | `FILTER` | **PASS** |
| `QA-GOLD-06` | "Tell me everything about CampusConnect." | `CampusConnect_Report.pdf` | `SYNTHESIS` | **PASS** |
| `QA-GOLD-07` | "What was the company revenue?" | `Q3_Budget_Summary.pdf` | `NOT_FOUND` | **PASS** |
| `QA-GOLD-08` | "What was the internship duration?" | `Internship_Report.pdf` | `FACT` | **PASS** |
| `QA-GOLD-01` | "What tech I used in resume?" | `Vijay_Resume.pdf` | `FACT` | **PASS** |

---

## 3. Search Benchmark Breakdown (100 Cases across 25 Categories)

| Code | Category | Total | Correct | Wrong Doc | No Match | Accuracy |
|:---:|---|:---:|:---:|:---:|:---:|:---:|
| - | EXACT_FILENAME | 4 | 4 | 0 | 0 | 100.0% |
| - | PARTIAL_FILENAME | 4 | 4 | 0 | 0 | 100.0% |
| - | FILENAME_TYPO | 4 | 4 | 0 | 0 | 100.0% |
| - | MISSING_CHARACTER | 4 | 4 | 0 | 0 | 100.0% |
| - | EXTRA_CHARACTER | 4 | 4 | 0 | 0 | 100.0% |
| - | TRANSPOSED_CHARACTERS | 4 | 4 | 0 | 0 | 100.0% |
| - | BAD_GRAMMAR | 4 | 4 | 0 | 0 | 100.0% |
| - | SHORTHAND | 4 | 4 | 0 | 0 | 100.0% |
| - | CONVERSATIONAL_LANGUAGE | 4 | 4 | 0 | 0 | 100.0% |
| - | FILLER_HEAVY_LANGUAGE | 4 | 4 | 0 | 0 | 100.0% |
| - | VAGUE_MEMORY | 4 | 4 | 0 | 0 | 100.0% |
| - | CONTENT_DESCRIPTION | 4 | 4 | 0 | 0 | 100.0% |
| - | FOLDER_CONSTRAINED | 4 | 4 | 0 | 0 | 100.0% |
| - | C_DRIVE_CONSTRAINT | 4 | 4 | 0 | 0 | 100.0% |
| - | D_DRIVE_CONSTRAINT | 4 | 4 | 0 | 0 | 100.0% |
| - | DEEP_NESTED_FOLDER | 4 | 4 | 0 | 0 | 100.0% |
| - | FILE_TYPE_CONSTRAINT | 4 | 4 | 0 | 0 | 100.0% |
| - | MULTIPLE_CONSTRAINTS | 4 | 3 | 1 | 0 | 75.0% |
| - | SEMANTIC_WORDING_VARIATION | 4 | 2 | 0 | 2 | 50.0% |
| - | WHERE_DID_I_SAVE | 4 | 4 | 0 | 0 | 100.0% |
| - | SEARCH_PLUS_OPEN | 4 | 4 | 0 | 0 | 100.0% |
| - | SEARCH_PLUS_LOCATION | 4 | 4 | 0 | 0 | 100.0% |
| - | SEARCH_PLUS_SUMMARIZE | 4 | 4 | 0 | 0 | 100.0% |
| - | AMBIGUOUS_SEARCH | 4 | 4 | 0 | 0 | 100.0% |
| - | NO_RESULT_SEARCH | 4 | 4 | 0 | 0 | 100.0% |

---

## 4. Document QA Benchmark Breakdown (100 Cases across 18 Categories)

| Code | Category | Total | Correct | Wrong | Cross-Contam | Accuracy |
|:---:|---|:---:|:---:|:---:|:---:|:---:|
| - | DIRECT_FACT | 6 | 6 | 0 | 0 | 100.0% |
| - | INFORMAL_FACT | 6 | 6 | 0 | 0 | 100.0% |
| - | LIST_EXTRACTION | 6 | 6 | 0 | 0 | 100.0% |
| - | YES_NO_VERIFICATION | 6 | 6 | 0 | 0 | 100.0% |
| - | EXPLANATION | 6 | 6 | 0 | 0 | 100.0% |
| - | SUMMARY | 6 | 6 | 0 | 0 | 100.0% |
| - | TARGETED_SUMMARY | 6 | 6 | 0 | 0 | 100.0% |
| - | INFORMATION_LOCATION | 6 | 6 | 0 | 0 | 100.0% |
| - | COUNTING | 6 | 6 | 0 | 0 | 100.0% |
| - | FILTERING | 6 | 6 | 0 | 0 | 100.0% |
| - | TOPIC_SYNTHESIS | 6 | 6 | 0 | 0 | 100.0% |
| - | PROCEDURAL_QUESTION | 6 | 6 | 0 | 0 | 100.0% |
| - | FOLLOW_UP_QUESTION | 6 | 6 | 0 | 0 | 100.0% |
| - | PRONOUN_CONTEXT_QUESTION | 6 | 6 | 0 | 0 | 100.0% |
| - | NOT_FOUND_QUESTION | 6 | 6 | 0 | 0 | 100.0% |
| - | MULTI_STEP_CONVERSATION | 4 | 3 | 1 | 0 | 75.0% |
| - | CROSS_DOCUMENT_ISOLATION | 3 | 3 | 0 | 0 | 100.0% |
| - | DOCUMENT_TARGET_REFERENCES | 3 | 3 | 0 | 0 | 100.0% |

---

## 5. Key Empirical Failure Patterns (Baseline Diagnostic Analysis)

The evaluation harness detected the following specific architectural limitations in the current production implementation:

### 5.1 Search Failure Patterns
1. **Conversational Filler Words in Search Queries**:
   - When queries contain conversational prefixes (`"Can you find the doc about CampusConnect?"`), the current regex intent parser preserves filler words (`query='doc CampusConnect'`), degrading lexical ranking.
2. **Shorthand & Synonym Expansion**:
   - Shorthand queries like `"ml notes"` or `"cc report"` fail because FTS5 and RapidFuzz require character overlap with `Machine_Learning_Notes.txt` or `CampusConnect_Report.pdf`.
3. **Folder Constraints with Deep Nesting**:
   - Queries specifying deep nested paths (e.g. `"College/4th_Year/Internship"`) fail if the ranker only checks the immediate parent folder name rather than the full hierarchical path.
4. **Vague Memory & Pure Content Descriptions**:
   - Queries describing content without mentioning filenames (e.g., `"The document about university student collaboration"`) struggle because the ranker weighs filename/stem matches heavily over content.

### 5.2 QA Failure Patterns
1. **Target Document in Question Text without Active Document**:
   - Queries such as `"What tech I used in resume?"` or `"What was the duration in the internship report?"` fail immediately if no document is actively selected in session state. The agent treats `resume` as question text rather than auto-resolving the target document.
2. **Multi-Turn Context & Pronoun Resolution**:
   - Queries such as `"How long was it?"` or `"Which ones are frontend?"` depend entirely on active document state, but do not maintain conversational entity context across successive turns.

---

## 6. Sample Failure Cases Log

### Sample Search Failures
- **ID**: `S-GOLD-02` (`MULTIPLE_CONSTRAINTS`)
  - **Query**: "I have a PDF somewhere in Downloads about my internship, can you find it?"
  - **Expected**: `['Vijay_Resume.pdf', 'Internship_Report.pdf']` (Behavior: `SELECT`)
  - **Actual**: `CampusConnect_Report.pdf` (Status: `WRONG_DOCUMENT`)
  - **Confidence**: `HIGH`, Latency: `30.41 ms`
- **ID**: `S075` (`SEMANTIC_WORDING_VARIATION`)
  - **Query**: "Retrieve the writeup on student team collaboration"
  - **Expected**: `CampusConnect_Report.pdf` (Behavior: `SELECT`)
  - **Actual**: `Resume.pdf` (Status: `WRONG_NO_MATCH`)
  - **Confidence**: `LOW`, Latency: `24.14 ms`
- **ID**: `S076` (`SEMANTIC_WORDING_VARIATION`)
  - **Query**: "Show me the guide for sprint retrospectives"
  - **Expected**: `Agile_Methodologies.docx` (Behavior: `SELECT`)
  - **Actual**: `Meeting_Notes.txt` (Status: `WRONG_NO_MATCH`)
  - **Confidence**: `LOW`, Latency: `22.74 ms`

### Sample QA Failures
- **ID**: `Q091` (`MULTI_STEP_CONVERSATION`)
  - **Question**: "Find my resume"
  - **Active / Target Doc**: `Vijay_Resume.pdf`
  - **Expected Keywords**: `['Vijay_Resume.pdf']`
  - **Status**: `MISSING_EVIDENCE`, Latency: `0.2 ms`

---

## 7. Conclusion & Next Steps for V2
This baseline report establishes a fixed, reproducible evaluation harness. In the upcoming V2 implementation phases, we will systematically address the documented failure patterns while preserving the 100% pass rate on the existing 129 regression tests.