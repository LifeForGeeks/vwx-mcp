# Viewport organization and native context

Version 0.5.0 adds `get_viewport_display`. It inspects the stored layer/class visibility of up to ten viewports in one MCP call. A summary includes scale, crop presence, view/projection codes, out-of-date state, class/layer visibility counts, and attribute-override counts. This makes it possible to compare department sheets without repeatedly opening their Layers and Classes dialogs.

```json
{"viewport_ids":["actual-viewport-uuid"]}
```

For specific names and detailed states:

```json
{"viewport_ids":["actual-viewport-uuid"],"detail":"visibility","class_names":["LX-Fixtures"],"layer_names":["Lighting"],"offset":0,"limit":50}
```

Use actual document names; examples are not installed house classes. Omitted name lists mean all document classes/design layers. Empty lists select none. Names are sorted alphabetically; offset/limit apply independently to the class and layer lists. Counts cover the entire selected scope, independently of paging. The page maximum is 200; the overall call maximum is 100,000 native visibility reads. Detail rows distinguish viewport visibility from document visibility. Native failure is `unknown`, never silently `visible`.

## What these settings mean

Native visibility codes are `-1` hidden, `0` visible, and `2` gray. Class attribute overrides are a separate setting. Neither a visible layer nor a visible class proves an individual object appears in the viewport: crop, object hierarchy, embedded viewports, per-object hides, styles and data visualization can affect the result. The response therefore explicitly sets `final_object_visibility_verified: false`. It does not inspect all those object relationships, viewport-style parameter ownership, print legibility or exported physical scale.

The [Vectorworks viewport display guide](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Viewports2/Overriding_viewport_display.htm) distinguishes layer/class properties, viewport styles and object display. [Class-property documentation](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Viewports2/Changing_the_class_properties_of_sheet_layer_or_design_layer.htm) explains viewport-specific visibility and the separate handling of embedded viewports and settings controlled by style. [Data visualization documentation](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Views/Applying_a_data_visualization.htm?agt=index) describes how visualization settings can supersede class overrides and prevent layer overrides from displaying. These distinctions prevent a document-wide class check from being mistaken for an issued-sheet check.

## Native SDK extension: installed, limited runtime scope verified

`native/Source/Bridge/VMNativeFunctions.cpp` adds the scripting procedure `VMGetViewportContext(viewportHandle) -> JSON string`. It uses the SDK's dedicated `ISDK::GetViewportStyle`, rather than assuming the generic plug-in-style getter describes viewports. It also reads the `IAttrByDataOverride` service with a balanced `AddContext`/`RemoveContext` scope. Results include the native style success/index/name and the service's enabled/paused state and scheme information. This does not yet inspect each object's final attributes or certify multi-scheme behavior.

The procedure was absent before implementation. It compiled and linked with MSVC v145 against SDK 832364, and was installed with the electrical reader after a normal Vectorworks close/restart. No startup side effects were added: registration only, with queries made when called. JSON string output, null-handle errors and repeated reads on two unstyled viewports are now verified. Both reported style index zero and an available, disabled/unpaused visualization service. Styled viewports, visualization-enabled cases, effective object attributes and restoration of nonempty visualization contexts still need live tests.

The original bridge remains backed up. The earlier viewport-only manifest is superseded; use `evidence/native-electrical-deployment/manifest.json` for the installed combined extension. The user closed Vectorworks normally, the guarded installer verified all hashes and the QA file was reopened. `tests/live_native_readers.py` retains the seven-call combined fixture/viewport exercise in `evidence/live-qa/live-native-readers.json`. No drawing mutations or object resets were performed. Window capture failed after QA loaded, so these native tests are not visual output verification.

For future native updates:

1. Create and inspect a new staged manifest before running `tools/install_staged_native.ps1`. Do not rerun the completed installation receipt. The installer refuses to run while Vectorworks is running and verifies source, installed and backup hashes before replacement.
2. Start Vectorworks, reopen the separate QA drawing and enable the existing bridge palette if necessary.
3. Validate `VMGetViewportContext` on unstyled/styled and visualization-disabled/enabled viewports, including wrong handles and repeated context entry/exit. Confirm the scripting output shape before relying on it.
4. Update the receipt and evidence only after actual runtime verification. Preserve the backup for rollback. The native installer does not mark runtime success.

`tools/build_native.ps1` makes the build reproducible. The project retains its upstream v143 default, while the helper selects the locally installed v145 toolset. Neither the build helper nor the Python updater installs a native binary implicitly.

## Verified Python inspection

Eight new tests first failed and then passed; the full toolkit suite passes **46** checks. The installed-server test `tests/live_viewport_display.py` confirmed **272** tools and exercised class and layer visible/hidden/gray settings on the separate QA viewport. It checked the second viewport and document-wide states, then restored and verified the original settings and scale. The test updates the viewport after restoration; it does not export or visually certify the resulting PDF.

Evidence: `evidence/live-qa/live-viewport-display.json`, `viewport-visibility-restore.json`, `viewport-unit-tests.txt`, and the deployment manifests. A subsequent native call verified that explicit empty name scopes at a later page offset do not falsely report truncation.

The tool is read-only and explicitly excluded from background-safe reads: dynamic native functions require a genuine scripting/menu context. Production visibility mutations and viewport-style editing remain work to implement and validate, not hidden assumptions in this inspector.
