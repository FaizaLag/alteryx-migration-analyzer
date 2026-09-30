# Answer key

Expert assessment of each test workflow, completed after building them and before the analyzer exists. The analyzer is evaluated against this file in Step 10.

Overall ratings and reasoning come from my build notes. Tool tables drafted with Claude and reviewed by me.

Rule: nothing above "After building" is edited once the analyzer produces output. Changes of view go in that section, dated.

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

**Applies to every workflow:** CSV inputs assume the data is loaded into Redshift tables first (`COPY` from S3, with column types defined explicitly, since CSVs carry no types). CSV outputs become a table (`CREATE TABLE AS`) or an `UNLOAD` to S3.

---

## WF1: Filter active members (simple)

**Inputs:** members.csv · **Tools:** Input → Filter → Select → Output

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) | Table loaded via `COPY` | Low | See loading note above |
| Filter | `WHERE status = 'Active'` | Low | Redshift string comparison is case-sensitive |
| Select | Column list; `plan_type AS plan` | Low | Rename becomes an alias |
| Output (CSV) | `CREATE TABLE AS` or `UNLOAD` | Low | |

**Planted gotchas:** none (clean baseline)
**Overall difficulty:** 2 /10
**Estimated migration effort:** __ hours
**Why:** One simple condition and no conversion.

---

## WF2: Cases per member by program (medium)

**Inputs:** members.csv, cases.csv · **Tools:** 2 Inputs → Join → Formula → Summarize → Output

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) × 2 | Tables loaded via `COPY` | Low | |
| Join | `INNER JOIN ... ON member_id` | Low | Only the J output is used, so unmatched rows drop, same as an inner join |
| Formula: `age_band` | `CASE WHEN ... THEN 'Senior' ELSE 'Adult' END` | Low | Redshift has no `IIF` |
| Formula: `days_open` | `DATEDIFF(day, open_date, COALESCE(close_date, CURRENT_DATE))` | Medium | Argument order differs from `DateTimeDiff`; blank CSV dates must become NULL; `DateTimeToday()` → `CURRENT_DATE` |
| Summarize | `GROUP BY` with `COUNT`, `AVG` | Medium | Redshift `AVG` returns BIGINT for integer input, so averages truncate; cast `days_open` to DECIMAL first |
| Output (CSV) | `CREATE TABLE AS` or `UNLOAD` | Low | |

**Planted gotchas**
- [x] `IIF` logic
- [x] `DateTimeDiff` with a blank `close_date` (open cases)
- [x] Found while reviewing: integer `AVG` truncation in Redshift

**Overall difficulty:** 4 /10
**Estimated migration effort:** __ hours
**Why:** Join, formulas, and Summarize all translate directly (JOIN, new columns in the query, GROUP BY), with a few syntax and type details to get right.

---

## WF3: Monthly case trend (harder)

**Inputs:** cases_2026_07.csv, cases_2026_08.csv, cases_2026_09.csv · **Tools:** 3 Inputs → Select → Union → Formula → Unique → Summarize → Sort → Output

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) × 3 | Tables loaded via `COPY` | Medium | Dates must load as text, since formats differ per file |
| Select (Sep) | `program_name AS program` | Low | Needed before the union, same as in Alteryx |
| Union | `UNION ALL` | Medium | Matches columns by **position**, not name; column order must be aligned by hand |
| Formula: `open_dt` | `CASE` choosing `TO_DATE(open_date, 'MM/DD/YYYY')`, `'DD-Mon-YYYY'` or `'YYYY-MM-DD'` | Medium | Format detection logic must be rewritten per format |
| Formula: `status`, `member_id` | `INITCAP(status)`; `COALESCE(NULLIF(member_id, ''), 'UNKNOWN')` | Low | |
| Unique | `ROW_NUMBER() OVER (PARTITION BY case_id ORDER BY ...) = 1` | Medium | Not plain `DISTINCT`: the duplicate rows differ (Aug "Open" vs. Sep "Closed"), so `DISTINCT` would keep both. Alteryx keeps the first row, which depends on Union input order |
| Summarize | `GROUP BY case_month, program` with `COUNT` | Low | |
| Sort | `ORDER BY` | Low | |
| Output (CSV) | `CREATE TABLE AS` or `UNLOAD` | Low | |

**Planted gotchas**
- [x] Three date formats parsed from text
- [x] Column renamed in September: Union by name vs. position
- [x] Lowercase status values in September
- [x] Two cases duplicated across August and September
- [x] Blank `member_id` in August

**Overall difficulty:** 6 /10
**Estimated migration effort:** __ hours
**Why:** Renaming before the union works in SQL too, but converting text to dates from different formats adds complexity, and deduplication needs care to reproduce Alteryx's keep-first behavior.

---

## WF4: Savings report (messy)

**Inputs:** claims.csv, benchmarks.csv, cases.csv · **Tools:** Formula, RegEx, 2 Joins, Formula, Sort, Multi-Row Formula, Python, Summarize, batch macro, 3 Outputs

| Tool | Redshift equivalent | Difficulty | Notes |
| --- | --- | --- | --- |
| Input (CSV) × 3 | Tables loaded via `COPY` | Medium | `allowed_amount` must load as text because of currency formatting |
| Formula: clean amount | `CAST(REPLACE(REPLACE(allowed_amount, '$', ''), ',', '') AS DECIMAL(12,2))` | Low | |
| RegEx (parse) | `REGEXP_SUBSTR(navigator_note, 'nav-[0-9]{4}-[0-9]+', 1, 1, 'i')` | Medium | Regex dialects differ; case-insensitivity must be set explicitly |
| Join to benchmarks | `LEFT JOIN`; unmatched rows via `WHERE b.proc_code IS NULL` | Medium | Alteryx's separate L output becomes its own query |
| Formula: `savings` | `CASE WHEN steered_flag = 'Y' THEN benchmark_cost - allowed ELSE 0 END` | Low | |
| Join to cases | `INNER JOIN ... ON case_id` | Low | |
| Sort + Multi-Row Formula | `SUM(savings) OVER (PARTITION BY member_id ORDER BY service_date ROWS UNBOUNDED PRECEDING)` | Medium | Redshift requires an explicit frame clause when a window aggregate has `ORDER BY` |
| Python tool | No SQL equivalent | High | Quantile flag could be rewritten with `PERCENTILE_CONT`; Python UDFs are not an option (Redshift ended support after June 30, 2026) |
| Batch macro | `GROUP BY program` | High | Simple logic here, but it lives in a separate `.yxmc` file that must be opened and analyzed on its own |
| Outputs (CSV) × 3 | Three tables or `UNLOAD`s | Medium | One query per output |

**Planted gotchas**
- [x] Currency stored as text
- [x] Inconsistent reference formats in `navigator_note` (RegEx)
- [x] `PROC-111` has no benchmark (unmatched Join records)
- [x] Multi-Row running totals
- [x] Macro: logic lives in a separate file
- [x] Python tool: no SQL equivalent

**Overall difficulty:** 9 /10
**Estimated migration effort:** __ hours
**Why:** RegEx, the macro, and the Python tool add complexity; the macro's logic sits in a separate file and depends on a .yxdb template to keep its metadata.

---

## After building

Anything learned later that changes my view. Dated; the assessments above stay as written.

-