"""Typed MCP surface for the Velvet Mirror native workflow module."""
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field, StrictBool

Scalar = Union[str, int, float, bool]
Point3 = Tuple[float, float, float]
Point2 = Tuple[float, float]


class Spec(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class LayerSpec(Spec):
    name: str
    kind: Literal['design', 'sheet'] = 'design'
    scale: Optional[float] = None
    paper_size: Optional[Point2] = None


class NativeObject(Spec):
    name: str
    plugin: Literal['Lighting Device', 'Stage Deck', 'Stage Steps', 'Side Arm', 'LEDWall']
    layer: str
    class_name: str = Field(alias='class')
    position: Point3
    rotation: Point3 = (0, 0, 0)
    symbol: Optional[str] = None
    fields: Dict[str, Scalar] = Field(default_factory=dict)


class LightingDocumentationTarget(Spec):
    object_id: str = Field(min_length=1,max_length=128)
    expected_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')


class LightingDocumentationEdit(LightingDocumentationTarget):
    values: Dict[Literal['unit_number','channel','purpose','color'],str]


class CablePartSymbolSpec(Spec):
    template_symbol: str
    symbol_name: str
    fields: Dict[str, Scalar]
    text_replacements: Dict[str, str]
    metadata: Dict[str, str] = Field(default_factory=dict)


class CablePartAvailabilitySpec(Spec):
    object_id: str = Field(min_length=1, max_length=128)
    enabled: StrictBool
    expected_fingerprint: str = Field(pattern=r'^[0-9a-fA-F]{64}$')


class CableSectionEdit(Spec):
    index: int = Field(strict=True, ge=1, le=100)
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    start_slack_mm: Optional[float] = Field(default=None, strict=True, ge=0, le=10000000, allow_inf_nan=False)
    end_slack_mm: Optional[float] = Field(default=None, strict=True, ge=0, le=10000000, allow_inf_nan=False)
    swag_mm: Optional[float] = Field(default=None, strict=True, ge=0, le=10000000, allow_inf_nan=False)
    loom_id: Optional[str] = Field(default=None, strict=True, max_length=128)
    box_id: Optional[str] = Field(default=None, strict=True, max_length=128)
    tape: Optional[str] = Field(default=None, strict=True, max_length=128)


class CablePathSpec(Spec):
    name: str = Field(min_length=1, max_length=128)
    layer: str = Field(min_length=1, max_length=128)
    class_name: str = Field(alias='class', min_length=1, max_length=128)
    route_id: str = Field(min_length=1, max_length=128)
    vertices: List[Point3] = Field(min_length=2, max_length=200)
    location: str = Field(default='', max_length=512)


class DistributorSpec(Spec):
    name: str = Field(min_length=1, max_length=128)
    layer: str = Field(min_length=1, max_length=128)
    class_name: str = Field(alias='class', min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=128)
    device_id: str = Field(min_length=1, max_length=128)
    position: Point3
    rotation: Point3 = (0, 0, 0)
    description: Optional[str] = Field(default=None, max_length=512)
    location: str = Field(default='', max_length=512)


class Accessory(Spec):
    symbol: str
    position_mm: Point3
    rotation: Point3 = (0, 0, 0)


class SourceAssignment(Spec):
    object_id: str
    sources: Dict[Literal['Body Inventory', 'Lens Inventory', 'Accessory Inventory'], str]


class TrussMember(Spec):
    name: str
    symbol: str
    position: Point3
    rotation: Point3 = (0, 0, 0)


class LabelOffset(Spec):
    object_id: str
    label_index: int
    offset_mm: Point2


class WorksheetColumn(Spec):
    header: str
    formula: str
    width: int = 150


class SheetFields(Spec):
    sheet: str
    fields: Dict[str, Scalar]


class Annotation(Spec):
    name: str
    kind: Literal['text', 'dimension']
    position: Point2
    end: Optional[Point2] = None
    text: Optional[str] = None
    offset: float = 0
    direction: Literal['horizontal', 'vertical', 'aligned'] = 'aligned'
    font_size: float = 10


def rows(items):
    return [x.model_dump(by_alias=True, exclude_none=True) for x in items]


def parameters(values):
    # locals() includes the closed-over dispatcher; only arguments go over IPC.
    return {k: v for k, v in values.items() if k != 'cmd'}


def register(vtool, cmd):
    @vtool
    def get_sheet_paperwork_audit(sheets: List[str], limit: int = 25) -> str:
        """Read 1..10 sheet layers without switching sheets: viewport title/number/scale/view/update state, native title-block counts, and worksheet-image resource identities/scales. Detect duplicate drawing numbers within each sheet, missing titles/numbers, invalid scales and broken worksheet links. Show which images/sheets share one worksheet UUID. Scan ordinary groups, up to 10000 objects; limit 1..100 bounds detail, complete counts retained. No regeneration/recalculation. Does not validate final visibility, label layout, title-block linked data, inventory values, page fit or PDF scale; use existing viewport/label inspectors for detail."""
        return cmd('get_sheet_paperwork_audit',parameters(locals()))

    @vtool
    def get_gdtf_file(path: str, expected_sha256: Optional[str] = None) -> str:
        """Read a local .gdtf archive up to 100 MB without running Vectorworks: exact modes, FixtureTypeID, manufacturer/name metadata, hash, model/reference counts and declared DMX spans. Optional hash guard. Simple single-break footprint is withheld for geometry references or unresolved offsets/breaks. No extraction or authenticity/geometry certification."""
        return cmd('get_gdtf_file',parameters(locals()))

    @vtool
    def get_mvr_gdtf_audit(path: str, limit: int = 50) -> str:
        """Audit an existing MVR up to 100 MB: fixture UUID presence/uniqueness, referenced embedded GDTF files, and exact mode names within each. Reports complete issue counts and bounded details, up to 10000 fixtures/200 GDTFs. No extraction or file changes; no patch/transform or destination-application certification."""
        return cmd('get_mvr_gdtf_audit',parameters(locals()))

    @vtool
    def get_lighting_gdtf(object_ids: List[str]) -> str:
        """Read stored native GDTF file/mode/type/custom IDs, geometry setting, footprint and edit fingerprint for up to 25 single-cell Lighting Devices. Reports whether VMGDTFExchange is loaded. Field strings alone do not prove embedded file identity or MVR correctness."""
        return cmd('get_lighting_gdtf',{'object_ids':object_ids})

    @vtool
    def assign_gdtf_file(expected_document: str, object_id: str, expected_fingerprint: str, path: str,
                         expected_sha256: str, mode: str, use_gdtf_geometry: bool) -> str:
        """Native SDK GDTF import onto one unpatched single-cell Lighting Device. Requires loaded VMGDTFExchange extension, explicit file/hash, exact mode and geometry setting, plus fresh get_lighting_gdtf fingerprint. Initial scope accepts only resolved simple single-break GDTFs. Validates native mode/footprint and protected pose/rigging/hardware/patch in a separate event. No guessed modes or direct Type ID/footprint writes. Keep receipt after failure; no blind retry. Exported GDTF identity, visual geometry and MVR must be checked separately. Native extension remains staged until restart validation."""
        return cmd('assign_gdtf_file',parameters(locals()))

    @vtool
    def export_lighting_gdtf(expected_document: str, object_id: str, path: str) -> str:
        """Export one single-cell native Lighting Device's GDTF to an unused absolute .gdtf path using VMGDTFExchange; inspect resulting archive and verify source state. Native export can synthesize generic data: compare source hash/FixtureTypeID/mode before calling it manufacturer data. No overwrite. Requires native extension installation/restart."""
        return cmd('export_lighting_gdtf',parameters(locals()))

    @vtool
    def get_lighting_documentation(object_ids: List[str]) -> str:
        """Read up to 25 single-cell native Lighting Devices: Unit Number, Channel, Purpose, Color and worksheet source values, plus compact organization/attachment/accessory counts and a fresh edit fingerprint. Fingerprint covers scoped geometry, hardware, patch, modes and inventory. Schematic and multi-cell objects rejected. No edits."""
        return cmd('get_lighting_documentation',{'object_ids':object_ids})

    @vtool
    def set_lighting_documentation(expected_document: str, items: List[LightingDocumentationEdit], dry_run: bool = False) -> str:
        """Batch edit unit_number, channel, purpose and color on 1..25 single-cell native Lighting Devices. Fresh get_lighting_documentation fingerprints required; every item preflighted before mutation. Text values including empty clearing; channel is not DMX address. Native setters target parent cell, followed by separate-event readback checking worksheet fields and protected pose/layer/class/rigging/accessories/patch. dry_run previews changes without mutation. Success returns rollback_items with fresh fingerprints; failure retains detailed receipts, no automatic rollback/retry. Label layout, live worksheet recalculation and duplicates outside selection are separate."""
        return cmd('set_lighting_documentation',{'expected_document':expected_document,'items':rows(items),'dry_run':dry_run})

    @vtool
    def number_lighting_devices(expected_document: str, items: List[LightingDocumentationTarget],
                                field: Literal['unit_number','channel'] = 'unit_number', start: int = 1,
                                increment: int = 1, prefix: str = '', suffix: str = '', padding: int = 0,
                                dry_run: bool = False) -> str:
        """Number up to 25 single-cell fixtures in the supplied UUID order, using fresh fingerprints. Positive increment; optional prefix/suffix and zero padding. Writes native Unit Number or Channel through the same verified documentation workflow. Explicit order only: no spatial sorting, per-position restart or collision check against unselected devices. Channels may intentionally repeat across fixtures. dry_run previews the sequence. No DMX-address edits."""
        p=parameters(locals());p['items']=rows(items)
        return cmd('number_lighting_devices',p)

    @vtool
    def create_stage_deck_grid(expected_document: str, name: str, layer: str, class_name: str,
                               origin_mm: Point3, columns: int, rows: int, deck_size_mm: Point3,
                               rotation: float = 0, structure: Literal['Legs-Basic','Legs-Braced','Folding','Deck Only'] = 'Legs-Braced',
                               top_thickness_mm: float = 25.4, trim_height_mm: float = 152.4,
                               leg_size_mm: float = 76.2, leg_spacing_mm: float = 914.4,
                               leg_profile: Literal['Square','Octagonal','Round'] = 'Square',
                               rail_edges: Optional[List[Literal['front','back','left','right']]] = None,
                               rail_type: Literal['None','Straight','Box Open','Box Filled','Toe','Straight+Toe','Box Open+Toe','Box Filled+Toe'] = 'Straight',
                               rail_height_mm: float = 1066.8, vendor: str = '', brand: str = '', model: str = '',
                               location: str = '', dry_run: bool = False) -> str:
        """Build up to 25 new native rectangular Stage Decks. All lengths/positions in mm; deck_size_mm=(width,depth,height). origin_mm is first deck's native insertion point relative to the design layer, rotation in degrees. Columns advance local +X, rows +Y; front/back are first/last rows, left/right first/last columns. Rail edges apply only to the outside of the grid. Unique Rxx-Cxx object names and Unit IDs; existing names/IDs rejected. Explicit native legs, top, trim and rail settings, Vendor/Brand/Model metadata. Existing layer/class required; no private parameters, custom geometry or automatic shared-leg removal. dry_run preflights without creating resources. Native readback runs in a separate event; keep receipts on failure. Vendor text does not assign Equipment Summary inventory sources."""
        p=parameters(locals()); p['class']=p.pop('class_name'); p['rail_edges']=rail_edges or []
        if not location:p.pop('location')
        return cmd('create_stage_deck_grid',p)

    @vtool
    def get_stage_deck_inspection(object_ids: List[str]) -> str:
        """Read 1..25 native Stage Deck UUIDs: dimensions in mm, native calculated leg count/area, rails, Unit/Vendor/Brand/Model metadata, layer/class, layer-relative matrix and regeneration presence. No mutation. Does not certify manufacturer geometry, structural capacity or inventory-source assignment."""
        return cmd('get_stage_deck_inspection',{'object_ids':object_ids})

    @vtool
    def get_cable_length_audit(object_ids: List[str], tolerance_mm: float = 1.0) -> str:
        """Read-only length agreement check for 1..10 native cables. Compare Object Info Length, section lengths and linear path-local geometry in mm; flag stale/zero lengths and part-count disagreement. Length comparison is limited to one section, no breaks and zero vertical drop. Curves are not approximated. Reports mismatch/incomplete/consistent_in_scope; agreement never certifies world geometry, stock sufficiency, connections or electrical design. tolerance_mm must be finite 0..100."""
        return cmd('get_cable_length_audit', parameters(locals()))

    @vtool
    def get_cable_sections(object_ids: List[str]) -> str:
        """Read 1..10 native CableObjects using section APIs. Returns 1-based sections/breaks, ordered part labels, counts, millimetre dimensions, section loom_id/box_id/tape, and scoped geometry/endpoint/run-metadata fingerprints. Bounded at 100 sections, 100 breaks and 500 parts per cable. Rejects uninitialized cables or unavailable geometry. Metadata selectors verified in VW2026; no electrical suitability claim."""
        return cmd('get_cable_sections', parameters(locals()))

    @vtool
    def set_cable_sections(expected_document: str, object_id: str, expected_fingerprint: str, sections: List[CableSectionEdit]) -> str:
        """Edit 1..25 existing sections using native SetCableSectionData. Fields: name, start_slack_mm, end_slack_mm, swag_mm, loom_id, box_id, tape. Metadata edits require exactly one section and zero breaks; empty text clears metadata. Verify both section and synchronized run fields. Indices are 1-based; supply a fresh get_cable_sections fingerprint. All edits preflighted, lengths use explicit mm, and a separate native event verifies changes. Stock selection may change. No break insertion, connector edits, direct ordered-part assignment or engineering approval. Preserve receipts; never blindly retry."""
        return cmd('set_cable_sections', {'expected_document':expected_document,'object_id':object_id,
            'expected_fingerprint':expected_fingerprint,'sections':rows(sections)})

    @vtool
    def set_cable_part_availability(expected_document: str, items: List[CablePartAvailabilitySpec]) -> str:
        """Set native CablePart.Use on 1..25 symbol definitions in the expected current document. Supply each fingerprint from get_cable_part_symbols. Entire batch is preflighted; stale resources, wrong document and duplicates are rejected. Returns per-part receipts and checks other native fields/labels/house metadata are preserved. No external library/cache writes or cable rebuild. Reopen any cached configuration dialog and verify actual run consumption separately. Read affected UUIDs after a partial failure before retrying."""
        return cmd('set_cable_part_availability', {'expected_document':expected_document,'items':rows(items)})

    @vtool
    def export_cable_part_library(expected_document: str, path: str, object_ids: List[str], empty_library_sha256: Optional[str] = None) -> str:
        """Export up to 25 native CablePart definitions using compiled VMExportSymbolLibrary. Existing destinations require an explicit current SHA256 and zero symbols/record formats; close the destination first. Makes a verified backup before native export. VW2026 testing found that absent destinations were not created by the SDK: prepare a library from the native Blank template and supply its hash. Verifies exported resource names and unchanged source records/labels, not exported field persistence or catalog registration. Failure retains destination and backup for inspection; never overwrite/retry blindly."""
        return cmd('export_cable_part_library', parameters(locals()))

    @vtool
    def get_cable_part_symbols(object_ids: List[str]) -> str:
        """Read up to 25 native CablePart symbol definitions, raw fields, visible labels and house physical connector metadata. Supports the verified 12-field schema and flat line/text/polyline symbols. Length uses millimetres; other numeric units remain unverified. Does not reset resources or verify catalog registration, engineering specifications or geometric dimensions."""
        return cmd('get_cable_part_symbols', parameters(locals()))

    @vtool
    def create_cable_part_symbols(expected_document: str, items: List[CablePartSymbolSpec]) -> str:
        """Clone up to 25 existing native CablePart symbols under unique names. Preflight the entire batch; require all 12 native fields explicitly and a replacement for every visible template label. Numeric fields are raw native values, Length in millimetres. Optional physical end manufacturer/model/gender metadata stays separate from native connector families. Verifies records/labels and preserves source templates. Current drawing only: export, native refresh and run configuration are separate. Retains UUIDs on failure; do not recreate blindly."""
        return cmd('create_cable_part_symbols', {'expected_document':expected_document,'items':rows(items)})

    @vtool
    def get_cable_parts_catalog(cache_path: str, connector_catalog_path: Optional[str] = None,
                               search: str = '', symbols: Optional[List[str]] = None,
                               cable_set: Optional[str] = None, offset: int = 0, limit: int = 25,
                               include_fields: bool = False, expected_sha256: Optional[str] = None) -> str:
        """Search one absolute CablePartsCache.xml path without a running Vectorworks bridge. Pages 1..50 cached parts with symbol/source identity, enabled flag, set and raw length. Optional exact symbols (max25) and set filter; SHA256 guards paging. Optional connector XML checks exact universal names without guessing aliases, gender or electrical compatibility. include_fields exposes bounded raw properties. Preserves duplicate resources and disabled entries; reports unknown flags/invalid numbers. This is cached data, not current stock, resource existence or verified native availability. Never edits the cache."""
        return cmd('get_cable_parts_catalog', parameters(locals()))

    @vtool
    def get_distributor_inspection(object_ids: List[str], detail: Literal['summary','components'] = 'summary',
                                   limit: int = 25) -> str:
        """Read up to 10 native DistributorObject instances or symbol definitions. Counts immediate native electrical components and reads exact connectors, stored ratings, internal IDs and definition-local poses. Summary omits component details. Details are capped to 100 components, fields to 512 characters with explicit truncation. Reports missing/duplicate internal identities and a fingerprint of the electrical definition. Does not resolve runtime external connections, infer world component poses, calculate power, reset objects or expand nested symbol/group geometry."""
        return cmd('get_distributor_inspection', parameters(locals()))

    @vtool
    def create_distributors(expected_document: str, items: List[DistributorSpec]) -> str:
        """Insert up to 25 native distributors using existing library symbol definitions with identified immediate electrical components. Require existing design layers/classes, unique object names and device IDs. Coordinates are design-layer document units. Preserves library definitions; accepts no private connection fields. After regeneration, verifies pose, organization, settings, generated symbol reference and component fingerprint in a separate native event. Retains UUIDs on incomplete verification; never blindly repeat creation. This does not power patch, create cables or establish electrical connections. Do not place inside vwx_batch."""
        return cmd('create_distributors', {'expected_document':expected_document,'items':rows(items)})

    @vtool
    def get_electrical_components(object_ids: List[str], detail: Literal['summary','components'] = 'summary',
                                  include_internal_connections: bool = False, limit: int = 25) -> str:
        """Inspect up to 10 native parametric objects through the optional compiled electrical provider. Summary counts all components; components detail returns up to 100 per object in provider order. Optional internal links retain socket indices and device/component identities. Reports missing extension/provider separately from empty component arrays and failures. Does not create connections, prove physical wiring, sum circuit power or certify ratings. Native extension must be installed and loaded; Python-only installation reports unavailable."""
        return cmd('get_electrical_components', parameters(locals()))

    @vtool
    def get_cable_connector_catalog(search: str = '', names: Optional[List[str]] = None,
                                    include_sockets: bool = False, offset: int = 0, limit: int = 25,
                                    expected_sha256: Optional[str] = None, path: Optional[str] = None) -> str:
        """Inspect Vectorworks' installed CableConnectors.xml or one explicit absolute UTF-8 XML path. Search universal/display names or look up up to 25 exact universal names; unknown names are explicit. Pages 1..50 connectors with source SHA-256 (optionally guard later pages). include_sockets preserves ordered socket indices and repeated labels. Shows directional ConnectableWith declarations and whether reciprocated in this file. Does not infer actual pin wiring, electrical compatibility, user/workgroup precedence or live connections; makes no edits."""
        return cmd('get_cable_connector_catalog', parameters(locals()))

    @vtool
    def get_cable_inspection(object_ids: List[str], include_fields: bool = False, issue_limit: int = 50,
                             geometry_detail: Literal['none','summary','points'] = 'none', geometry_point_limit: int = 500,
                             include_connector_configuration: bool = False) -> str:
        """Read up to 50 modern CableObject/CablePathObject UUIDs: IDs, run looms, native lengths, endpoint references and parts presence. include_fields adds bounded fields; issue_limit 1..100 caps review rows. Optional geometry summary (max 10 objects) reads NURBS data and returns a fingerprint, separate origin/angles, and local length/endpoints only for continuous corner paths; points adds controls, weights and knots. geometry_point_limit 2..2000 bounds reads per object (default 500); over-limit geometry is explicitly unavailable. Fingerprint is not a full affine/world geometry or connection check. include_connector_configuration (max 10 objects) compares both endpoint families and cable type with their style ownership, and reads separate adapter/inventory fields; style mismatch does not infer wiring or physical gender. No section looms, pin mapping, following, inventory completeness or engineering verification. No edits."""
        return cmd('get_cable_inspection', parameters(locals()))

    @vtool
    def create_cable_paths(expected_document: str, items: List[CablePathSpec]) -> str:
        """Create up to 25 independent native cable paths. Each item requires unique name, existing design layer/class, unique route_id and 2..200 corner vertices [x,y,z] in design-layer document units; optional location. Uses NURBS internally and automatically verifies every vertex, transform, class/ID and native length after host regeneration. No network joins or cable/equipment connections. Do not wrap in vwx_batch; on incomplete verification retain receipts and never recreate blindly."""
        return cmd('create_cable_paths', {'expected_document': expected_document, 'items': rows(items)})

    @vtool
    def get_viewport_documentation(viewport_ids: List[str], include_labels: bool = False, limit: int = 50) -> str:
        """Inspect title/number/view/scale and Drawing Label or Drawing Label2 objects in up to 10 viewport annotation groups. Reports mismatched metadata, exact conventional title/view disagreements and modern custom-scale text for review. Summary by default; include_labels returns actual fields, missing fields and style names, bounded by limit (1..100). Does not edit, infer arbitrary titles, enter symbol/PIO internals, or certify rendered labels/physical scale."""
        return cmd('get_viewport_documentation', parameters(locals()))

    @vtool
    def get_viewport_display(viewport_ids: List[str], detail: Literal['summary','visibility'] = 'summary',
                             class_names: Optional[List[str]] = None, layer_names: Optional[List[str]] = None,
                             offset: int = 0, limit: int = 50) -> str:
        """Read stored layer/class visibility, scale, crop presence and override counts for up to 10 viewports. Summary counts cover selected names or all document classes/design layers. visibility pages each alphabetic list (max 200/page). Distinguishes viewport and document visibility. Optional native extension adds actual style/data-visualization context; absent extension is explicitly unknown. Does not prove final object visibility, PDF readability or physical scale. No edits."""
        return cmd('get_viewport_display', parameters(locals()))

    @vtool
    def get_data_sheet_inspection(mapping_name: str, data_sheet: str = '',
                                  object_ids: Optional[List[str]] = None,
                                  field_offset: int = 0, field_limit: int = 25) -> str:
        """Read native Data Manager/OIP data sheets. Omit data_sheet to list up to 100 names for an exact mapping name (for example Lighting Device). Specify a sheet to page its field definitions; optionally read those labels on up to 10 object UUIDs. Max 50 fields/page, 512 characters/value. Returns visibility, formula flags, raw operation status, value source and explicit errors. Caller-selected mapping applicability and source correctness are not certified. No edits or inference of editable status."""
        p = parameters(locals())
        p['object_ids'] = object_ids or []
        return cmd('get_data_sheet_inspection', p)

    @vtool
    def get_entertainment_state(criteria: str = "(PON='Lighting Device')", limit: int = 50,
                                detail: Literal['summary','devices','full'] = 'summary', offset: int = 0,
                                include_structure: Optional[bool] = None) -> str:
        """Concise live summary by default: native counts, actual attachment counts and inventory grouped by symbol/body/lens/accessory source. detail=devices gives UUID-sorted compact pages; full adds matrices/accessory poses. Summary covers all matches regardless of page size. include_structure defaults true only for full. No frozen snapshot or cached model data."""
        p=parameters(locals())
        if include_structure is None:p.pop('include_structure')
        return cmd('get_entertainment_state', p)

    @vtool
    def get_native_schema(object_id: str) -> str:
        """Read actual installed native parameter names/types and values by UUID, including native LD metadata and attachments."""
        return cmd('get_native_schema', {'object_id': object_id})

    @vtool
    def get_lighting_patch_audit(criteria: str = "(PON='Lighting Device')", limit: int = 50,
                                 include_parts: bool = False) -> str:
        """Read-only DMX audit across matched native LD cells and accessories. Checks recorded single-break footprints, unpatched parts, 512-slot overflow, same-system/universe overlaps and identical patches for review. Bounded issue output, complete counts up to 2000 parts. Does not certify modes, multi-break GDTF, universe configuration or unmatched devices; no automatic fixes."""
        return cmd('get_lighting_patch_audit', parameters(locals()))

    @vtool
    def get_bridge_job_status(cid: str) -> str:
        """Recover an uncertain file-bridge call by correlation ID without rerunning it. Completed results remain readable until TTL expiry."""
        return cmd('get_bridge_job_status', {'cid': cid})

    @vtool
    def ensure_drawing_structure(expected_document: str, layers: List[LayerSpec], classes: List[str]) -> str:
        """Create missing layers/classes. Full active VWX path guards edits; existing layer type/scale conflicts are errors, not silent changes."""
        return cmd('ensure_drawing_structure', {'expected_document': expected_document, 'layers': rows(layers), 'classes': classes})

    @vtool
    def list_native_library_resources(path: str, resource_type: int = 16, filter: str = '', limit: int = 100) -> str:
        """Browse a local VWX library by name without Resource Manager clicks or importing content.16=symbol/style,47=record. Returns existence flags and explicit truncation."""
        return cmd('list_native_library_resources', parameters(locals()))

    @vtool
    def import_native_resources(expected_document: str, path: str, names: List[str], resource_type: int = 16) -> str:
        """Import exact resource names from a local VWX library in one native event.16=symbol/style,47=record. Existing names are never overwritten."""
        return cmd('import_native_resources', parameters(locals()))

    @vtool
    def create_native_objects(expected_document: str, items: List[NativeObject]) -> str:
        """Create up to25 native Lighting Devices, decks, steps, side arms or LED walls. XYZ in design-layer document units (layer elevation is separate); rotations in degrees. Use installed field names from get_native_schema. Existing names rejected."""
        return cmd('create_native_objects', {'expected_document': expected_document, 'items': rows(items)})

    @vtool
    def set_lighting_accessories(expected_document: str, device_ids: List[str], accessories: List[Accessory]) -> str:
        """Ensure cell-0 native accessories and positions in MILLIMETRES. Reuses one matching accessory per symbol; rejects ambiguity. Verifies parent pose and actual HP link."""
        return cmd('set_lighting_accessories', {'expected_document': expected_document, 'device_ids': device_ids, 'accessories': rows(accessories)})

    @vtool
    def set_lighting_sources(expected_document: str, assignments: List[SourceAssignment]) -> str:
        """Set exact native body/lens/accessory inventory identifiers independently. Caller supplies real catalog names; no inventory XML editing or stock inference."""
        return cmd('set_lighting_sources', {'expected_document': expected_document, 'assignments': rows(assignments)})

    @vtool
    def create_truss_position(expected_document: str, name: str, position_name: str, layer: str, class_name: str,
                              position: Point3, members: List[TrussMember], rotation: Point3 = (0,0,0)) -> str:
        """Create native HP and new TrussItems from library BrxTrussItemRecord. Member XYZ is local to HP; HP XYZ is design-layer/document units. Does not synthesize inter-member snap connections or capacities."""
        return cmd('create_truss_position', {'expected_document': expected_document, 'name': name, 'position_name': position_name,
                   'layer': layer, 'class': class_name, 'position': position, 'members': rows(members), 'rotation': rotation})

    @vtool
    def attach_loads_to_position(expected_document: str, position_id: str, expected_device_ids: List[str]) -> str:
        """Run native auto-attachment for the WHOLE Hanging Position. Report all changed LD links/movements and verify expected LDs attached. Position text alone never proves attachment."""
        return cmd('attach_loads_to_position', parameters(locals()))

    @vtool
    def set_fixture_label_layout(expected_document: str, legend: str, devices: List[LabelOffset]) -> str:
        """Reuse a native 2D-layout legend and set existing label-handle offsets in mm. Requires a configured handle index; preserves device transforms and HP links."""
        return cmd('set_fixture_label_layout', {'expected_document': expected_document, 'legend': legend, 'devices': rows(devices)})

    @vtool
    def upsert_database_worksheet(expected_document: str, name: str, criteria: str, columns: List[WorksheetColumn],
                                  font_size: int = 10, update: bool = False) -> str:
        """Create/update a formatted two-row native database worksheet. Preserves resource identity; reports real subrow count and formula errors after recalculation."""
        return cmd('upsert_database_worksheet', {'expected_document': expected_document, 'name': name, 'criteria': criteria,
                   'columns': rows(columns), 'font_size': font_size, 'update': update})

    @vtool
    def place_shared_worksheet(expected_document: str, worksheet: str, sheet: str, name: str, position: Point2) -> str:
        """Place a named worksheet image at paper-space top-left, sharing ONE worksheet resource across sheets. Existing image returns its UUID without duplicating."""
        return cmd('place_shared_worksheet', parameters(locals()))

    @vtool
    def update_title_block_data(expected_document: str, project: Dict[str, Scalar], sheets: List[SheetFields]) -> str:
        """Update already-linked native title blocks. Shared project fields reach ALL borders before any reset, avoiding data loss. Does not create linked text layouts."""
        return cmd('update_title_block_data', {'expected_document': expected_document, 'project': project, 'sheets': rows(sheets)})

    @vtool
    def create_sheet_viewport(expected_document: str, sheet: str, name: str, scale: float, bounds: Tuple[float,float,float,float],
                               center: Point2, layers: List[str], hidden_classes: List[str],
                               view: Literal['plan','front','isometric'] = 'plan', hidden_line: bool = False,
                               include_helper_geometry: bool = False) -> str:
        """Create native scaled/cropped viewport. Bounds:left,top,right,bottom in view-plane model units; center in paper units. Helper/snapping/input classes hidden by default. Returns annotation offset for annotate_viewport."""
        return cmd('create_sheet_viewport', parameters(locals()))

    @vtool
    def annotate_viewport(expected_document: str, viewport_id: str, annotation_offset: Point2, items: List[Annotation]) -> str:
        """Add native dimensions/text to VP annotations. Points are model coordinates projected into the view plane; use offset returned by create_sheet_viewport. Font sizes are printed points."""
        return cmd('annotate_viewport', {'expected_document': expected_document, 'viewport_id': viewport_id,
                   'annotation_offset': annotation_offset, 'items': rows(items)})

    @vtool
    def save_document_checked(expected_document: str) -> str:
        """Native save with full-document-path guard, checked native return code and actual saved file size/time."""
        return cmd('save_document_checked', parameters(locals()))

    @vtool
    def export_sheet_set_checked(expected_document: str, sheets: List[str], configured_output: str, destination: str, configure: bool = False) -> str:
        """Export ordered sheets using existing native PDF settings. configure=true opens initial native settings/save dialogs; select configured_output there. Reuse is click-free. Verify changed actual PDF before copying to destination; still visually review scale/content."""
        return cmd('export_sheet_set_checked', parameters(locals()))
