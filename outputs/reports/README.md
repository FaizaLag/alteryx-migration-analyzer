# Alteryx to Redshift: migration assessments

| Workflow | Score | Tools | Gotchas | Main risk |
|---|---|---|---|---|
| [wf4_savings_report.yxmd](wf4_savings_report.md) | 9/10 | 17 | 16 | Python logic has no SQL equivalent |
| [wf3_monthly_trend.yxmd](wf3_monthly_trend.md) | 6/10 | 10 | 15 | Date parsing logic depends on mixed formats in source data |
| [wf2_cases_by_member.yxmd](wf2_cases_by_member.md) | 4/10 | 6 | 10 | Average on whole-number field loses decimals |
| [wf1_active_members.yxmd](wf1_active_members.md) | 2/10 | 4 | 1 | CSV source has no defined data types |
| [wf4_program_summary.yxmc](wf4_program_summary.md) | 1/10 | 2 | 0 | (no AI summary yet) |
