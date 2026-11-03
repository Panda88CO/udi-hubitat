"""
Unit tests for node_types.py:
- Node definitions, drivers, and attributes
- Driver names cross-check against profile/nls/en_us.txt
- Address and Name sanitization
- Command handlers and URI building
"""
import os
import unittest
import xml.etree.ElementTree as ET
from tests.test_helpers import PROJECT_ROOT, MockPolyglot, MockRequests, MockResponse
import node_types


class TestNodeTypes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load NLS mapping
        nls_path = os.path.join(PROJECT_ROOT, 'profile', 'nls', 'en_us.txt')
        cls.nls_map = {}
        with open(nls_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    cls.nls_map[k] = v

        # Load nodedefs mapping: nodeDef id -> nls id
        nodedefs_path = os.path.join(PROJECT_ROOT, 'profile', 'nodedef', 'nodedefs.xml')
        tree = ET.parse(nodedefs_path)
        cls.nodedef_nls = {
            nd.attrib['id']: nd.attrib['nls']
            for nd in tree.getroot().findall('nodeDef')
        }

    def setUp(self):
        self.poly = MockPolyglot()

    def test_address_sanitization(self):
        base = node_types.HubitatBase(self.poly, 'ctrl', 'Device_123!@#$', 'My Device', 'http://hub/all?token=x')
        self.assertEqual(base.getValidAddress('Device_123!@#$'), 'device_123')
        self.assertEqual(base.getValidAddress('very_long_address_exceeding_14_chars'), 'very_long_addr')

    def test_name_sanitization(self):
        base = node_types.HubitatBase(self.poly, 'ctrl', 'dev1', 'Living Room Light #2!', 'http://hub/all?token=x')
        self.assertEqual(base.getValidName('Living Room Light #2!'), 'Living Room Light 2')

    def test_all_node_classes_have_required_attributes(self):
        node_classes = [
            node_types.StdLampNode,
            node_types.RgbLampNode,
            node_types.CtLampNode,
            node_types.EnergyOutletNode,
            node_types.OutletNode,
            node_types.SwitchNode,
            node_types.DimmerNode,
            node_types.MultiSensorTHLA,
            node_types.MultiSensorTLAS,
            node_types.MultiSensorTH,
            node_types.MultiSensorT,
            node_types.MultiSensorTL,
            node_types.MultiSensorL,
            node_types.MotionSensor,
            node_types.LutronPicoNode,
            node_types.LutronFastPicoNode,
            node_types.THSensor,
            node_types.ContactNode,
            node_types.SimpleRemoteNode,
            node_types.EcobeeSensor,
            node_types.AirThingsSensor,
            node_types.EcobeeThermostat,
        ]

        for cls in node_classes:
            self.assertTrue(hasattr(cls, 'id'), f"{cls.__name__} missing 'id' attribute")
            self.assertTrue(hasattr(cls, 'drivers'), f"{cls.__name__} missing 'drivers' attribute")
            self.assertTrue(hasattr(cls, 'commands'), f"{cls.__name__} missing 'commands' attribute")
            self.assertEqual(cls.id, cls.id.upper(), f"{cls.__name__} id '{cls.id}' must be uppercase")

            # Verify driver dictionary structure and NLS alignment
            nls_id = self.nodedef_nls.get(cls.id)
            self.assertIsNotNone(nls_id, f"NodeDef ID '{cls.id}' for {cls.__name__} not found in nodedefs.xml")

            for driver_dict in cls.drivers:
                self.assertIn('driver', driver_dict, f"Driver in {cls.__name__} missing 'driver' key")
                self.assertIn('value', driver_dict, f"Driver in {cls.__name__} missing 'value' key")
                self.assertIn('uom', driver_dict, f"Driver in {cls.__name__} missing 'uom' key")
                self.assertIn('name', driver_dict, f"Driver in {cls.__name__} missing 'name' key")

                # Cross-check name matches NLS
                driver_key = driver_dict['driver']
                nls_key = f"ST-{nls_id}-{driver_key}-NAME"
                expected_name = self.nls_map.get(nls_key)
                self.assertEqual(
                    driver_dict['name'],
                    expected_name,
                    f"{cls.__name__} driver '{driver_key}' name '{driver_dict['name']}' != NLS '{expected_name}'"
                )

    def test_uri_building(self):
        base = node_types.HubitatBase(self.poly, 'ctrl', '12', 'Test', 'http://192.168.1.50/apps/api/10/devices/all?access_token=secret')
        uri_on = base._build_uri('12', 'on')
        self.assertEqual(uri_on, 'http://192.168.1.50/apps/api/10/devices/12/on?access_token=secret')

        uri_level = base._build_uri('12', 'setLevel', 75)
        self.assertEqual(uri_level, 'http://192.168.1.50/apps/api/10/devices/12/setLevel/75?access_token=secret')

        # Without query string
        base_no_query = node_types.HubitatBase(self.poly, 'ctrl', '12', 'Test', 'http://192.168.1.50/devices/all')
        self.assertEqual(base_no_query._build_uri('12', 'off'), 'http://192.168.1.50/devices/12/off')

    def test_hubitat_ctl_command_dispatch_and_requests(self):
        mock_req = MockRequests()
        orig_requests = node_types.requests
        node_types.requests = mock_req
        try:
            lamp = node_types.RgbLampNode(self.poly, 'ctrl', '45', 'Living Lamp', 'http://hub/all?token=abc')
            mock_req.calls.clear()

            # Test DON
            lamp.hubitatCtl({'cmd': 'DON'})
            self.assertEqual(len(mock_req.calls), 1)
            self.assertIn('/45/on?token=abc', mock_req.calls[0]['url'])

            # Test DOF
            mock_req.calls.clear()
            lamp.hubitatCtl({'cmd': 'DOF'})
            self.assertEqual(len(mock_req.calls), 1)
            self.assertIn('/45/off?token=abc', mock_req.calls[0]['url'])

            # Test SETLVL
            mock_req.calls.clear()
            lamp.hubitatCtl({'cmd': 'SETLVL', 'value': 80})
            self.assertEqual(len(mock_req.calls), 1)
            self.assertIn('/45/setLevel/80?token=abc', mock_req.calls[0]['url'])

            # Test SETHUE and alias SET_HUE
            mock_req.calls.clear()
            lamp.hubitatCtl({'cmd': 'SETHUE', 'value': 50})
            self.assertIn('/45/setHue/50?token=abc', mock_req.calls[0]['url'])

            mock_req.calls.clear()
            lamp.hubitatCtl({'cmd': 'SET_HUE', 'value': 50})
            self.assertIn('/45/setHue/50?token=abc', mock_req.calls[0]['url'])

            # Test SETSAT / SET_SAT
            mock_req.calls.clear()
            lamp.hubitatCtl({'cmd': 'SETSAT', 'value': 70})
            self.assertIn('/45/setSaturation/70?token=abc', mock_req.calls[0]['url'])

            # Test SETKELVIN / SET_KELVIN
            mock_req.calls.clear()
            lamp.hubitatCtl({'cmd': 'SETKELVIN', 'value': 3000})
            self.assertIn('/45/setColorTemperature/3000?token=abc', mock_req.calls[0]['url'])

            # Test Button commands PUSHBTN, HOLDBTN, RELEASEBTN
            remote = node_types.SimpleRemoteNode(self.poly, 'ctrl', '99', 'Remote', 'http://hub/all?token=abc')
            mock_req.calls.clear()
            remote.hubitatCtl({'cmd': 'PUSHBTN', 'value': 1})
            self.assertIn('/99/push/1?token=abc', mock_req.calls[0]['url'])

            mock_req.calls.clear()
            remote.hubitatCtl({'cmd': 'HOLDBTN', 'value': 1})
            self.assertIn('/99/hold/1?token=abc', mock_req.calls[0]['url'])

            mock_req.calls.clear()
            remote.hubitatCtl({'cmd': 'RELEASEBTN', 'value': 1})
            self.assertIn('/99/release/1?token=abc', mock_req.calls[0]['url'])
        finally:
            node_types.requests = orig_requests

    def test_airthings_f_vs_c_node_id(self):
        dev_c = {'temp_unit': 'C'}
        dev_f = {'temp_unit': 'F'}

        sensor_c = node_types.AirThingsSensor(self.poly, 'ctrl', 'air1', 'Air C', 'http://hub/all?token=x', dev_c)
        self.assertEqual(sensor_c.id, 'AIRTHSENSOR')

        sensor_f = node_types.AirThingsSensor(self.poly, 'ctrl', 'air2', 'Air F', 'http://hub/all?token=x', dev_f)
        self.assertEqual(sensor_f.id, 'AIRTHSENSORF')


if __name__ == '__main__':
    unittest.main()

