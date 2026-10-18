# Evaluation

How well does the analyzer match an expert's assessment? This compares the tool's output with my answer key (`tests/answer_key.md`), written before the analyzer produced any output.

## Method

- **Test set:** 4 synthetic Alteryx workflows of increasing complexity, plus the batch macro used by WF4. All data is invented.
- **Answer key:** my difficulty rating (1–10), the risky tools, and 14 planted migration gotchas, committed before the analyzer existed.
- **What was compared:** difficulty score, planted gotchas flagged, extra findings, and the accuracy of the AI explanations.
- **Important caveat:** the scoring rules were calibrated on these same 4 workflows, so matching scores here is expected, not independent proof. See "Not yet tested" below.

## Results

| Workflow | My rating | Tool score | Planted gotchas flagged | Extra findings | AI citation check | AI accuracy | Client-ready? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WF1 Active members | 2 | 2 | none planted | CSV input | Pass | __ | __ |
| WF2 Cases by member | 4 | 4 | 3 of 3 | Hard-coded year (2026) | Pass | __ | __ |
| WF3 Monthly trend | 6 | 6 | 5 of 5 | — | Pass | __ | __ |
| WF4 Savings report | 9 | 9 | 6 of 6 | — | Pass | __ | __ |
| Macro (WF4) | not rated | 1 | none planted | — | Pass | __ | __ |
| **Total** | | **4 of 4 match** | **14 of 14** | | **5 of 5** | | |

*AI accuracy: are all statements supported by the facts? Note anything wrong, vague, or missing.*
*Client-ready: would I send this report to a client as is? If not, the one thing to change.*

## What the tool caught

- **Integer AVG (WF2):** Redshift's AVG on whole numbers returns a whole number, so a literal translation would silently drop decimals.
- **Unique keeps the first row (WF3):** plain `DISTINCT` would keep both duplicate cases because their status differs ("Open" vs. "closed"); the faithful SQL needs `ROW_NUMBER()`.
- **Regex settings (WF4):** three separate Redshift parameters are needed to reproduce the RegEx tool (case-insensitive, capture group, Perl-style pattern).
- **Hard-coded year (WF2):** found while testing the AI output; not planted, but a real risk.
- __ *(anything else you noticed)*

## What it missed, and limits

- **Data-dependent issues aren't detected directly.** WF3 parses one date format with slashes while the data uses dashes; Alteryx tolerated it, but a literal SQL translation may not. The tool flags the formula as a risk to test, but can't see the mismatch without the data.
- **Scores are calibrated on the test set** (see caveat above).
- **Effort and cost aren't estimated.**
- __ *(anything else you noticed)*

## Changes made during testing

| Found | Fixed in | Change |
| --- | --- | --- |
| AI described the Summarize's aggregations without having them in its facts | `src/lineage.py` | Tool details now include aggregations (e.g. "Avg days_open") |
| Hard-coded year not flagged | `rules/formula_gotchas.yaml` | New `hardcoded_year` check |
| Macro interface tools' names reported as comments | `src/parser.py` | Interface tool labels skipped |

Gaps were fixed in the rules and facts, not by loosening the AI prompt, so every AI claim stays traceable to the workflow.

## Not yet tested: fresh workflows

The analyzer has not yet been run on workflows its rules weren't tuned on. Until it is, the scores above show the rules are consistent with my judgment on these 4 workflows, not that they generalize. Planned next test: new workflows using tools outside this test set (e.g. Cross Tab, DateTime), with my rating written before running the tool. Tool types the rules don't know are flagged as "unknown" and scored conservatively, so they're never silently under-scored.

## Conclusion

The analyzer turns an Alteryx workflow into a plain-English summary of its components, rates each part’s migration difficulty and risk, and names the Redshift equivalent. Tested on 4 workflows, it matched my expert ratings and flagged every planted risk. Teams could run it across their workflows to build a scored library that helps management plan a migration.
