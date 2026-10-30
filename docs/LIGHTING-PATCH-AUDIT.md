# Lighting patch audit — 0.3.0

Learned and verified in Vectorworks 2026 Update 2.1 on 12 September 2026. The new `get_lighting_patch_audit` inspects native Lighting Device cells and their accessories in one MCP call. It performs no model edits.

## Native behavior and sources

- Cells and accessories can be independently patched. Systems separate address spaces. Identical starting address/channel combinations can be intentional, so the tool reports them for review rather than silently changing them. [Vectorworks DMX patch workflow](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/LightingDesign2/DMX%20patching.htm).
- Universes contain 512 addresses; the native preferences show the configured labels and address ranges. The QA document's System A, universe 1 had range 1–512, verified visually in Spotlight Preferences. The dialog was canceled without changing settings. [Universe preferences](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Setup/Spotlight_preferences_Universes_pane.htm).
- The displayed DMX footprint is stored under the installed parameter name `Num Channels`. Modes can supply that footprint; GDTF takes precedence when both fixture modes are set. The audit reads the recorded footprint and does not certify its manufacturer/mode correctness. [Lighting Device properties](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/LightingDesign1/Lighting_device_properties.htm).
- The bundled SDK stub incorrectly described accessory index -1 as the parent. Live reads returned empty/zero values. Parent-cell reads use **-2**; numeric fields require `LDevice_GetParamLong`. -1 is unsupported for getters. Setter -1 targets ALL accessories. Verified against [GetParamStr](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/LDevice_GetParamStr.md), [GetParamLong](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/LDevice_GetParamLong.md), and [SetParamLong](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/LDevice_SetParamLong.md). Index corrections and the index builder preserve this lesson.

## Live tests and resulting changes

Two known QA fixtures were temporarily configured with controlled patch values, then restored from a saved receipt. Tests verified an overlapping range, identical addresses in different systems without conflict, identical patching as a review item, universe overflow, and the restored unpatched state. Each original fixture's saved fields, transform and actual native HP link matched after restoration. Existing source/delivery files were not used for these edits.

During setup, separate Universe/DMX Address/Absolute Address edits were cleared on regeneration. Keeping the combined `UniverseAddress` string consistent made the values persist. Typed native setters were used in the final successful tests. This is evidence for the current build and QA configuration, not a universal patch-writing API: separators, configured universes, aliases and multi-break mapping still need an explicit mutation contract. There is no automatic patch-fix tool in this release.

The investigation also found that the generic Lighting Device creator omitted the library `Num Channels` value and retained the default 1. It now copies that field from the Light Info Record. A fresh Robe Pointe test device retained the library's 30-channel footprint, remained unpatched, and was removed after the check. No particular operating mode was inferred.

The initial whole-QA read traversed 212 Lighting Devices and 578 cell/accessory parts, including 366 accessories without footprint or patch. Those accessory records are excluded from control-range conflicts. Zero-footprint unpatched body cells are review items because they may use non-DMX control. The tool does not treat them as proof of a faulty laser design.

## Output and coverage

Default output includes complete scoped counts, error/review counts, and at most 50 issues. Errors are returned before review items, so missing-mode notices cannot hide an address conflict. `include_parts=true` returns up to `limit` source rows for diagnosis. UUID/cell/accessory keys identify precise parts. Schematic representations identified by native `IsLDSchematicViewObj` are counted separately and excluded to avoid duplicate fixture conflicts. The QA drawing had no such representations; exclusion is covered by a regression test. More than 2,000 parts is rejected before analysis; narrow criteria rather than accepting an incomplete audit. Narrow criteria exclude conflicts with unmatched fixtures.

Checks use recorded single-break intervals. Multi-break GDTF layouts, universe existence and label aliases, mode correctness, network wiring, and actual hardware settings are not certified. Universe labels are compared exactly after whitespace trimming. Multiple cells are exercised by regression tests; live conflict tests used single-cell fixtures and their native clamp accessories.

Evidence: `tests/test_patch_audit.py`, `tests/live_patch_audit.py`, `tests/live_library_footprint.py`, and local ignored `evidence/live-qa/live-patch-audit.json`, `patch-restore-receipt.json`, `library-footprint-check.json`. The installed server now exposes 270 tools, including 20 entertainment workflows.
