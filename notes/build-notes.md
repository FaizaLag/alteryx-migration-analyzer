# Alteryx Analyzer Tool: Build notes

Notes from building the four test workflows (Step 3).

## WF1: Active members

- Simple: one simple condition and no conversion.

**Rating:** 2

## WF2: Cases per member by program

- Join: to be translated to a table join.
- Formulas: new variables created in the query, with the right translation to Redshift.
- Summarize: translated to a GROUP BY.

**Rating:** 4

## WF3: Monthly case trend

- Renaming the variable before the Union works. The same is needed in SQL.
- Formulas converting text to dates from different formats can add complexity. Use CASE in SQL?
- Unique: Need logic to keep the first row for each case_id
- Uses GROUP BY and ORDER BY.

**Rating:** 6

## WF4: Savings report

- RegEx, macro, and Python tools add complexity.
- The macro takes an Alteryx database file (.yxdb) as its input template, so the metadata is maintained.

**Rating:** 9

## Lessons learned while building

- **CSV files lose data types.** Every CSV field comes in as text (V_String). The macro's CSV template turned `savings` into text until I switched to a `.yxdb` template, which keeps types. Same in Redshift: loading a CSV with `COPY` needs the table's column types defined explicitly.
- **Macros travel with their workflow.** WF4 stores the macro's file path, so the `.yxmc` must always move with it. A migration has to account for logic that lives in a separate file.
- **Workflows store full file paths.** Every Input, Output, and Macro Input saves its full path, including usernames and folder names. Files need checking before sharing.
- **Row order isn't guaranteed.** The batch macro returned programs in a different order than expected. In Redshift, rows have no order without `ORDER BY`, so outputs whose order matters need an explicit sort.
- **Running totals depend on grouping and sorting.** The Multi-Row Formula resets per member and relies on the Sort before it. In SQL this becomes a window function: `SUM(savings) OVER (PARTITION BY member_id ORDER BY service_date)`.
- **Negative savings exist.** 14 steered claims had an allowed amount above the benchmark. The workflow keeps them as negative values; how to treat them is a methodology decision, not a technical one.
- **Mismatched column names break a Union.** September's `program_name` needed a rename first; otherwise the Union creates two separate columns.