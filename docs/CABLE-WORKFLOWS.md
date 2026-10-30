# Native cable routes and inspection

Version0.11.0 adds native section inspection and name/slack/swag edits with a separate verification event. The live single-section QA test rebuilt25ft stock to50ft and restored25ft; saved/reopened section and part state matched. Explicit mm suffixes are mandatory when using native section setters because bare numbers use drawing units although getters return mm. See [Cable sections](CABLE-SECTIONS.md). Seven current scripting functions were absent from the SDK completion stub; the reference index now includes them with official source URLs. Multi-section/break/loom editing, connected source chains and custom-part run consumption remain open.

## Local path readback (0.10.2)

`get_cable_inspection` now accepts `geometry_detail='none'|'summary'|'points'` (default `none`) and `geometry_point_limit=500` (2..2000). Geometry mode accepts at most ten objects. Summary reads bounded NURBS pieces, degrees, control points, weights and knots, returning counts, a SHA-256 snapshot fingerprint, and the object's decomposed parent-space origin/rotation. Points mode also returns the piece data. Over-limit, unsupported or invalid geometry is explicitly unavailable without hiding stored record data. Default inspection adds no NURBS enumeration.

Continuous, clamped degree-one pieces with two controls and positive weights additionally report **path-local** length and endpoints. Higher-degree curves retain their controls/weights/knots, with evaluated endpoints and length left unknown. These are not world coordinates: full affine scale/mirror, parent transforms and layer transforms are outside this scripting reader. The fingerprint covers only observed NURBS data and the decomposed object transform; it is not complete geometry, electrical connectivity or an automatic movement check. Do not compare local length to a scaled instance's drawn length without resolving the full transform.

All **108 offline tests** pass. A fresh installed 279-tool connection passed **seven read-only live calls** against the native 20-foot jumper and both existing 3D QA routes. Local points/weights/knots, origins/angles, independently expected straight lengths, stable repeat fingerprints, limit handling and default behavior were checked. All sampled native fields, paths, object transforms, class/layer assignments, selection and active context were unchanged. Payloads for this three-object scope: default 2,645 bytes, geometry summary 4,847, full points 5,720; these are payload sizes, not measured model tokens. Evidence: `evidence/live-qa/live-cable-geometry.json`, `evidence/cable-geometry-verification.json`. Deployment: `evidence/deployment-20260912-120354/manifest.json`. No native binary change, drawing edit, save or UI interaction was needed for this feature's live checks.

The SDK movement investigation ruled out `AddBeforeMoveObject` / `AddAfterMoveObject`: the SDK documents those as undo primitives for internal drawing-list/layer/order moves, explicitly excluding coordinate dragging. `AddCoordMoveObject3D` is an undo primitive, not documented proof of cable-following notifications. `IObjUpdateSupport` receives native state callbacks; it is not an established way to synthesize them for another plug-in. No unsupported callback or private connector setter was added. Source-to-distributor connection and native movement/path-following remain open.

## Latest native patch result and inspector correction (0.10.1)

The user confirmed the second native command reported **2 successful**. Poll of CID `a1710eccf3eb` returned done. Cable count increased from 2 to 3: one new native CableObject `9c27b811-8318-406c-bc1b-0c3dd22d7b19`, now named `VM-QA-CHAIN-JUMPER`. Its style is `Jumper Edison`, drawn length 240 document inches (20 ft), stocked length 300 inches (25 ft), ordered stock code `E-25ft`. The twofer `d718aced-1403-442a-8cd7-a8bcedcd6ee5` references that cable in OutputUUID1, and the cable's endpoint object UUIDs match that twofer and the selected fixture `8734ee85-3bdf-4541-9858-a4aef0c8fbcd`. The message count is not a count of newly drawn cables. The source/distributor-only zero result does not prove a universal command limitation.

Native creation inherited active class `SHEET-Text`; this QA cable was reassigned to `VM-QA-Electrical-Cables`. Future native patch wrappers must establish and restore the intended layer/class context. No private fields were written.

