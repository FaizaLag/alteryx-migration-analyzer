# wf4_program_summary.yxmc

**Redshift migration difficulty: 1/10**, direct translation. 2 tools, 0 migration gotchas.

## In short

This macro filters claims data to the 'Care Navigation' program and then summarizes the results by program, summing savings and counting claim IDs. It scored 1 out of 10, meaning it translates to Redshift SQL almost directly with no significant rework needed. The only two scored tools, Filter [3] and Summarize [6], both map cleanly to standard SQL (WHERE clause and GROUP BY with aggregates).

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

**No significant risks identified** (low)  
The facts show no gotchas and only low-difficulty tools, so there is nothing flagged that would complicate migration.

## Next steps

1. Translate the Filter [3] condition into a SQL WHERE clause.
2. Translate the Summarize [6] step into a GROUP BY query with SUM(savings) and COUNT(claim_id).
3. Confirm what tools 2, 4, 5, and 7 do, since the facts only describe their position in the data flow, not their function.
4. Validate the Redshift query output against the original macro's results using a sample dataset.

## Every gotcha found

| Severity | Issue | Tools | What to do in Redshift |
|---|---|---|---|
