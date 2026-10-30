# Native cable initialization experiment

**Parked by user request.** The extension was installed and exercised once. Native style update and deferred regeneration both left stored Length at zero. The new probe `becd54c6-7e1f-4b8d-8c2d-9a7633cdcbcb` has a 6096mm path; it is retained for inspection. Guards passed, reference snapshots stayed unchanged, and seven existing native-reader regression calls passed. See `evidence/live-qa/native-cable-lifecycle-probe.json` and `live-native-readers.json`. Do not rerun creation. The proposed subsequent UI Move experiment was canceled before any movement. Work has moved to lighting, rigging and staging.

The separate QA fixture `944ec808-fb71-48df-bd4c-5484b4ae964c` was created using CreateCustomObjectN, then SetCustomObjectPath, SetPluginStyle and ResetObject. Its section/path were 6,096 mm but stored Length remained zero. Evidence: `true1-constructor-n.json`. It is now the four-foot asymmetric connector/stock fixture described in [connector configuration](CABLE-CONNECTOR-CONFIGURATION.md).

The Python `UpdatePIOFromStyle(h)` call returned a null handle and no observed length repair. The published Python signature has no input despite the VectorScript declaration requiring a VAR object handle. This is a binding inconsistency to investigate, not proof that the native method fails. Evidence: `true1-update-style-call.json` and `true1-update-style-result.json`.

A duplicate of the official style, `VM QA TRUE1 Style Lifecycle`, was assigned only to this probe. `UpdateStyledObjects` rebuilt its native stock but left stored Length zero. The existing chain and user-drawn reference snapshots remained unchanged. Later edits to the isolated style's start/end fields propagated and selected the custom Edison-to-TRUE1 part correctly. No shared official style was edited. Evidence: `true1-isolated-style-update.json`.

## Extension design (installed; initialization experiment failed)

`VMCableLifecycleProbe(requestJSON)` provides a narrow experiment using SDK 832364 APIs:

- `update_style`: only a top-level active-layer CableObject with blank object/component endpoint references; calls the actual SDK UpdatePIOFromStyle(handle), then ResetObject.
- `create_styled`: consumes an existing top-level active-layer linear NURBS path and applies an existing CableObject style. Calls CreateCustomObjectPath with **doRegen=false**, assigns the style, calls UpdatePIOFromStyle, then regenerates. It inherits the path class. It does not set private endpoints or computed Length.

Both operations require an exact saved active-document guard. Requests, style traversal and paths are bounded; styles containing endpoint references are rejected. Errors retain created UUIDs and prohibit automatic retry after mutation begins. Success means the native calls returned; separate-event verification remains mandatory. This is an experimental script extension, not an exposed production MCP cable creator or proof of correct initialization/connections.

Compiled and backed up pair: `evidence/native-cable-lifecycle-deployment/manifest.json`; build log is alongside it. It also retains the viewport, electrical and library-export functions. Install only after Vectorworks closes normally:

```powershell
& .\tools\install_staged_native.ps1 -ManifestPath .\evidence\native-cable-lifecycle-deployment\manifest.json
```

The installer requires an explicit manifest rather than defaulting to an obsolete bridge. `tests/live_cable_lifecycle_probe.py` has already executed; do not rerun it. Failed length agreement remains a failed experiment, not a working factory.

Sources: [SetPluginStyle example with separate style update](https://raw.githubusercontent.com/Vectorworks/developer-scripting/main/Function%20Reference/Functions/SetPluginStyle.md), [UpdatePIOFromStyle signature](https://raw.githubusercontent.com/Vectorworks/developer-scripting/main/Function%20Reference/Functions/UpdatePIOFromStyle.md), [UpdateStyledObjects](https://raw.githubusercontent.com/Vectorworks/developer-scripting/main/Function%20Reference/Functions/UpdateStyledObjects.md), and installed `ISDK.h` declarations for CreateCustomObjectPath and UpdatePIOFromStyle.
