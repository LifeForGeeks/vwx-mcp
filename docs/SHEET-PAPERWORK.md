# Sheet paperwork inspection

Version 0.15.1 adds `get_sheet_paperwork_audit`. It accepts 1–10 unique sheet-layer names and a detail limit of 1–100 (default 25). It reads selected sheets and nested ordinary groups without activation, regeneration or worksheet recalculation.

The audit reports viewport titles, drawing numbers, scales, view/projection codes, crop presence and update status; worksheet image/resource UUIDs, image scales and resource dimensions; and native Title Block Border counts. It detects duplicate drawing numbers within each sheet, missing titles/numbers, invalid scales and broken worksheet references. Zero/multiple title blocks are review findings.

Worksheet images are grouped by resource UUID across the selected sheets. This proves shared resource identity, not accurate inventory formulas, current calculations, correct supplier grouping or matching Data Visualization colors.

Counts cover the complete inspected scope; detail is bounded. Traversal has a 10,000-node limit and cycle protection. It does not enter symbol or plug-in internals or viewport annotations. It does not certify page fit, label readability, title-block field contents, object visibility or exported PDF scale.

Seven offline tests were added; the full recorded suite passed 196 tests. Deployment: `evidence/deployment-20260913-202941/manifest.json`. Native runtime validation is pending; this is not a verified issued-sheet checker yet.

The related [Data Visualization workflow plan](../../vectorworks-research/data-visualization-workflows.md) adds the next requirements for matching viewport appearance, legends and worksheet images.