The cable has separate stored connector references: __StartConnectorUUID is `111eb5fe-2a27-4fb0-9c4e-12d819cdc78a` (matching the library's output component geometry UUID), and __EndConnectorUUID is all zeros, while StartObjectPort and EndObjectPort both remain -1. Version 0.10.1 exposes these optional reference strings as read-only diagnostics and distinguishes unavailable, blank, zero UUID and present-unverified states. It renames `endpoint_port_unassigned` to `endpoint_port_unspecified`; numeric -1 alone is not proof of disconnection. Zero identities are preserved, not repaired or automatically rejected. This is not complete runtime circuit or pin verification.

Movement trials found that HMove used the current view plane, while Move3DObj produced the intended [600,0,0] model position. Neither updated the 240-inch cable path, including a subsequent LDevice_Reset. The fixture was restored exactly to [480,0,0], cable geometry/references/class were checked, and QA was saved. Do not use these low-level moves as a verified connected-equipment movement workflow. The simulated source still has no observed connection; source-to-distributor patching, OIP/schematic comparison, movement/path following, looms, inventory completion and engineering calculations remain unfinished.

All 99 offline tests pass. The installed inspector and final QA readback/save passed live. Seven deployment hashes match `evidence/deployment-20260912-115429/manifest.json`. Evidence: `power-patch-fixture-trial.json`, `power-patch-fixture-after.json`, `cable-movement-trial.json`, `power-patch-final-readback.json` in `evidence/live-qa`; summary `evidence/cable-patch-verification.json`. No command remains pending and no source-show document was edited.

## Earlier release findings

Version 0.7.0 adds `create_cable_paths` and `get_cable_inspection`: 25 entertainment tools, 275 tools in the full server. Tested in Vectorworks 2026 Update 2.1, build 844096, using the separate Toolkit QA document.

## Verified scope

`create_cable_paths(expected_document, items)` creates up to 25 native `CablePathObject` instances. Each item requires `name`, an existing design `layer` and `class`, a unique `route_id`, and 2..200 3D corner `vertices`; `location` is optional. Coordinates are relative to the design layer in document units. Layer elevation remains separate. Unsupported settings, repeated names/route IDs, invalid geometry and wrong documents are rejected. This tool creates route geometry; it does not establish network joins, equipment connections or cable following.

The implementation converts an open 3D polygon to NURBS before creating the native path. After Vectorworks completes its regeneration event, an internal read-only `get_cable_path_verification` checks every segment/control point, degree, transform, class, ID, location and native length against the creation receipt. Existing class attributes are inherited; the tool does not impose a drawing standard's line weight or scale. No generic polygon is accepted as a successful native route.

Call creation directly; its `items` list batches compatible paths. `vwx_batch` rejects this operation because native regeneration must finish before verification. An older MCP connection returns `requires_verification=true`: call `vwx('get_cable_path_verification', {expected_document, created})` in a separate call using the exact receipt. Verification failure retains the UUIDs and recovery parameters; do not repeat creation. Native failures may leave a partial path, which is reported rather than automatically deleted. Verification is read-only and can be repeated after inspection.

`get_cable_inspection(object_ids, include_fields=false, issue_limit=50)` reads up to 50 explicit modern cable/path UUIDs. It reports path/run IDs, run-level loom groups, parsed native lengths, path type, style name, stored endpoint object UUIDs/ports and presence of reported parts. Optional native field details are bounded to 512 characters per field; missing and truncated fields are explicit. Review counts cover the full selected scope even when issue rows are capped. Blank values remain blank; unavailable fields remain unknown. No object is reset or edited.

An endpoint UUID that resolves is only a valid object reference. It does not prove the intended device component, port, pin, electrical link, load attachment or path-following relationship. `native_connections_verified` and `sections_and_breaks_verified` remain false. The inspector is not an electrical calculator or a complete inventory validator.

## Native findings that prevent false success

- The modern run universal name is `CableObject`. The current route is `CablePathObject`, which contains both circuit and Spotlight cable counts. `CablePathObject2` is also registered, with a different five-field schema; it is not supported by these tools.
- `CreateCustomObjectPath('CablePathObject', polygon3D, None)` produced geometry but a zero Length field even after reset. The NURBS version of the identical route reported 480 document inches / 40 feet. Creating a PIO handle alone is insufficient.
- NURBS conversion of a corner polyline produces degree-one pieces with two control points each. Live reads use `NurbsGetPt3D(curve, segment, point)`. `GetPolyPt3D` uses zero-based vertex indices; using the final one-based index returned an invalid sentinel coordinate in the probe. Consult the SDK's parameter comments when the compact index omits them.
- `CC_RouteFromShape` returned no handle and left the QA source polygon unchanged in this application session. This is not evidence that licensing is the cause, or that the function works interchangeably with the route tool.
- A native `CableObject` probe associated successfully with the official `Data XLR5-XLR5` style, yet connector/type/length/parts fields remained empty or zero. Supplying NURBS alone did not fix run initialization. Cable-run creation is therefore not exposed as a finished workflow.
- Exact fields include the native spelling `StartConector`, `CableRun_ID`, `Loom_ID`, `Part_ID`, `LengthPartsTotal` and `UsedPartsOrdered`. Do not substitute display captions as universal field names.
- Default Volt/Ampere values are not verified device ratings. No power design is inferred from them.

The native [cable editing workflow](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Cables/Editing_cables.htm) distinguishes drawn length from needed and stocked cable, and includes section breaks, slack/swag and incoming/outgoing looms. Those section relationships need their own verified control route; one run's `Loom_ID` does not capture them. [Cable paths](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Cables/Drawing_cable_paths.htm) can drive subsequent cable routing and updates. This release has not yet verified those associations or their edit propagation.

The SDK `ICableConnectionsProvider` supplies component data and internal pin links through an object event sink. Component identity uses the device UUID together with component UUID. Connector universal names come from `CableConnectors.xml`. This remains a candidate native inspection route, not a tested network editing API.

## Evidence

- `tests/test_cables.py`: nine focused checks; 62 total toolkit checks pass. Covers incomplete/stale references, unknown fields, truncation, invalid batches, changed route shape and post-creation recovery.
- `tests/live_cables.py` / `evidence/live-qa/live-cables.json`: fresh installed server, 275 tools, 11 calls. Two routes were created in one call, including an irregular 3D diagonal; all native vertices and lengths matched. Wrong-document, degenerate and duplicate attempts left paths unchanged. Active layer/class and a control cable's reset counter were preserved. QA saved successfully.
- Final deployment `evidence/deployment-20260912-100357/manifest.json`: all seven installed hashes matched. `evidence/live-qa/cable-final-installed-check.json` records four additional calls after the last code changes and visual refinement: clean inspection, repeated full geometry verification, unsupported-setting rejection and batch-boundary rejection. No routes were recreated.
- `evidence/live-qa/cable-default-schemas.json`: installed parameter definitions, captured with `DefineCustomObj(name,0)` in QA. Definitions are not proof of instance behavior.
- `tests/live_cable_documentation.py`, `live-cable-documentation.json` and `cable-documentation-refinement.json`: native sheet, plan/elevation, annotation and export evidence. Refinement increased the QA path class to 10 mil and added A/B labels. This is a QA page, not a completed show or cable schedule.
- `evidence/live-qa/cable-pdf-verification.json`: one 24 x 18 inch PDF page, scale 1:48. The 30-foot dimension is 540 PDF points (7.5 inches); the 10-foot rise is 180 points (2.5 inches). The final Poppler render was visually reviewed for visible routes, readable labels and clipping.

The native C++ viewport extension remains staged and uninstalled. This release uses the existing bridge with updated Python commands/server files.

## Next native workflow gates

1. Reproduce cable-run insertion through the native Cable tool, then compare style initialization and internal section/part data with the failed script probes.
2. Inspect actual source, distributor and consumer components and their paired UUID/pin identities; verify native power schematic readback.
3. Establish and edit a cable following a route/truss, including entry/exit, endpoint reassignment, breaks and incoming/outgoing looms. Confirm persistence after movement, reshape and save/reopen.
4. Reconcile ordered stock parts, slack/swag, adapters, suppliers, visible geometry and worksheet output. Confirm all numerical units and actual equipment data before implementing electrical calculations.
5. Extend complete rigging relationships and visible hardware in parallel with the broader Spotlight coverage inventory. A route crossing or touching truss is not an attachment.
