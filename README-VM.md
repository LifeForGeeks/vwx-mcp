# Velvet Mirror Vectorworks MCP

Version 0.15.1 adds [sheet paperwork inspection](docs/SHEET-PAPERWORK.md) with shared worksheet resource checks. The recorded offline suite passes 196 tests; this new audit still needs runtime validation. The native GDTF extension is installed, with live checks pending because the bridge palette was not running after launch. Deployment: `evidence/deployment-20260913-202941/manifest.json`.

Version 0.15.0 added verified [lighting documentation and numbering](docs/LIGHTING-DOCUMENTATION.md), plus [GDTF/MVR readers and native GDTF import/export wrappers](docs/GDTF-MVR-CONTROL.md). Live lighting changes were restored, and 98 source MVR fixtures passed embedded-file/mode checks. Native import/export is not yet runtime verified.

Data Visualization is now a core development requirement: [workflow research and native API map](../vectorworks-research/data-visualization-workflows.md). Supplier colors, labels, legends and shared worksheet inventories must agree. Full scheme editing and per-object effective display inspection are not implemented yet. Mounting realism, brackets/clamps, pan/tilt, tower contact and visible straps remain active priorities; the floating-laser cause has not been verified.

Version 0.14.0 adds [native modular stage deck creation and inspection](docs/STAGE-DECK-GRIDS.md): millimetre inputs, rotated grids, explicit construction, perimeter rails, unique IDs and reportable supplier fields. 171 offline tests pass. Live evidence is in `evidence/live-qa/stage-grid-verified.json`; visual and manufacturer-specific geometry review remain separate. Current priority is lighting, rigging and staging.

