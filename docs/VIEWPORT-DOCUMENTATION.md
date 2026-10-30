# Native viewport and drawing-label inspection

Version 0.6.0 adds `get_viewport_documentation`, bringing the entertainment surface to 23 tools and the full server to 273. This read-only operation inspects up to ten explicit viewport UUIDs in one call, replacing repeated viewport and label Object Info reads.

```json
{"viewport_ids":["actual-viewport-uuid"],"include_labels":true,"limit":50}
```

The result includes viewport drawing title/number, sheet layer name, native view type, section flag, actual viewport scale, and annotation-label count. It distinguishes the legacy `Drawing Label` record from modern `Drawing Label2`. Modern labels use `ScaleDisplay`; legacy labels use `fScale Config`. There is no ordinary modern `Scale` record field in the observed schema: custom scale text and native viewport scale must remain separate.

Review cases include label title/number/sheet disagreement, exact conventional titles inconsistent with a standard view axis, missing schema fields and modern custom scale display. Arbitrary titles are not interpreted. Section and custom views are excluded from the title/view heuristic. Top-view axis matching does not certify Top/Plan projection behavior. A missing native label is reported as a zero count, not an error: a drawing may intentionally use other annotations.

`limit` bounds issues and optional label details to 1–100 entries (default 50); complete issue/label counts and truncation flags are retained. There is currently no pagination beyond that detail bound. Narrow the viewport scope for issues; a viewport with more than 100 labels requires a future paging extension for complete label detail. Values are capped at 512 characters with explicit truncation flags. Missing fields remain null; failed native reads return an error rather than a clean audit.

Traversal enters the viewport annotation group and ordinary nested groups, with a 10,000-object guard across the call. It does not enter symbol definitions or generated PIO geometry, and does not inspect standalone sheet labels. Styles are reported by name, but style ownership, dynamic text layout, rendered text, collisions, visibility, duplicate drawing numbers across a whole sheet, and physical PDF scale are not verified. Neither the inspector nor its heuristics edits or resets anything.

## Verified native behavior

On Vectorworks 2026 Update 2.1, two named labels were created only in `Velvet-Mirror-Toolkit-QA.vwx`: `VM-QA-DrawingLabel-Probe` and `VM-QA-DrawingLabel2-Probe`. Both are annotations of `TK-Viewport-1`. The modern label deliberately uses custom text `NOT TO SCALE` to test that review case.

Eight calls through a fresh installed-server connection verified both label generations, custom-scale reporting, and a deliberate title/view disagreement. Changing the modern label title to `Front Elevation` and resetting it updated the viewport and the other label after the native event ended. The viewport still had a top view, so the inspector flagged the disagreement. The test restored the original `Top Plan` title and verified that a second viewport and coordination preference were unchanged. Read-only calls were checked against before/after state. No source Armory file was edited.

Evidence: `evidence/live-qa/live-viewport-documentation.json` and `tests/live_viewport_documentation.py`. The complete offline toolkit suite passes 53 tests, including seven new documentation-inspection checks. Unit tests cover nested ordinary groups, schema gaps, bounds, custom/section views and failed native reads; styled labels and all layout variants still need live coverage.

## Sources and implementation route

- [Vectorworks Drawing Label documentation](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Annotation2/Creating_drawing_labels.htm): automatic drawing coordination and custom scale display.
- [Marker and drawing-label styles](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Annotation2/Creating_styles_for_markers_and_drawing_labels.htm): modern dynamic text syntax and style/layout behavior.
- Installed SDK `ObjectVariables.h`: 1032 drawing title, 1033 drawing number/locator, 1003 viewport scale, 1007 view type, 1054 section flag.
- Installed SDK `ProgramVariables.h`: 544 automatic drawing coordination. `MiniCadCallBacks.h`: annotation group 2 and standard-view constants.

This scripting operation does not depend on the separately staged C++ viewport-style/data-visualization extension. That extension still needs a normal restart and runtime validation.
