# Velvet Mirror MCP 0.1.0 — validation

Tested 12 September 2026 on the installed Windows Vectorworks 2026 Update 2.1 and its existing native bridge. This is an entertainment workflow extension of the local upstream fork, retaining its MIT license. The native C++ bridge was not replaced.

## Verified in the live application

The updated installed server registered **269 MCP tools: 250 existing and 19 new**. A real FastMCP client connected to that installed server and executed the workflows against `evidence/live-qa/Velvet-Mirror-Toolkit-QA.vwx`, a separate test copy. No delivery model was used as a test canvas.

| Workflow | Evidence |
| --- | --- |
| Inspection and organization | Actual document path, units, layers/classes, installed native parameter schemas; repeated layer/class setup; wrong-document rejection |
| Library resources | Listed an installed ROE library, imported an exact previously absent resource, rejected a name collision |
| Native equipment | Created two native Lighting Devices, a Stage Deck and an LEDWall with supplied parameters and verified transforms |
| Rigging | Created a library-backed TrussItem inside a native Hanging Position; native auto-attachment linked both expected fixtures without moving them |
| Accessories and inventory | One native clamp assembly per fixture; repeated placement reused it; 85 mm accessory offset round-tripped correctly; distinct owned/rental body-source strings persisted |
| Labels and title blocks | Changed a configured label-handle offset without moving its fixture; shared native project data and selected sheet data persisted |
| Worksheets | One live database worksheet with two fixture rows; two sheet images referenced the same worksheet resource; repeat placement reused its image |
| Views and dimensions | Native plan viewports at 1:48, explicit layer/class visibility, crop placement and class override readback; a native 8-foot dimension |
| Recovery | Retrieved the same retained native job result twice through the new MCP status tool |
| Save/export | Saved the QA VWX; exported two sheets through the native PDF exporter and verified the actual output path |

## Visual and physical-scale checks

Both PDF pages are **36 × 24 inches**. The freshly created 8 × 4 ft deck has an actual PDF outline of **144 × 72 points (2 × 1 inches)**, matching 1:48. The dimension reads **8′-0″** and its glyph height matches 10-point paper text. Both pages contain the two fixture/source rows from the shared worksheet. Rendered pages and an enlarged detail were visually inspected; the deck, fixtures, truss and native dimension are present.

This check caught defects that API success alone missed:

- The first PIO graphics generation could contain an invisible line style even though the parent had correct class attributes. Creation now yields to Vectorworks, then the MCP performs a second guarded regeneration event. A newly created test deck passed without a manual repair.
- Viewport adoption could shrink dimension text. Font sizing now occurs after adoption and is checked in the PDF.
- Viewport bounds needed explicit cache resets before/after movement; the final crop is correctly positioned on the sheet.

The before/after SHA-256 hashes of the original Armory VWX and delivered coordination PDF match. The prior cached export proof was backed up and restored after successful QA export.

## Regression coverage

The offline suite covers wrong-document rejection, invalid/nonfinite coordinates, rotation basis math, accessory reuse and unit conversion, shared worksheet identity, dimension enum/offset signatures, annotation adoption ordering, viewport settings, correct class-override API arguments, typed payload serialization, retained result polling, CID validation, stale-heartbeat handling, claimed/unclaimed timeout races, two-event creation/failure recovery, the pump event boundary, and rejection of incompatible single-event batching before edits.

Machine-readable evidence is local and excluded from Git:

- `evidence/live-qa/live-objects.json`, `live-sheets.json`, `live-finish.json`
- `evidence/live-qa/final-installed-check.json`
- `evidence/live-qa/pdf-and-originals-validation.json`
- `evidence/deployment-*/manifest.json` and backed-up deployed files

## Scope of these results

The live checks used an inch-based drawing with existing installed library resources and linked documentation resources. This release does not claim equivalent live coverage for metric documents, every manufacturer symbol, multi-cell devices, multiple identical independent accessories, newly authored title-block/legend layouts, every 3D viewport projection, or Stage Steps/Side Arm creation through the new generic creator. Inter-member truss snap connections are not synthesized. Electrical/cable-network authoring, MVR/GDTF validation and additional SDK interfaces remain future work. Existing upstream tools outside the named fixes were not comprehensively retested.

The PDF is a functional test sheet, not a finished show drawing or a mounting/structural approval.
