"""
Unit tests for node_types.py:
- GenericHubitatNode dynamic instantiation & configuration
- Legacy node classes backward compatibility
- Address and Name sanitization
- Command execution and URI building
"""
import unittest
from tests.test_helpers import MockPolyglot, MockRequests, MockResponse
import node_types


class TestNodeTypes(unittest.TestCase):
    def setUp(self):
        self.poly = MockPolyglot()

    def test_address_sanitization(self):
        node = node_types.GenericHubitatNode(
            self.poly, 'ctrl', 'Device_123!@#$', 'My Device', 'http://hub/all?token=x'
        )
        self.assertEqual(node.getValidAddress('Device_123!@#$'), 'device123')
        self.assertEqual(node.getValidAddress('very_long_address_exceeding_14_chars'), 'verylongaddres')

    def test_name_sanitization(self):
        node = node_types.GenericHubitatNode(
            self.poly, 'ctrl', 'dev1', 'Living Room Light #2!', 'http://hub/all?token=x'
        )
        self.assertEqual(node.getValidName('Living Room Light #2!'), 'Living Room Light 2')

    def test_generic_hubitat_node_dynamic_configuration(self):
        drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Status'},
            {'driver': 'OL', 'value': 50, 'uom': 51, 'name': 'On Level'}
        ]
        cmd_map = {'DON': 'on', 'DOF': 'off', 'SETLVL': 'setLevel'}
        node = node_types.GenericHubitatNode(
            self.poly, 'ctrl', '123', 'Dimmer 1',
            'http://192.168.1.10/apps/api/1/devices/all?access_token=abc',
            node_def_id='ND_SW_LVL',
            drivers=drivers,
            command_map=cmd_map
        )

        self.assertEqual(node.id, 'ND_SW_LVL')
        self.assertEqual(len(node.drivers), 2)
        self.assertEqual(node.command_map['DON'], 'on')
        self.assertEqual(node.command_map['SETLVL'], 'setLevel')

    def test_command_uri_building_and_dispatch(self):
        mock_req = MockRequests(MockResponse(status_code=200))
        orig_requests = node_types.requests
        node_types.requests = mock_req

        try:
            drivers = [{'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Status'}]
            cmd_map = {'DON': 'on', 'DOF': 'off', 'SETLVL': 'setLevel'}
            node = node_types.GenericHubitatNode(
                self.poly, 'ctrl', '274', 'Bed Bulb',
                'http://192.168.1.50/apps/api/12/devices/all?access_token=secret',
                node_def_id='ND_SW_LVL',
                drivers=drivers,
                command_map=cmd_map
            )

            # Test DON
            node.cmd_on()
            self.assertEqual(len(mock_req.calls), 1)
            self.assertEqual(
                mock_req.calls[0]['url'],
                'http://192.168.1.50/apps/api/12/devices/274/on?access_token=secret'
            )

            # Test DOF
            node.cmd_off()
            self.assertEqual(len(mock_req.calls), 2)
            self.assertEqual(
                mock_req.calls[1]['url'],
                'http://192.168.1.50/apps/api/12/devices/274/off?access_token=secret'
            )

            # Test SETLVL with value
            node.cmd_set_level({'value': 75})
            self.assertEqual(len(mock_req.calls), 3)
            self.assertEqual(
                mock_req.calls[2]['url'],
                'http://192.168.1.50/apps/api/12/devices/274/setLevel/75?access_token=secret'
            )

            # Test QUERY
            node.cmd_query()
            self.assertEqual(len(mock_req.calls), 4)
            self.assertEqual(
                mock_req.calls[3]['url'],
                'http://192.168.1.50/apps/api/12/devices/274/refresh?access_token=secret'
            )

        finally:
            node_types.requests = orig_requests

    def test_legacy_node_classes_compatibility(self):
        legacy_classes = [
            node_types.StdLampNode,
            node_types.RgbLampNode,
            node_types.CtLampNode,
            node_types.EnergyOutletNode,
            node_types.OutletNode,
            node_types.SwitchNode,
            node_types.DimmerNode,
            node_types.MotionSensor,
            node_types.ContactNode,
            node_types.THSensor,
            node_types.LutronPicoNode,
            node_types.EcobeeSensor,
            node_types.EcobeeThermostat,
            node_types.MultiSensorTHLA,
        ]

        for cls in legacy_classes:
            node = cls(self.poly, 'ctrl', '10', 'Test Device', 'http://hub/all?token=x')
            self.assertIsNotNone(node.id)
            self.assertIsInstance(node.drivers, list)
            for d in node.drivers:
                self.assertIn('driver', d)
                self.assertIn('name', d)
                self.assertIn('uom', d)

    def test_airthings_node_id_temp_units(self):
        c_node = node_types.AirThingsSensor(
            self.poly, 'ctrl', '101', 'Wave C', 'http://hub/all?token=x',
            dev={'temp_unit': 'C'}
        )
        self.assertEqual(c_node.id, 'AIRTHSENSOR')

        f_node = node_types.AirThingsSensor(
            self.poly, 'ctrl', '102', 'Wave F', 'http://hub/all?token=x',
            dev={'temp_unit': 'F'}
        )
        self.assertEqual(f_node.id, 'AIRTHSENSORF')


if __name__ == '__main__':
    unittest.main()
