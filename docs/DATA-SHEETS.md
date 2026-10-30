# Native data-sheet inspection

Version 0.4.0 adds `get_data_sheet_inspection`. It reads Data Manager sheet definitions and selected Object Info data values in one native call, without opening dialogs or dumping all plug-in parameters. This is an inspection tool, not an IFC certification or a data-sheet editor.

## Use

List the sheets for an exact Data Manager mapping name:

```json
{"mapping_name":"Lighting Device"}
```

Read a named sheet's field definitions and optionally its values on up to ten object UUIDs:

```json
{"mapping_name":"Lighting Device","data_sheet":"Production","object_ids":["actual-object-uuid"],"field_offset":0,"field_limit":25}
```

`Production` is an example, not an automatically installed house sheet. Use the returned sheet names. Mapping names may represent plug-in, symbol, or criteria mappings; the caller must choose the appropriate definition. The tool does not prove that a selected mapping applies to each selected object. Objects are addressed independently by UUID and read through the object-specific DSH API.

The definition includes zero-based field indices, labels, visibility and formula flags. Values include native success, raw operation-status and source codes. Blank successful values remain blank. Failed reads return `value: null` and contribute to `failed_reads`; missing objects or unavailable object sheets contribute to `object_errors`. A failed definition query returns an error rather than a fabricated empty sheet. Field pages cap at 50, values at 512 characters with a truncation flag. Sheet-name listing caps at 100 with explicit truncation. Reads are live, not a frozen snapshot.

## Findings verified in Vectorworks 2026 Update 2.1

The separate `Velvet-Mirror-Toolkit-QA.vwx` contains two experimental Lighting Device sheets: `VM QA Device` and `VM QA Empty`. The former exposes Channel, Supplier (Body Inventory), Fixture Model (Inst Type), and Fixture ID (FixtureID). Its Supplier field is intentionally hidden for testing. These are QA fixtures, not a finished house standard or changes to source show documents.

- `IFC_GetDSNameAt(mapping, index)` and `IFC_GetDSFieldInfoAt(mapping, sheet, index)` enumerate with **zero-based** indices.
- The documented Python `DSH_GetDSNameAt(object)` and `DSH_GetDSFieldInfoAt(object, sheet)` expose index variables as outputs, unlike the indexed C++ SDK interface. Repeated object-name calls produced different success/index results on the same prepared object; field-info calls failed. They are not used for enumeration. We did not guess alternative Python arities or modify the signature index.
- `DSH_GetDSFieldValue(object, sheet, label)` reliably returned `Chauvet Color Strike M` and `LX-160` from the known fixture. Its blank supplier remained a successful blank read.
- `IFC_AddDSField('Lighting Device', sheet, 'Lighting Device', '', universal_field_name, label)` linked the tested native fields. Use actual universal names: **Inst Type**, not the guessed **Instrument Type**. The API accepted the nonexistent name and returned a misleading `"0"`; success alone does not validate source correctness.
- Hiding Supplier through `IFC_SetDSFieldVis` changed its definition's visibility to false. Reading the hidden value still returned operation status `2`, the same as the visible fields. Do not interpret status `2` as visible or independently certified editable.
- SDK source codes are `-1` not set, `0` instance, `1` mapping, `2` instance mapped, `3` GUID. Only the instance and failed-read cases were observed live in this pass. Unknown codes are preserved. Operation-status numeric meanings are deliberately not inferred.
- A separate exploratory criteria mapping was created successfully, but DSH queries on its 2D locus/rectangle failed. Those test objects and that mapping were removed. General criteria-mapping application remains unresolved; there is no production mapping-creation tool in this release.

The native main-thread/menu context is required. The tool is marked read-only for MCP clients and explicitly excluded from background-safe reads. No plug-in reset or object edit occurs during inspection.

## Validation and limits

Eight new unit tests first failed before implementation; all **38** toolkit tests then passed. `tests/live_data_sheets.py` opened a fresh installed MCP connection, confirmed **271** registered tools, and passed seven native calls covering path, names, values/visibility, paging, an empty sheet, a missing sheet, and a missing object. Evidence is in `evidence/live-qa/live-data-sheets.json`. This demonstrates native API data, not visual OIP layout, editing, mapping-derived values, or save/reopen persistence. The QA file was saved after setup; it was not reopened for this check.

The installed updater retained backups and SHA-256 manifests under `evidence/deployment-20260912-073950`. New connections expose the named tool; the existing connection can use `vwx` with command `get_data_sheet_inspection`. There is no new native binary.

Primary references: [Vectorworks data-sheet scripting functions](https://www.vectorworks.co.jp/develop/ScriptReference/Pages/DataSheets.html), [Vectorworks Data Manager scripting functions](https://www.vectorworks.co.jp/develop/ScriptReference/Pages/IFC.html), and installed SDK `IIFCSupport.h` / `vs.py`. The SDK establishes possible capabilities; live evidence establishes only the cases listed above.
