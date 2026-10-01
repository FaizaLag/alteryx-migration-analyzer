# wf4_program_summary.yxmc

**Redshift migration difficulty: 1/10**, direct translation. 2 tools, 0 migration gotchas.

## In short

This macro filters claims data to the 'Care Navigation' program and then summarizes savings and claim counts by program. It scores 1 out of 10, the lowest difficulty band, because both tools used are simple, direct-translation operations. There are no gotchas or structural complications noted in the facts.

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

**Unlabeled upstream/downstream tools** (low)  
The data flow shows tools 2, 4, 5, and 7 feeding into or out of the filter and summarize steps, but the facts don't describe what these tools do. This can't be assessed from the workflow file as given.

## Next steps

1. Confirm what tools 2, 4, 5, and 7 do, since they are not detailed in the extracted facts but are part of the data flow.
2. Translate Filter [3] into a WHERE clause for program = 'Care Navigation'.
3. Translate Summarize [6] into a GROUP BY program with SUM(savings) and COUNT(claim_id).
4. Validate the Redshift output against the original macro's output for a sample of records.

## Every gotcha found

| Severity | Issue | Tools | What to do in Redshift |
|---|---|---|---|
