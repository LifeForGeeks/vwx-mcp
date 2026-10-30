# Native modular stage decks

`create_stage_deck_grid` creates up to 25 rectangular **Stage Deck plug-in objects** per call. `get_stage_deck_inspection` reads their dimensions, construction, rail settings, native calculated leg counts, organization and reporting fields.

All input lengths are millimetres, independent of drawing units. `deck_size_mm` is width, depth, overall height. `origin_mm` is the first deck's native insertion point relative to its design layer; it is not a promise that the assembly's lower-left footprint corner is at that point. Columns advance along local +X and rows along local +Y, then the entire layout rotates about the first insertion point. Layer elevation remains separate. Creation restores the previous active layer/class and drawing attributes.

Example: four 4-by-8-foot decks, 2 feet high, with braced legs and three perimeter rail edges:

```json
{
  "expected_document": "C:\\absolute\\QA.vwx",
  "name": "STAGE-A",
  "layer": "Staging",
  "class_name": "Staging-Decks",
  "origin_mm": [0, 0, 0],
  "columns": 2,
  "rows": 2,
  "deck_size_mm": [1219.2, 2438.4, 609.6],
  "structure": "Legs-Braced",
  "rail_edges": ["back", "left", "right"],
  "rail_type": "Straight+Toe",
  "vendor": "Rental company",
  "location": "Main Stage",
  "dry_run": true
}
```

Review the dry-run plan, then use `dry_run: false`. The named layer/class must already exist; `ensure_drawing_structure` handles that separately. Each deck receives a unique `STAGE-A-R01-C01` style object name and native Unit ID. Existing names or Unit IDs block the entire batch. Rail settings are applied only on the selected grid perimeter; interior seams receive `None`. Front/back correspond to the first/last local rows and left/right to the first/last columns.

Top thickness, trim height, leg size/spacing/profile and rail height are explicit configurable inputs. Defaults describe generic geometry, not a manufacturer's approved assembly. The native Stage Deck engine calculates the legs; the tool does not remove shared legs, create connectors between decks, or certify structural capacity. Stairs, ramps, skirts, brand-specific frame geometry and Equipment Summary source assignment remain separate work. Vendor/Brand/Model are native reportable text fields, not native equipment inventory allocations. Component class overrides are disabled for this scope; each deck follows its requested object class.

The current server makes a second native call after creation, checking regeneration, requested field values, dimensions, poses, layer/class and calculated leg count. If it fails, preserve the creation receipt and read the objects; never repeat creation blindly. Generic clients that lack orchestration must call `get_stage_deck_verification` with the returned `created` receipt and `expected_document` in a separate event. Do not use a single-event `vwx_batch` for creation.

Validation: `tests/test_stage_grid.py` checks unit conversion, rotated layout, perimeter edges, invalid inputs, duplicate IDs, dry-run non-mutation and recovery after partial/native verification failures. `tests/live_stage_grid.py` is a one-shot installed QA harness; its original receipt is `evidence/live-qa/stage-grid-installed.json`. That run detected a tuple/list position binding issue; retained decks were corrected in place. `tests/live_stage_grid_finish.py` verified those decks and a fresh rotated assembly after fixing the tuple conversion, with final evidence in `evidence/live-qa/stage-grid-verified.json`. Six decks passed native readback; source objects and active context were preserved. Neither one-shot harness should be rerun. Native data verification does not substitute for a visual drawing review.

Reference: [Vectorworks 2026: Inserting a stage deck](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/EventDesign2/Inserting_a_stage_deck.htm). Parameter choices are checked against the installed plug-in before mutation.
