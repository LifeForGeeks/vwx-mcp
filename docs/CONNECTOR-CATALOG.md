# Cable connector catalog — version 0.8

`get_cable_connector_catalog` makes the installed connector definitions available through a bounded, read-only MCP call. This supplies exact identities and recorded socket structure for subsequent cable workflows; it does not create or verify native network connections.

## Usage

```python
get_cable_connector_catalog(search="Socapex", limit=25)
get_cable_connector_catalog(names=["XLR5"], include_sockets=True)
```

The default source is `Libraries/Entertainment/Power/Cable Tools/CableConnectors.xml` below the running application's `vs.GetFolderPath(1)`. An explicit absolute `.xml` path selects that file only; missing files never fall back silently. Each response includes the resolved source path, kind, SHA256 and byte count. Use `expected_sha256` on subsequent pages to reject a changed snapshot.

Search matches universal and localized names without case sensitivity. Exact `names` queries require universal names, preserve unresolved requests in `missing_names`, and cannot be combined with search. Limits: 25 exact names, 50 entries per page, 1 MiB input, 2,048 entries and 1,000 returned socket/link rows per page. Reduce page size when detailed output exceeds its bound. Parsing accepts the observed UTF-8 schema and rejects DTD/entities, duplicate connector identities, unknown fields and malformed counts rather than guessing their meaning.

Results preserve connector universal/localized names, declared socket count, listed socket count, definition status and repeated socket names. Optional sockets retain XML order, including duplicate labels; their `index` is zero-based XML order, **not a certified physical pin number**. `declared_connections` records each directional `ConnectableWith` declaration, whether its target exists in this file and whether that target declares the reverse relationship. Absence or reciprocity does not establish electrical compatibility.

The response explicitly reports `active_catalog_precedence_verified`, `electrical_compatibility_verified` and `physical_wiring_verified` as false. User/workgroup precedence, Vectorworks' in-memory catalog, physical wiring and engineering ratings are outside this tool's scope. No document, catalog or connection setters are called. Native application-folder lookup is kept in menu scripting context.

## Observed installed data

The tested VW2026 application file contains 105 connectors in 35,218 bytes. These observations describe that snapshot:

- Six entries match Socapex. The 120 V US 19-socket definition repeats PE1 at indices 12–14 and PE2 at 15–17; these repeated labels remain intact.
- The US 208 V Socapex definition declares the 230 V definition, but the latter does not declare the reverse. The result preserves that asymmetry.
- Socapex-16 declares 16 sockets but lists seven; this is `count_differs`.
- XLR5 declares five sockets but lists none; this is `not_listed`. The tool does not invent a DMX pinout. Its display name, `5-pin XLR`, is not accepted as an exact universal-name alias.

## Verification

All 71 toolkit tests passed, including nine new tests for snapshot changes, bounds, parsing, exact lookup, missing/partial maps, repeated labels and directional declarations. A fresh installed MCP connection registered 276 tools and passed eight live calls: application lookup/search, guarded paging, detailed Socapex lookup, unresolved alias, deliberate hash mismatch, explicit-file lookup, and QA state checks before/after. Source bytes and captured active document/layer/class/path-count state were unchanged; this is not a complete object-by-object document comparison.

Evidence: `../evidence/connector-full-suite.txt`, `../evidence/live-qa/live-connector-catalog.json`, `../evidence/connector-verification.json`. Deployment: `../evidence/deployment-20260912-101555/manifest.json`, with seven matching installed hashes. Tests: `../tests/test_connector_catalog.py` and `../tests/live_connector_catalog.py`.

The native electrical-component provider remains a separate SDK integration task. No C++ binary was changed or restarted for this tool.
