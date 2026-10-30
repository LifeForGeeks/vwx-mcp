# Inspection efficiency — 0.2.0

12 September 2026. The previous full-state response returned every layer/class and fixture matrix/accessory pose for routine checks. A captured live response for 212 fixtures was 165,088 UTF-8 bytes.

The existing MCP tool now supports summary, compact device pages, and explicit full detail. It queries actual native HP links rather than trusting Position text. Inventory groups combine symbol with all three supplier fields, allowing one equipment symbol to represent different body/lens/accessory sources. Summary inspection avoids fetching device matrices and individual accessory poses. No UI interaction or document mutation was needed to learn or validate this change.

| Live query | Response bytes | Observed seconds |
| --- | ---: | ---: |
| Previous full response | 165,088 | Not measured |
| New default summary | 2,390 | 0.549 |
| New explicit full response | 166,960 | 0.982 |
| Scoped first compact device page | 1,762 | 0.916 |
| Scoped second compact device page | 1,759 | 0.540 |

The default response is 98.55% smaller. This compares different levels of requested detail; it is not compression of equivalent full information. Full device records and structure remain available and matched the captured baseline exactly. The small full-response increase includes scoped counts, inventory grouping and pagination metadata.

Actual attachment/accessory counts and all inventory groups matched the baseline. Two compact pages covered the two QA fixtures without duplicates or omissions. The updated installed server advertised the summary default in its real MCP input schema. All 21 offline regression tests passed, including tests that summary counts cover every match independently of page size, different lens suppliers stay distinct, Position text does not establish attachment, and only the requested full page fetches expensive details.

These are UTF-8 byte measurements and single live timing observations. Model-token savings and controlled performance gains were not measured. Group output is capped at 50 with explicit truncation; pages read live state and can change after edits. Global native counts are distinguished from the criteria-scoped Lighting Device summary.

Reproduce with the installed server Python by running `tests/benchmark_inspection.py` after capturing a complete matching baseline in `evidence/live-qa/inspection-before-0.2.json`. The script performs read-only calls and refuses a different active document. Full responses and measurements stay in local ignored evidence files. No show model or delivered PDF was modified.
