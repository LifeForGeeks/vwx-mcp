# Lighting documentation and numbering

Version 0.15.0 adds `get_lighting_documentation`, `set_lighting_documentation` and `number_lighting_devices`.

Read the selected UUIDs to obtain current native Unit Number, Channel, Purpose and Color values plus edit fingerprints. Submit explicit values or number the supplied list in its chosen order, with optional start/increment/prefix/suffix/zero padding. A dry run previews changes. Empty strings clear fields. Channel remains a control identifier; numbering never assigns a DMX address.

This release handles up to 25 single-cell native Lighting Devices with up to 20 accessories each. Multi-cell and schematic representations are rejected. Numbering does not infer spatial order, restart at each hanging position or reject intentional duplicate channels on unselected fixtures. The native string setter uses cell 0 and accessory -2, targeting the device rather than all accessories.

All rows and fingerprints are checked before any edit. After regeneration, a separate native event checks native and worksheet-source field values and preserves scoped matrix/layer/class/rigging attachment, accessory symbols/poses, inventory sources, GDTF assignments, modes and DMX patch. GDTF file/mode fields use their actual installed names, including `GDTF Fixture Name`. Color may change native light appearance; color-setting accuracy does not establish rendered color accuracy.

Successful responses omit large internal verification receipts and return compact device state plus guarded `rollback_items`. Submit those items only if restoration is wanted and their fingerprints are still current. Failed or uncertain operations retain receipts; inspect before retrying. There is no automatic rollback after an uncertain native call.

Live QA numbered two attached fixtures, changed channel/purpose/color, rejected stale edits, then restored their original fields. Both native clamps and rigging links, GDTF/mode state and patch remained unchanged. Evidence: `lighting-documentation-verified.json` in `evidence/live-qa`. The original receipt `lighting-documentation-installed.json` records a comparison bug caused by tuples becoming lists across JSON; snapshots are now normalized before comparison. Do not rerun either one-shot harness. Native worksheet source values were verified; rendered label layout and worksheet recalculation were not.

The command pump now explicitly yields after these mutations and after stage-grid creation. Do not place them in a single-event batch.

References: [Vectorworks Lighting Device properties](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/LightingDesign1/Lighting_device_properties.htm), [native string setter](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/LDevice_SetParamStr.md).
