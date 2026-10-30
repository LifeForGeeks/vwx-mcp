import math
import unittest
import test_cables
from test_entertainment import e, vs


class CableGeometryTests(unittest.TestCase):
    setUp = test_cables.CableTests.setUp
    invoke = test_cables.CableTests.invoke
    setup_inspector = test_cables.CableTests.setup_inspector
    def setup_geometry(self):
        self.setup_inspector()
        vs.GetTypeN.side_effect = lambda h: 111 if h.endswith('-geo') else 86
        vs.NurbsCurveGetNumPieces.return_value = 2
        vs.NurbsDegree.return_value = 1
        vs.NurbsGetNumPts.return_value = 2
        vs.NurbsGetWeight.return_value = 1.0
        vs.NurbsNumKnots.return_value = 4
        vs.NurbsKnot.side_effect = lambda h,s,i: [0,0,1,1][i]
        self.points = [[(0, 0, 0), (120, 0, 0)], [(120, 0, 0), (120, 0, 120)]]
        vs.NurbsGetPt3D.side_effect = lambda h,s,i: self.points[s][i]
        vs.GetEntityMatrix.return_value = (True, (240, 0, 24), 10, 20, 30)

    def inspect_geometry(self, **kwargs):
        return self.invoke('get_cable_inspection', object_ids=['run'], geometry_detail='summary', **kwargs)

    def test_default_does_not_read_geometry(self):
        self.setup_geometry()
        row = self.invoke('get_cable_inspection', object_ids=['run'])['objects'][0]
        self.assertNotIn('geometry', row)
        vs.NurbsCurveGetNumPieces.assert_not_called()

    def test_summary_has_local_endpoints_and_separate_transform(self):
        self.setup_geometry()
        row = self.inspect_geometry()['objects'][0]['geometry']
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['linear_length_local'], 240)
        self.assertEqual(row['endpoints_local'], [[0,0,0], [120,0,120]])
        self.assertEqual(row['object_transform']['origin_parent'], [240,0,24])
        self.assertEqual(row['object_transform']['rotation_degrees'], [10,20,30])
        self.assertFalse(row['world_coordinates_verified'])
        self.assertNotIn('pieces', row)
        self.assertEqual(len(row['sha256']), 64)
        vs.ResetObject.assert_not_called(); vs.SetRField.assert_not_called()

    def test_points_and_summary_share_fingerprint_and_changes_are_detected(self):
        self.setup_geometry()
        before = self.inspect_geometry()['objects'][0]['geometry']['sha256']
        row = self.invoke('get_cable_inspection', object_ids=['run'], geometry_detail='points')['objects'][0]['geometry']
        self.assertEqual(before, row['sha256'])
        self.assertEqual(row['pieces'][1]['control_points_local'], [[120,0,0],[120,0,120]])
        vs.GetEntityMatrix.return_value = (True, (360, 0, 24), 10, 20, 30)
        moved = self.inspect_geometry()['objects'][0]['geometry']['sha256']
        self.assertNotEqual(before, moved)
        self.points[1][1] = (120,0,130)
        self.assertNotEqual(moved, self.inspect_geometry()['objects'][0]['geometry']['sha256'])

    def test_curves_do_not_report_control_polygon_as_route_length_or_endpoints(self):
        self.setup_geometry()
        vs.NurbsDegree.return_value = 2
        vs.NurbsGetNumPts.return_value = 3
        vs.NurbsNumKnots.return_value = 6
        vs.NurbsKnot.side_effect = lambda h,s,i: [0,0,0,1,1,1][i]
        self.points = [[(0,0,0),(60,30,0),(120,0,0)]] * 2
        row = self.inspect_geometry()['objects'][0]['geometry']
        self.assertEqual(row['status'], 'ok')
        self.assertIsNone(row['linear_length_local'])
        self.assertIsNone(row['endpoints_local'])
        self.assertFalse(row['corner_polyline'])

    def test_geometry_limits_fail_explicitly_before_point_reads(self):
        self.setup_geometry()
        row = self.inspect_geometry(geometry_point_limit=3)['objects'][0]['geometry']
        self.assertEqual(row['status'], 'unavailable')
        self.assertNotIn('sha256', row)
        vs.NurbsGetPt3D.assert_not_called()

    def test_bad_native_geometry_does_not_hide_valid_record_data(self):
        self.setup_geometry()
        for value in [(math.nan,0,0), (1,2), (math.inf,0,0)]:
            self.points[0][0] = value
            result = self.inspect_geometry()
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['objects'][0]['loom_id'], 'L1')
            self.assertEqual(result['objects'][0]['geometry']['status'], 'unavailable')
            self.assertIn('geometry_unavailable', result['issue_counts'])

    def test_disjoint_pieces_are_not_a_continuous_corner_path(self):
        self.setup_geometry()
        self.points[1][0] = (121,0,0)
        row = self.inspect_geometry()['objects'][0]['geometry']
        self.assertFalse(row['corner_polyline'])
        self.assertIsNone(row['linear_length_local'])
        self.assertIsNone(row['endpoints_local'])

    def test_geometry_options_rejected_before_native_reads(self):
        self.setup_geometry()
        for bad in [{'geometry_detail': 'full'}, {'geometry_point_limit': True},
                    {'geometry_point_limit': 2001}, {'geometry_point_limit': 1}]:
            result = self.invoke('get_cable_inspection', object_ids=['run'], **bad)
            self.assertEqual(result['status'], 'error')
        vs.GetObjectByUuid.assert_not_called()

    def test_weights_and_knots_are_in_snapshot_and_fingerprint(self):
        self.setup_geometry()
        before = self.inspect_geometry()['objects'][0]['geometry']['sha256']
        vs.NurbsGetWeight.return_value = 2.0
        after = self.inspect_geometry()['objects'][0]['geometry']['sha256']
        self.assertNotEqual(before, after)
        vs.NurbsKnot.side_effect = lambda h,s,i: [0,0,2,2][i]
        self.assertNotEqual(after, self.inspect_geometry()['objects'][0]['geometry']['sha256'])
        vs.NurbsGetWeight.return_value = -1.0
        row = self.inspect_geometry()['objects'][0]['geometry']
        self.assertFalse(row['corner_polyline'])
        self.assertIsNone(row['linear_length_local'])
