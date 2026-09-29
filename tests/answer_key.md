# Answer key

My expert predictions for each test workflow, written **before** building them and before the tool exists. The tool is evaluated against this file in Step 10.

Rule: predictions are never edited after the fact. If building a workflow changes my view, I add it under "After building" and keep the original.

## Scoring scale

**Overall difficulty (1–10)**

| Score | Meaning |
| --- | --- |
| 1–2 | Direct SQL translation; a junior analyst could do it in an hour |
| 3–4 | Mostly direct; a few syntax rewrites |
| 5–6 | Needs design decisions (loading data, date handling, nulls) |
| 7–8 | Some logic has no SQL equivalent; needs redesign or another tool |
| 9–10 | Major rework; hidden logic, scripts, or behavior hard to reproduce |

**Per-tool difficulty:** Low = syntax swap · Medium = behavior or type differences to handle · High = no direct equivalent

---

## WF1: Filter active members (simple)

**Purpose:** Keep active members and the columns needed downstream.
**Inputs:** members.csv
**Tools:** Input → Filter → Select → Output

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) | | | |
| Filter | | | |
| Select | | | |
| Output (CSV) | | | |

**Planted gotchas:** none (clean baseline)
**Overall difficulty:** __ /10
**Estimated migration effort:** __ hours
**Why:**

---

## WF2: Cases per member by program (medium)

**Purpose:** Count cases and average days open per member and program.
**Inputs:** members.csv, cases.csv
**Tools:** 2 Inputs → Join → Formula → Summarize → Output

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) × 2 | | | |
| Join | | | |
| Formula | | | |
| Summarize | | | |
| Output (CSV) | | | |

**Planted gotchas**
- [ ] `IIF` logic
- [ ] `DateTimeDiff` with a blank `close_date` (open cases)

**Overall difficulty:** __ /10
**Estimated migration effort:** __ hours
**Why:**

---

## WF3: Monthly case trend (harder)

**Purpose:** Combine three monthly extracts and count cases by month and program.
**Inputs:** cases_2026_07.csv, cases_2026_08.csv, cases_2026_09.csv
**Tools:** 3 Inputs → Union → Formula (date logic) → Summarize → Sort → Output

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) × 3 | | | |
| Union | | | |
| Formula | | | |
| Summarize | | | |
| Sort | | | |
| Output (CSV) | | | |

**Planted gotchas**
- [ ] Three date formats parsed from text (`DateTimeParse` / `DateTimeFormat`)
- [ ] Column renamed in September (`program_name`): Union by name vs. position
- [ ] Lowercase status values in September
- [ ] Two cases duplicated across August and September
- [ ] Blank `member_id` in August (`IsNull` handling)

**Overall difficulty:** __ /10
**Estimated migration effort:** __ hours
**Why:**

---

## WF4: Savings report (messy)

**Purpose:** Calculate steerage savings per case against benchmark costs.
**Inputs:** members.csv, cases.csv, claims.csv, benchmarks.csv
**Tools:** Join, Multi-Row Formula, RegEx, batch macro, Python tool, multiple outputs

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) × 4 | | | |
| Join (claims to benchmarks) | | | |
| Multi-Row Formula | | | |
| RegEx | | | |
| Batch macro | | | |
| Python tool | | | |
| Outputs (multiple) | | | |

**Planted gotchas**
- [ ] Currency stored as text (`"$11,012.14"`)
- [ ] Inconsistent reference formats in `navigator_note` (RegEx)
- [ ] `PROC-111` has no benchmark (unmatched Join records)
- [ ] Multi-Row running totals
- [ ] Macro: logic lives in a separate file
- [ ] Python tool: no SQL equivalent

**Overall difficulty:** __ /10
**Estimated migration effort:** __ hours
**Why:**

---

## After building

Anything I learned while building that changes my view. Dated, and added below; the predictions above stay as written.

- 
