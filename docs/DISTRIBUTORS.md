# Native distributors

## Latest native patch result and inspector correction (0.10.1)

The user confirmed the second native command reported **2 successful**. Poll of CID `a1710eccf3eb` returned done. Cable count increased from 2 to 3: one new native CableObject `9c27b811-8318-406c-bc1b-0c3dd22d7b19`, now named `VM-QA-CHAIN-JUMPER`. Its style is `Jumper Edison`, drawn length 240 document inches (20 ft), stocked length 300 inches (25 ft), ordered stock code `E-25ft`. The twofer `d718aced-1403-442a-8cd7-a8bcedcd6ee5` references that cable in OutputUUID1, and the cable's endpoint object UUIDs match that twofer and the selected fixture `8734ee85-3bdf-4541-9858-a4aef0c8fbcd`. The message count is not a count of newly drawn cables. The source/distributor-only zero result does not prove a universal command limitation.

Native creation inherited active class `SHEET-Text`; this QA cable was reassigned to `VM-QA-Electrical-Cables`. Future native patch wrappers must establish and restore the intended layer/class context. No private fields were written.

The cable has separate stored connector references: __StartConnectorUUID is `111eb5fe-2a27-4fb0-9c4e-12d819cdc78a` (matching the library's output component geometry UUID), and __EndConnectorUUID is all zeros, while StartObjectPort and EndObjectPort both remain -1. Version 0.10.1 exposes these optional reference strings as read-only diagnostics and distinguishes unavailable, blank, zero UUID and present-unverified states. It renames `endpoint_port_unassigned` to `endpoint_port_unspecified`; numeric -1 alone is not proof of disconnection. Zero identities are preserved, not repaired or automatically rejected. This is not complete runtime circuit or pin verification.

Movement trials found that HMove used the current view plane, while Move3DObj produced the intended [600,0,0] model position. Neither updated the 240-inch cable path, including a subsequent LDevice_Reset. The fixture was restored exactly to [480,0,0], cable geometry/references/class were checked, and QA was saved. Do not use these low-level moves as a verified connected-equipment movement workflow. The simulated source still has no observed connection; source-to-distributor patching, OIP/schematic comparison, movement/path following, looms, inventory completion and engineering calculations remain unfinished.

All 99 offline tests pass. The installed inspector and final QA readback/save passed live. Seven deployment hashes match `evidence/deployment-20260912-115429/manifest.json`. Evidence: `power-patch-fixture-trial.json`, `power-patch-fixture-after.json`, `cable-movement-trial.json`, `power-patch-final-readback.json` in `evidence/live-qa`; summary `evidence/cable-patch-verification.json`. No command remains pending and no source-show document was edited.

## Earlier release findings

Version 0.10.0 adds `create_distributors` and `get_distributor_inspection`: 29 entertainment workflows / 279 total tools. This implements equipment insertion and inspection. The connected source → distributor → cable → fixture workflow remains incomplete.

## Contracts

`create_distributors(expected_document, items)` inserts up to 25 native `DistributorObject` instances using existing symbol definitions. Each item supplies an existing design `layer` and `class`, unique object `name`, unique distributor `device_id`, `symbol`, `position`, optional `rotation`, `description` and `location`. Positions use design-layer document units; rotations use degrees. The entire batch is preflighted before insertion. Existing equipment and library definitions are preserved. Arbitrary/private connection fields are rejected.

The server verifies each creation after regeneration in a separate native event. Read-only `get_distributor_verification` checks native type, generated symbol reference, settings, matrix, layer/class and an electrical definition fingerprint. Insertion also compares orientation axes against the requested rotation. Verification can be repeated without creation/reset. Failed or uncertain calls retain UUIDs; inspect them before retrying. Do not use creation in `vwx_batch`. Old server clients must explicitly follow `requires_verification` with the exact receipt.

`get_distributor_inspection(object_ids, detail="summary", limit=25)` accepts up to ten distributors or symbol definitions. It counts immediate electrical components and reports the symbol identity/fingerprint. Component detail includes raw settings, connector names, definition-local pose, geometry UUID, stored internal ID and identity issues. Fields over 512 characters are explicitly truncated in output; counts/fingerprint cover the full bounded scan. Limits: 4,096 immediate children, 512 components and 1 MB serialized data. Nested groups/symbols are not expanded. Component poses are not world coordinates.

Stored internal IDs/connection strings are a different representation from the SDK provider's paired runtime device/component identities. Missing internal IDs remain review items; the tool never invents replacements. Inserting a simulated native generator left its internal ID blank. This is retained in its creation receipt, not treated as verified connectivity or an automatic reason to reject geometry insertion.

## Native findings

- Correct PIO: `DistributorObject`. Physical components: `ElectricComponent_Generator`, `_Input`, `_Output`, `_Fuse`, `_Consumer`.
- The native distributor generated a symbol instance and label. Its `ICableConnectionsProvider` was unavailable; definition inspection is a separate read path, not proof of an empty electrical device or a replacement for runtime graph inspection.
- Official `Edison Twofer`: one input/two outputs. `100A Cube 001 Edison`: one input, 25 outputs, 12 fuses. These are observed library contents, not certified wiring or manufacturer ratings.
- `DSelectAll()` left selected objects on other layers. Collecting all `(SEL=TRUE)` handles, applying `SetDSelect` individually, then verifying the exact selected UUIDs allowed a scoped command attempt.
- Workspace XML confirms menu universal names `PowerPatchSel_Menu`, `PowerPatchPositoin_Menu` (native spelling), and `CablePreferencesMenu2`. `PowerPatchSelection` was not the registered menu name and returned with no observed field/cable change. A DoMenuTextByName return alone is not proof of native execution.

## Validation and recovery

`tests/live_distributors.py` used a fresh 279-tool installed server. Nine calls checked library component counts, three distributor insertions, post-event geometry/settings/pose, summary/detail agreement, wrong-document/duplicate rejection, repeated verification and saving. Evidence: `evidence/live-qa/live-distributors.json`. Its creation names already exist; do not rerun blindly.

The source symbol `VM-QA-SIMULATED-120V-15A-SOURCE` is explicitly artificial QA equipment. Two other new instances use official US library symbols. The final offline suite passed **97 tests**, including fourteen distributor tests. Three additional live calls in `tests/live_distributor_rotation.py` verified the final installed rotation guard on a new deliberately tilted QA instance (10/20/30 degrees), verified the earlier distributors unchanged, and saved QA. Twelve live calls cover the declared distributor scope. Final installed files match `evidence/deployment-20260912-110430/manifest.json`; native VLB/VWR did not change.

A separate native test Lighting Device was created on `QA Electrical Chain`. PowerPatchSel_Menu was invoked with only the simulated source and new twofer selected. It initially timed out (CID `14f45598d75c`, VW_DISPATCH_STUCK); after an Escape attempt, a later poll returned `done` with `native_command_returned=true`. The user subsequently reported the dialog said "successfully patched 0". Record this as zero newly patched devices, not a successful electrical connection; whether Escape dismissed the feedback is immaterial to the zero result. Before/after cable count remained 2 and both distributor parameter records were unchanged. This does not establish a successful patch or absence of a connection elsewhere in the native graph. Evidence: `evidence/live-qa/power-patch-returned.json`. The job is no longer pending; inspect native OIP/schematic state before any new patch attempt.

Capture still fails with `encode latest capture frame failed: window crop is outside captured monitor`; coordinate geometry also reported unavailable. User assistance to make the window accessible is pending. The API works again, and QA was saved after the final rotation test, fixture creation and returned patch attempt.

No private connection fields or production/source shows were edited. Visual OIP/schematic comparison, readable scaled documentation, actual connections, cable generation, following, stock parts, slack/swag, looms, suppliers and engineering calculations remain unverified for this chain.

Next: restore UI access and check reciprocal OIP/schematic connections and cable objects; prove source → distributor and distributor → fixture links; then add native path following and reconcile stocked parts/inventory before electrical calculations.

Primary references: [distributors](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Cables/Placing_distributors.htm), [power patching](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Cables/Power_patching_the_electrical_system.htm), [custom electrical devices](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Cables/Creating_custom_electrical_devices.htm).
