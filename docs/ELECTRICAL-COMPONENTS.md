# Electrical-component inspection — version 0.9

Status: Python/MCP interface and compiled SDK extension **installed and live-tested for the scope below**. All 83 offline toolkit tests passed. After the normal restart, six MCP calls verified provider access and seven further calls checked two fixtures, repeated identities/reads, invalid handles and two unstyled viewport contexts. The server registers 277 tools (27 entertainment plus 250 upstream). This is native inspection, not external connection creation or electrical design validation.

## Interface

```python
get_electrical_components(object_ids=["actual-object-uuid"])
get_electrical_components(
    object_ids=["actual-object-uuid"], detail="components",
    include_internal_connections=True, limit=100)
```

The tool accepts up to ten unique native parametric-object UUIDs. Plain symbols and other types are explicitly unsupported in this initial adapter; their electrical participation is not denied. Summary counts cover all returned components. Detail preserves provider order, returning up to 100 components per object; truncation is explicit. Internal links require an explicit detail option. Missing objects, unsupported object types, absent extension, absent provider and provider/contract failures remain distinct from successful empty arrays.

Each component exposes its paired device/component identity, raw type code, name, connector universal name, average/maximum consumption in watts, virtual-component flag and link-through flag. Unknown type codes remain unknown. Consumption is provider data, never summed into a circuit total: inputs and consumers can describe shared downstream demand. The SDK marks its separate voltage/maximum-power fields as unused; this adapter deliberately omits them. Power factor, operating voltage, breaker ratings, external cable connections and native power-calculation results are outside this contract.

Optional internal links retain the provider's own/other socket indices and target component identity. Target matching is restricted to the same device UUID. Duplicate pairs and missing identities are reported; repeated component IDs under different devices remain legal. A target match is an identity check, not proof of correct physical wiring. No reverse links or missing pin maps are invented. Use the connector catalog for exact declared connector structure, observing its separate wiring/precedence limits.

The native reader uses `VCOMSinkPtr<ICableConnectionsProvider>(object, IID_CableConnectionsProvider)` and `GetObjectConnections`. It calls no object setters/resets and no connection mutation service. Payload limits are 512 components, 2,048 internal links total, 2,048 bytes per native string and 1 MB serialized JSON. Invalid/non-finite consumption rejects the snapshot. Python independently validates field types, identities, bounds and contract version before presenting results. Both `external_connections_verified` and `engineering_values_verified` remain false.

## Native build and deployment

Built against installed Vectorworks SDK 2026 build 832364 with MSVC v145. `VMNativeFunctions.cpp` registers `VMGetElectricalComponents` alongside `VMGetViewportContext`. The definition's 3100 field is the function version, not a selector; dispatch uses zero-based function indices. SDK `AddRoutine` dispatches every registered routine for each action, so this implementation registers one dispatcher, not one duplicate dispatcher per function.

The installed pair, immutable staged copies and original installed backups are recorded in `../evidence/native-electrical-deployment/manifest.json`; build log sits beside it. The earlier viewport-only staged pair was archived separately before rebuilding. Do not install that older pair over the new extension.

Installation completed after the user saved and closed Vectorworks normally. `tools/install_staged_native.ps1` checked process state and the staged, installed and backup hashes before copying. Vectorworks was restarted and the separate toolkit QA file opened. Do not rerun the installer against the completed receipt or replace a loaded binary. Provider availability remains object-specific.

Computer Use could capture startup and the Open dialog after restart, but the error `window crop is outside captured monitor` returned after the QA file loaded. The bridge automatically resumed and direct MCP validation succeeded. Visual OIP/schematic comparison remains pending; no production/source show was edited.

## Validation and remaining cases

`tests/test_electrical_components.py`: 12 new tests, including duplicate paired identities, cross-device IDs, unavailable/empty/failure distinctions, malformed/non-finite values, output bounds and read-only menu routing. Evidence: `../evidence/electrical-full-suite.txt`, `../evidence/live-qa/live-electrical-components.json` and `../evidence/electrical-verification.json`.

The initial unavailable-extension exercise is archived as `electrical-before-native-install.json`. The post-install `live-electrical-components.json` inspected one existing Lighting Device, CableObject and CablePathObject without creating geometry: the Lighting Device returned components; the cable/path objects reported no provider. Summary/detail, missing UUID, duplicate request rejection and before/after object-list/layer/class checks passed.

`tests/live_native_readers.py` and `live-native-readers.json` add seven read-only calls. Two Color STRIKE M instances each returned a virtual consumer and link-through output. Both output components use UUID `00000000-0000-0000-0000-000000000001`, correctly distinguished by their different device UUIDs. The consumer component identity was empty and remains explicitly reported rather than repaired; its native link targets the output within that device. These virtual defaults do not establish invalid equipment or a physical socket layout. Both consumer values were 870 W, matching each stored `Lighting Device.Wattage` value `870 W`. Both native connector names were `NEMA 5-15`; that is the provider's stored/default data, not a verified hardware connector specification. Only the single native socket-index-0 link was returned; no additional pin wiring was invented.

Repeated reads were stable. Both unstyled QA viewports returned successful dedicated style reads with resource index zero and an available, disabled/unpaused data-visualization service. Both native functions returned JSON errors for null handles. Captured QA state stayed unchanged; this does not compare every property of every object or visually verify an electrical system.

Remaining cases: compare component names/connectors and ordering visually with OIP/schematic; test a distributor with known internal links and physical components; validate actual hardware specifications and calculation fields; test persistence across another save/reopen; then investigate external network mutation and calculation services. Full power-network, cable-parts and rigging workflows remain ongoing.

Official workflow context: Vectorworks' [Creating custom electrical devices](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Cables/Creating_custom_electrical_devices.htm) explains components within device symbols and notes that stacking order determines the displayed input/output order. This establishes why order matters; it does not prove provider order equals OIP order. That correspondence is a pending runtime check.
