# wf4_program_summary.yxmc

**Redshift migration difficulty: 1/10**, direct translation. 2 tools, 0 migration gotchas.

## In short

This workflow filters records to a single program (Care Navigation) and then summarizes the result by summing savings and counting claims. It scores 1 out of 10, meaning it is a direct translation to SQL. Both tools used have simple, well-known SQL equivalents, so there are no design decisions or rework needed.

*Written by AI (claude-sonnet-5) from facts extracted by code; every cited tool was checked.*

## How data flows

```mermaid
flowchart LR
    t3["Filter<br/>program = Care Navigation"]
    t6["Summarize<br/>by program; Sum savings; Count claim_id"]
    t2["Macro Input"]
    t4["Control Parameter"]
    t5["Action"]
    t7["Macro Output"]
    t3 -->|true| t6
    t6 --> t7
    t2 --> t3
    t5 -.->|sets value| t3
    t4 -.-> t5
    classDef high fill:#f8d7da,stroke:#b02a37,color:#3d0a10
    classDef medium fill:#fff3cd,stroke:#b8860b,color:#3d2e00
    classDef low fill:#d1e7dd,stroke:#2e7d4f,color:#0b2e1c
    class t3,t6 low
    classDef none fill:#e9ecef,stroke:#6c757d,color:#212529
    class t2,t4,t5,t7 none
```

## Main risks

## Next steps

1. Translate the Filter [3] into a WHERE clause for program = 'Care Navigation'.
2. Translate the Summarize [6] into a GROUP BY query with SUM(savings) and COUNT(claim_id).
3. Confirm the exact field names and data types for program, savings, and claim_id before writing the SQL.
4. Validate the Redshift output against the original workflow output for the Care Navigation program to confirm matching totals.

## Every gotcha found

| Severity | Issue | Tools | What to do in Redshift |
|---|---|---|---|
