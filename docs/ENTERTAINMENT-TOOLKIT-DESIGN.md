# Entertainment control toolkit

Ongoing goal established by the user: **learn, verify, automate, and reuse**. Use vision and computer control wherever they help establish correct behavior, then convert repeated work into native MCP capabilities that reduce token use, UI actions, and round trips. Preserve native drafting semantics and visual/documentation quality. Keep concise results in the conversation and detailed evidence in files. The standing implementation guidance is recorded in `AGENTS.md`.

Requested by Michael after the Armory recreation, 12 September 2026. Extend the installed MCP rather than creating another control channel. Reusable tools run on Vectorworks' existing native mutation executor; screenshot/UI control remains useful for visual review and initial settings that the Python API cannot configure.

## Design

One focused Python workflow module supplies native inspection, document structure, fresh library import, parametric equipment creation, truss/hanging-position creation, lighting accessories/sources, worksheets and repeated worksheet images, title-block data, scaled viewports and annotations, and checked save/PDF export. Explicit MCP wrappers expose the workflows; the generic dispatcher remains available in an already-running Codex session.

Mutations require the expected full document path. All positions state their units and coordinate space. Existing objects/resources are not silently replaced. Batch inputs are validated before editing wherever possible; errors identify partial work. Native relationships are inspected, not inferred from the Position text field. The known crash-prone legacy attachment query is limited to Lighting Devices. Connected truss is never blindly reset.

Fix the existing dimension enum and viewport-class override signatures. Correct file transport so stale UI heartbeat during an already-claimed job is not reported as a closed bridge. Retain results for repeatable status reads and expose a job-status tool so an uncertain result never requires blindly resubmitting a mutation.

## Scope boundaries

Use native PIOs and symbol metadata; do not invent hardware ratings, supply names, power factors, DMX/GDTF modes, or cable designs. Existing linked title-block layouts and label legends can be reused; their first visual layout remains native authoring. PDF export reuses a once-configured native export destination and verifies the actual resulting file before copying to a requested destination. It must report a missing/mismatched configuration rather than claiming export success.

A C++ SDK extension could later expose additional native interfaces such as direct PDF options and title-block layout operations. Building a second UI automation layer would retain the same dialogs and timing problems, so the first implementation uses the proven Python APIs and the existing bridge.

## Validation

Offline regression tests cover transport claim/result races, validators, enum conversion, native API call contracts, worksheet image sharing and coordinate math. Live MCP tests run against a separate native drawing copy: repeated creation, native symbols/PIOs, accessories, sources, truss/position membership, worksheet counts/images, title-block data, viewport scale/dimensions, save/export. Test invalid requests and verify the original Armory deliverables remain unchanged. Record tool registration, live outcomes and any limitations in a deployment report.
