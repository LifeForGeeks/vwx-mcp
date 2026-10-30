# Cable start and end configuration

Version 0.13.1 extends `get_cable_inspection` with `include_connector_configuration=True` for up to ten objects. Default output is unchanged. For native CableObjects it reads:

- Cable type, start family (`StartConector`, native spelling) and end family.
- Each parameter's style ownership and corresponding style-definition value. Only an exact, untruncated by-style comparison is reported as matching or mismatching.
- Separate start/end adapter and connector/adapter inventory fields.

Missing/ambiguous styles produce an explicit unavailable result. Style traversal is bounded at 256 immediate children and 512 parameters. Strings are capped at 512 characters. The reader never changes styles, connector choices, endpoints, stock or geometry. Matching family names do not verify physical gender, pins, compatibility, adapters or actual device connections.

The official TRUE1 style stores `NAC3FX-W and NAC3MX-W` at both ends. Physical male/female identities remain separate `VM Cable Part Detail` metadata on custom part symbols; no invented connector aliases are introduced. Both endpoints and CableType are by-style in the inspected native references. The source TRUE1 style also reports UsedParts as by-style, whereas UsedPartsOrdered and Length are by-instance. This is a relevant observation for the stale Harting raw-UsedParts report, not a complete causal proof.

## Verified behavior

Seven offline tests cover independent end mismatches, by-instance differences, missing/ambiguous resources, absent/truncated values and limits. All 163 toolkit tests pass. Five fresh installed calls compare default/detail output, validate three cable configurations, cross-check a custom part, and confirm unchanged returned section snapshots. The detail adds 3,289 JSON bytes for those three objects. A test-harness typo (`Short Name` instead of native `ShortName`) was corrected; the first read-only evidence is retained separately.

The isolated cable `944ec808-fb71-48df-bd4c-5484b4ae964c` has a 1,219.2 mm path, 150 mm slack at each end and no swag. Its private QA style has NEMA 5-15 at the start and TRUE1 at the end. The native stock engine selects custom part `QA-E-T1-5`, whose recorded length is 1,524 mm, covering the 1,519.2 mm requirement. Both connector values match the custom CablePart record and its style. This verifies asymmetric native stock selection, not the separate Adapter Start/End mechanism or complete cable initialization: stored Length is still zero and endpoint references are blank.

Evidence: `evidence/live-qa/cable-connector-configuration-installed.json`, `custom-adapter-consumption-probe.json`, `cable-connectors-0131-final.json`. QA is saved. Python deployment: `evidence/deployment-20260913-193155/manifest.json`; native binaries were not replaced by this deployment.

Reference: [Vectorworks cable settings and configuration](https://app-help.vectorworks.net/2026/eng/VW2026_Guide/Cables/Editing_cables.htm). SDK style-mode constants are in `MiniCadCallBacks.h`; native mode 0 is by-instance, 1 by-style, 2 always by-instance.
