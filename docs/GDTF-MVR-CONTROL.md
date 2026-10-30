# GDTF and MVR controls

User requirement: GDTF assignment must be controlled properly for MVR export, including the actual file, exact mode, geometry setting and exported data.

## Working readers

- `get_gdtf_file`: inspect a local GDTF archive, file SHA256, FixtureTypeID, declared manufacturer/name, exact modes, model/reference counts and direct DMX-break spans. A simple single-break footprint is reported only without geometry references or unresolved offsets/breaks. It is not a complete GDTF geometry or multi-break evaluator.
- `get_lighting_gdtf`: read the installed Lighting Device's actual GDTF fields, native footprint and state fingerprint. Field strings do not prove that the correct archive is embedded.
- `get_mvr_gdtf_audit`: read an existing MVR, check fixture UUIDs, exact embedded GDTF filenames and exact mode membership inside each embedded archive. Full scoped issue counts and bounded details; no file modifications or extraction.

The bundled `Generic@LED_RGB8.gdtf` was read as mode `Default`, with three addressed slots plus a virtual dimmer. The user's `Get Cranked 2.0 C.1 MVR.mvr` passed the embedded file/mode checks for 98 fixtures. This does not certify the fixture specifications, patch, geometry, live file assignment or destination application's interpretation. Evidence: `evidence/live-qa/gdtf-readers-installed.json`.

Archive limits: 100 MB file, 16 MB XML, 10000 members/fixtures, 200 modes or referenced GDTFs, and 100 MB total referenced embedded GDTFs. DTD/entity XML is rejected. Geometry-reference expansion and unresolved breaks are reported as outside the simple footprint scope, not guessed.

## Native importer/exporter: installed, not runtime verified

`VMGDTFExchange(requestJSON)` wraps the SDK's `IImportExportGDTF::ImportLightingDeviceGDTF` and `ExportLightingDeviceGDTF`. It requires the saved document path, explicit target device UUID, local .gdtf path, and an exact mode for imports. Exports refuse existing destinations. It preserves the four existing native functions. It never fabricates a mode, Type ID or footprint with text writes.

`assign_gdtf_file` validates the GDTF hash/mode and device fingerprint before calling the native importer. The initial scope is one unpatched single-cell device and a resolvable simple single-break mode. The geometry switch is explicit. Separate-event checks cover requested mode, native footprint, geometry switch and protected fixture state. Assignment verification alone does not establish embedded file identity; export it and compare its contents.

`export_lighting_gdtf` uses the native exporter and inspects its output. The SDK can synthesize a generic GDTF when a manufacturer archive is absent. Therefore the output must be compared against the intended source's hash, FixtureTypeID and modes. Manufacturer metadata is a declaration, not authentication.

The pair in `evidence/native-gdtf-exchange-deployment/manifest.json` was installed after verifying Vectorworks was closed. Its state is `installed_pending_runtime_validation`; do not reinstall this completed deployment. Vectorworks was launched, but computer input was stopped by the user with Escape. The next read returned `VW_BRIDGE_DOWN` (palette heartbeat never); no GDTF command executed and no mutation is pending. Re-establish the palette and confirm the QA document before runtime checks.

After restart into the separate QA drawing, run `tests/live_gdtf_native.py` **once** and preserve its receipt. The prepared test creates a clearly labeled disposable API-contract fixture, assigns the bundled generic RGB profile with GDTF geometry disabled, exports it, compares identity/modes, and confirms existing QA reference fixtures are unchanged. The test object intentionally does not represent real hardware. This harness has not yet run.

Pending: native import/export runtime proof, correct source-file identity after assignment, geometry-on orientation comparison, authentic model/mode testing, multi-cell and geometry-reference layouts, reassignment/resource collision behavior, patched-device changes, MVR export settings and a destination-application round trip. The MVR audit does not export MVR or validate transforms/patch. Do not report these as completed.

Sources: installed SDK 832364 `Filing/IImportExportGDTF.h`; [Vectorworks attaching GDTF](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/LightingDesign2/Attaching_GDTF_data.htm); [MVR/GDTF specification repository](https://github.com/mvrdevelopment/spec); [GDTF file format](https://gdtf-development.com/help/developers/gdtf_1_2/file-format-definition/index.html).