Local entertainment-drafting fork of [vicquick/vwx-mcp](https://github.com/vicquick/vwx-mcp), built from the Armory recreation lessons. Version **0.15.1** includes 48 entertainment tools alongside the existing 250-tool server, including connector/style configuration inspection, section loom/box/tape edits, cable length audits, native cable-section edits, part Use flags, custom cable-part authoring/export, electrical-component inspection, cable-path creation and documentation checks. The upstream MIT license and attribution remain in `LICENSE`. No upstream repository or remote service has been modified.

Version0.13.1 verifies both endpoint families against their style and keeps adapters and physical connector metadata separate.163offline tests and5fresh installed calls pass. The native engine now selects the custom Edison-to-TRUE1 part for an asymmetric test cable. Complete insertion still fails the stored-Length check; native device connections and pins remain unverified. See [connector configuration](docs/CABLE-CONNECTOR-CONFIGURATION.md). An experimental [native lifecycle extension](docs/CABLE-LIFECYCLE-PROBE.md) was installed and tested; stored Length still failed. Cable initialization is now parked by user request.

The native bridge is retained. The new code is in `vwx-plugin/entertainment.py`, with typed MCP schemas in `mcp-server/entertainment_tools.py`. A new MCP connection loads the additional named tools and server orchestration. The configured connector ID remains `vwx-mcp` for compatibility; its server identity is **Velvet Mirror Vectorworks**. The updated server also supports the same workflows through `vwx(command, params)`.

## What it replaces

| Repeated manual work | Tools |
| --- | --- |
| Detecting disagreement between Object Info length, native sections and linear path geometry | `get_cable_length_audit` |
| Changing current-document cable-part Use flags with stale-data protection | `set_cable_part_availability` |
| Reading native sections/ordered stock and editing names, slack, swag and single-section loom/box/tape | `get_cable_sections`, `set_cable_sections` |
| Creating custom native cable parts with updated labels and physical connector metadata | `create_cable_part_symbols`, `get_cable_part_symbols` |
| Exporting parts into a backed-up empty native user library | `export_cable_part_library` |
| Inserting native library distributors and inspecting electrical definitions | `create_distributors`, `get_distributor_inspection` |
| Reading native electrical components and internal links | `get_electrical_components` |
| Looking up exact installed connector identities, ordered sockets and directional declarations | `get_cable_connector_catalog` |
| Creating 3D cable routes and checking native geometry/length after regeneration | `create_cable_paths` |
| Reading cable/run looms, endpoint references, parts presence and incomplete configuration | `get_cable_inspection` |
| Reading Object Info, checking layers/classes and counting native objects | `get_entertainment_state`, `get_native_schema` |
| Reading data-sheet definitions, visibility and selected object values | `get_data_sheet_inspection` |
| Reading drawing-label fields, title coordination and view/scale review cases | `get_viewport_documentation` |
| Comparing viewport layer/class visibility, scale and override counts | `get_viewport_display` |
| Checking recorded DMX patch across cells and accessories | `get_lighting_patch_audit` |
| Browsing a downloaded library and importing exact resources | `list_native_library_resources`, `import_native_resources` |
| Building drawing organization | `ensure_drawing_structure` |
| Inserting native equipment with explicit parameters | `create_native_objects` |
| Creating truss and a native hanging position | `create_truss_position` |
| Attaching loads and checking real native links | `attach_loads_to_position` |
| Repeated accessory placement and source assignment | `set_lighting_accessories`, `set_lighting_sources` |
| Moving fixture labels | `set_fixture_label_layout` |
| Building/recalculating inventories and repeating their images across sheets | `upsert_database_worksheet`, `place_shared_worksheet` |
| Editing project/sheet fields across linked title blocks | `update_title_block_data` |
| Configuring scaled/cropped views and adding readable dimensions/text | `create_sheet_viewport`, `annotate_viewport` |
| Repeated save/export and recovering uncertain long calls | `save_document_checked`, `export_sheet_set_checked`, `get_bridge_job_status` |

See the [full Spotlight coverage roadmap](../vectorworks-research/spotlight-coverage-roadmap.md) for the expanded objective and installed-help inventory.

## Operating contract

Version0.13.0 adds single-section loom, box and tape metadata to the existing section tool, with native run synchronization and live worksheet verification.156offline tests pass. Both QA cables were restored after installed-tool tests. See [section metadata](docs/CABLE-SECTIONS.md). Native-drawn reference length is correct, but its stored UsedParts disagrees with the native ordered-parts function; the QA comparison worksheet preserves this reporting regression. Do not use UsedParts alone as an inventory authority. Complete API insertion and multi-section synchronization remain unfinished.

Version 0.12.0 adds a live-verified [cable length audit](docs/CABLE-LENGTH-AUDIT.md), with 151 offline tests passing. Native stock selection of the custom TRUE1 30ft part is now verified in a separate unconnected QA section. Its API-created CableObject still reports zero Object Info length despite a correct section/path length; the audit catches this mismatch. Complete cable creation is not advertised. External-library discovery, adapter consumption and complete connections/route following remain open. Earlier pending-dialog and custom-consumption notes below are historical.

Version0.11.1 supports flat polyline cable-part graphics and passes145offline tests. Native stock tests exposed a critical limit: changing CablePart.Use directly did not exclude that part from native selection, even after forcing a50ft rebuild and shrinking the run. Both the flag and original cable were restored. Treat set_cable_part_availability as a resource-flag setter; refreshing/applying active inventory remains unresolved. Evidence: `evidence/live-qa/cable-availability-forced-rebuild.json`. Native section editing and stock rebuilding remain validated.

Version0.11.0 passes144offline tests. Live tests verified current-document part Use flags and native section name/slack/swag edits with post-event stock rebuilding: the QA cable changed from25ft to50ft stock and returned to25ft after restoration. Both QA custom parts were restored enabled. Dimensions sent to section setters always include an explicit mm suffix; getters return mm in the tested version, while bare setter numbers use drawing units. See [native section control](docs/CABLE-SECTIONS.md). The user saw and enabled both custom parts in Manage Cable Parts; the external cache still contains no custom entries, so it cannot establish current-document availability or external-library discovery. Actual custom-part consumption, multi-section/break/loom edits and complete cable workflows remain unfinished. See [custom parts and completion gates](docs/CUSTOM-CABLE-PARTS.md).

Version 0.10.2 adds optional cable geometry summaries and detailed NURBS readback. It reports local straight-path lengths/endpoints, separate parent-space origin/angles and a bounded snapshot fingerprint, while preserving curved controls without inventing a curved length. Full affine/world geometry and connected movement remain unverified. All 108 offline tests and seven fresh installed read-only calls passed. Default results stay compact. See [cable geometry scope and evidence](docs/CABLE-WORKFLOWS.md).

Version 0.10.1 corrects cable inspection using a native power-patch example: one 20-foot Jumper Edison run with one 25-foot stock cable, matching distributor/fixture references and separate stored connector UUIDs despite numeric ports of -1. All 99 offline tests and installed inspector/readback checks pass. The full source chain and movement/path-following workflows remain unfinished. See the latest findings in [cable workflows](docs/CABLE-WORKFLOWS.md).

Version 0.10 adds native distributor insertion with post-event settings/pose/geometry checks and immediate electrical-component definition inspection. The final suite passed 97 offline tests; twelve live calls verified the declared distributor scope. A native power-patch command returned after a timeout, with no observed cable-count or parameter changes; its electrical result remains unverified. The connected cable chain, visual and engineering validation remain unfinished. See [distributor scope and recovery](docs/DISTRIBUTORS.md).

`get_electrical_components` inspects selected parametric objects through a compiled SDK provider, with paired device/component identities, raw consumption and optional internal pin links. Both interface and native extension are installed. All 83 toolkit tests passed; 13 post-install MCP calls checked provider access, two fixture identities/stored wattages, unavailable providers, repeated reads, invalid handles and unstyled viewport contexts. External connection control, physical wiring/specifications and power calculations remain unverified. Read [electrical inspection and deployment](docs/ELECTRICAL-COMPONENTS.md).

`get_cable_connector_catalog` reads one on-disk connector XML snapshot with bounded search, exact-name lookup, optional ordered sockets and hash-guarded paging. It preserves partial/missing socket definitions and asymmetric declarations. It does not establish active override precedence, physical pin wiring or electrical compatibility, and does not create connections. Version 0.8 passed 71 toolkit tests and eight live MCP calls against 105 installed connector definitions, with 276 registered tools. See [connector catalog scope and evidence](docs/CONNECTOR-CATALOG.md).

`create_cable_paths` builds native NURBS-backed corner routes and checks every vertex, transform, ID/class and calculated length in a separate native event. `get_cable_inspection` reads compact modern cable/path data and reports missing configuration. This is route geometry and stored-data control; joins, cable following, pin/port connections, section looms and complete parts/power workflows remain open. All 62 toolkit checks passed; the installed 275-tool server passed an 11-call exercise and native plan/elevation PDF scale review. See [cable workflow scope and evidence](docs/CABLE-WORKFLOWS.md).

`get_viewport_documentation` reads actual legacy/modern annotation-label fields and flags review candidates without editing. It passed a fresh 273-tool server connection, eight live calls and title restoration in QA. See [scope and evidence](docs/VIEWPORT-DOCUMENTATION.md).

`get_viewport_display` reads stored viewport layer/class settings independently of document visibility. Its native style/data-visualization extension is now installed and live-tested on two unstyled viewports with visualization disabled. Styled/enabled and effective-object-display cases remain unverified. See [viewport inspection and native deployment](docs/VIEWPORT-DISPLAY.md). The earlier Python inspection passed 46 toolkit checks and a native visibility/restoration exercise.

`get_data_sheet_inspection` reads exact mapping/sheet names and optionally values on selected UUIDs. It pages field definitions and preserves native value-source/status codes, blanks and failures. It does not certify mapping applicability, field-source correctness or editability. See [native findings and validation](docs/DATA-SHEETS.md) before adding data-sheet mutations.

`get_lighting_patch_audit` reads every matched Lighting Device cell and accessory with native typed getters. It checks recorded single-break address ranges, separates systems/universes, and prioritizes errors in bounded output. Identical patches, unspecified modes and unpatched parts require review rather than automatic correction. Zero-footprint unpatched body cells may use non-DMX control; their purpose must be reviewed. The audit does not validate universe configuration/aliases, GDTF multi-break data, or actual fixture modes. Fresh native Lighting Devices now retain the library Light Info Record's `Num Channels` when provided. See [patch audit findings and validation](docs/LIGHTING-PATCH-AUDIT.md).

`get_entertainment_state` now defaults to `detail="summary"`: document units, document-wide native counts, and scoped attachment/accessory totals and inventory groups. Groups distinguish symbol and body/lens/accessory sources; blank source values remain blank. At most 50 groups are returned, with explicit group-count/truncation metadata. Scope the criteria further when groups are truncated.

Use `detail="devices"` for compact equipment pages with UUIDs, classes/layers, native HP links and supplier fields. Use `detail="full"` for matrices, accessory poses and the previous detailed device format. Page size defaults to 50; `offset` and `next_offset` support UUID-sorted traversal. Each call reads live state, so paging is not a frozen snapshot. Summary counts and inventory always cover all matches, not just the page. `include_structure=true` adds the complete layer/class lists; it defaults true only in full mode.

**0.1 caller migration:** callers that consume `devices`, `layers`, or `classes` must request the appropriate detail/structure mode explicitly. `detail="full", limit=250` reproduces the former default detail coverage. The original mutation workflows are unaffected.

In the 212-fixture QA drawing, the former full response was 165,088 UTF-8 bytes and the default summary was 2,390 bytes (**98.55% smaller**). Attachment/accessory totals and source-group counts matched the baseline exactly. Payload size is a token-use proxy, not measured model-token consumption. Evidence and read-only reproduction code: `tests/benchmark_inspection.py` and `evidence/live-qa/inspection-benchmark.json`.

- Every workflow mutation requires `expected_document`, the full path of the intended active VWX file. A mismatch stops the operation before editing.
- Equipment creation uses two native events: insert, allow Vectorworks to generate its internal geometry, then regenerate with explicit class attributes. The server performs both within one MCP tool call. The native pump yields between events. Do not put this command inside `vwx_batch`; its own `items` list already batches equipment.
- A client still running the OLD server can reach newly installed native commands, but cannot automatically orchestrate both creation stages. If it receives `requires_finalization=true`, call `vwx('finalize_native_objects', {expected_document, created})` with the exact returned `created` rows in a separate call, or reconnect the MCP server. Never recreate the same objects to recover.
- Resource and object names are not silently replaced. A repeated creation returns a collision instead of adding duplicates. Accessory placement reuses one matching native accessory; repeating a worksheet-image placement returns the existing image. Report updates require `update=true` and retain the worksheet resource.
- Model positions use native **design-layer coordinates in document units**; layer elevation is reported separately. Truss member positions are local to their Hanging Position. Viewport centers, worksheet anchors and paper sizes use paper coordinates in document units. Annotation coordinates are projected into the viewport's view plane, with the offset returned by `create_sheet_viewport`.
- Accessory placement inputs are **millimetres**, even in inch documents. Vectorworks' getter returns document units in this build; the toolkit converts readback to mm. Fixture rotations remain degrees.
- Supplier values are exact native inventory identifiers. Body, lens and accessory suppliers can differ. No inventory XML is edited, and stock availability, catalog eligibility and bookings are not inferred.
- Lighting attachment reports query native links. A matching Position text field does not count as an attachment. Auto-attachment scopes the entire Hanging Position and reports all changed Lighting Device links/movements.
- Errors can leave partial native work if the engine fails after creation. The result says so; inspect named objects before retrying. Batch validation handles document, type, resource, coordinate and name errors before edits wherever possible. No claim of transactional rollback is made.

## Examples

For a new show, establish design layers, classes, units and elevations first. Import current library resources, then create truss/hanging positions and other supports before inserting fixtures. Set fixtures' actual transforms, add the appropriate native accessories, run attachment, and inspect actual HP links. Keep supplier/ownership data on instances of one equipment symbol. Create database inventories from that data, repeat worksheet images across sheets, then build scaled viewports and dimensions. Update viewports and inspect the resulting PDF before delivery. Physical connections, approved mounting arrangements and ratings still come from the actual equipment and project requirements.

Use the typed tools normally. In an existing session, the equivalent generic calls use these payloads (substitute the actual path and UUIDs):

```json
{
  "command": "ensure_drawing_structure",
  "params": {
    "expected_document": "C:\\Shows\\Example.vwx",
    "layers": [
      {"name": "10 Rigging", "kind": "design", "scale": 48},
      {"name": "L-101", "kind": "sheet", "paper_size": [36, 24]}
    ],
    "classes": ["LX-Fixtures", "RIG-Truss"]
  }
}
```

```json
{
  "command": "set_lighting_accessories",
  "params": {
    "expected_document": "C:\\Shows\\Example.vwx",
    "device_ids": ["fixture-uuid"],
    "accessories": [
      {"symbol": "Verified Clamp Assembly", "position_mm": [0, 0, 85], "rotation": [0, 0, 0]}
    ]
  }
}
```

The clamp's 85 mm value is an example, not a universal mounting offset. Supply the actual fixture/hardware geometry.

## Reliability fixes

Long rendering blocks the native heartbeat. Once a job is claimed, the server now waits for its result instead of declaring the bridge closed and suggesting a dangerous retry. Completed results remain readable until the existing result TTL expires. `get_bridge_job_status` retrieves them repeatedly; missing/expired results are explicitly uncertain.

Native dynamic VS functions need the genuine menu scripting context even for some read-only queries. Spotlight inspection, library inspection and document-path queries now use that context. Their MCP annotations still correctly identify them as read-only; they are excluded from the background-safe OnIdle manifest.

`draw_dimension` and `create_linear_dimension` now use the correct native direction enums and separate dimension-line offset from text offset. The old MCP enum values remain mapped for compatibility. The unrelated legacy chain-dimension function has not been validated by this release. Viewport class overrides now use `(viewport, class_name, ...)`, not a nonexistent override handle, and report actual readback. Annotation text is sized after viewport adoption, which prevents Vectorworks from shrinking it during reparenting. Save checks the native return and disk artifact instead of swallowing errors.

## What still needs native setup or further development

- The first linked title-block layout and native label legend remain authored/configured resources. These tools reuse them and control their data/placements; they do not pretend that `LinkText` creates native title-block data links.
- PDF export reuses a once-configured native destination. `configure=true` opens the native settings/save dialogs once; choose `configured_output` there. Subsequent exports need no clicks. The tool verifies that exact PDF was updated before copying to `destination`. It does not silently guess where Vectorworks exported, nor does it replace visual page/scale review.
- A resource represented only by a `.vwx.proxy` still needs downloading through Vectorworks. Library browsing/import works on local `.vwx` files.
- `create_truss_position` creates real TrussItems and a native HP profile with library metadata. It does not synthesize inter-member snap connections. Confirm native connections before treating a multiple-piece assembly as a connected system.
- Accessory inspection/placement currently handles cell 0 and one instance per accessory symbol; use a verified assembly symbol for a clamp pair. Multi-cell devices and repeated independent identical accessories need a richer addressing contract.
- Manufacturer-driven symbol authoring, electrical consumer/source/distributor creation, connected cable networks, MVR/GDTF mapping/validation, and additional SDK-only operations are the next development areas. This release does not claim those workflows are automated.
- No ratings, power factors, physical support systems, patch or distribution designs are invented. Parametric object creation is not engineering validation.

## Install and verify

The existing native bridge and Python environment are prerequisites. Run `tools/install_local.ps1` from PowerShell; it backs up each existing deployed file and writes a SHA-256 deployment manifest under `evidence`. It does not modify the C++ bridge, workspace, Codex credentials, or upstream remote. Python commands hot-reload. Start a new MCP connection to load the changed server/tool catalog.

Optional tool preset: `VWX_TOOLSET=entertainment`. The full preset remains the installed default.

Run offline regression tests with the installed server Python:

```powershell
& "$env:USERPROFILE\.local\share\vwx-mcp\.venv\Scripts\python.exe" -m unittest discover -s tests -v
```

`tests/live_smoke.py` is an explicit integration exercise for the separate Toolkit QA drawing copy. It is not an automatic test to run against a working show file. Each call and result is recorded in `evidence/live-qa`; repeated creation phases intentionally stop on existing names. The reviewed Armory VWX and PDF are protected by before/after file hashes.

See [the validation report](docs/TOOLKIT-VALIDATION.md) for the installed/live results, physical PDF scale checks and specific untested areas.
