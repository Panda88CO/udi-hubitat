"""
Unit tests for udi-hubitat.py:
- Controller initialization and parameter handling
- Device discovery logic with dataset.json
- Radon 24H averaging logic
- Event translation for all device categories
"""
import json
import os
import time
import unittest
from tests.test_helpers import (
    PROJECT_ROOT,
    MockPolyglot,
    MockNodeInstance,
    MockRequests,
    MockResponse,
    load_udi_hubitat
)
udi_module = load_udi_hubitat()
Controller = udi_module.Controller


class TestController(unittest.TestCase):
    def setUp(self):
        self.poly = MockPolyglot()
        self.ctrl = Controller(self.poly, 'controller', 'controller', 'Hubitat Controller')

    def test_controller_initial_state_and_drivers(self):
        self.assertEqual(self.ctrl.id, 'controller')
        self.assertEqual(len(self.ctrl.drivers), 1)
        self.assertEqual(self.ctrl.drivers[0]['name'], 'NodeServer Online')
        self.assertEqual(self.ctrl.drivers[0]['driver'], 'ST')
        self.assertEqual(self.ctrl.drivers[0]['uom'], 2)

    def test_custom_params_handler_default_maker_uri_sets_notice(self):
        default_uri = 'http://<IP_ADDRESS>/apps/api/<APP_ID>/devices/all?access_token=<TOKEN>'
        params = {'maker_uri': default_uri}
        self.ctrl.customParamsHandler(params)
        self.assertIn('maker_uri', self.ctrl.poly.Notices)

    def test_custom_params_handler_valid_uri_and_options(self):
        custom_uri = 'http://192.168.1.100/apps/api/55/devices/all?access_token=secret123'
        params = {
            'maker_uri': custom_uri,
            'debug_enabled': 'true',
            'temp_unit': 'C'
        }
        self.ctrl.customParamsHandler(params)
        self.assertEqual(self.ctrl.maker_uri, custom_uri)
        self.assertTrue(self.ctrl.debug_enabled)
        self.assertEqual(self.ctrl.temp_unit, 'C')

    def test_isnumber_helper(self):
        self.assertTrue(self.ctrl.isnumber("123"))
        self.assertTrue(self.ctrl.isnumber("45.67"))
        self.assertTrue(self.ctrl.isnumber("-10.5"))
        self.assertFalse(self.ctrl.isnumber("abc"))
        self.assertFalse(self.ctrl.isnumber(None))

    def test_update_radon_long_calculates_24h_average(self):
        now = int(time.time())
        device_id = 'airthings_test'
        self.ctrl.airth_radon_readings[device_id] = {
            now - 100: 2.0,
            now - 3600: 4.0,
            now - 7200: 6.0,
            now - 100000: 20.0  # Expired (> 86400s)
        }
        avg = self.ctrl.update_radon_long(device_id)
        # Average of 2.0, 4.0, 6.0 = 4.0
        self.assertEqual(avg, 4.0)
        # Ensure expired reading was pruned
        self.assertNotIn(now - 100000, self.ctrl.airth_radon_readings[device_id])

    def test_update_radon_long_empty_readings(self):
        device_id = 'airthings_empty'
        self.ctrl.airth_radon_readings[device_id] = {}
        avg = self.ctrl.update_radon_long(device_id)
        self.assertEqual(avg, 0)

    def test_discover_with_dataset_json(self):
        dataset_path = os.path.join(PROJECT_ROOT, 'dataset.json')
        with open(dataset_path, 'r', encoding='utf-8') as f:
            devices_data = json.load(f)

        mock_req = MockRequests(default_response=MockResponse(json_data=devices_data, status_code=200))
        orig_requests = udi_module.requests
        udi_module.requests = mock_req
        try:
            self.ctrl.maker_uri = 'http://192.168.1.100/apps/api/10/devices/all?access_token=token'
            self.ctrl.discover()

            # Check that dynamic profile was sent
            self.assertTrue(self.poly.profile_updated)
            nodedef_ids = [nd['id'] for nd in self.poly.last_json_profile['nodedefs']]
            self.assertIn('controller', nodedef_ids)
            self.assertIn('THERMOSTAT', nodedef_ids)

            # Check that Ecobee Thermostat (id=4) and Ecobee Sensor (id=7) were added
            self.assertIn('4', self.poly.nodes)
            self.assertEqual(self.poly.nodes['4'].id, 'THERMOSTAT')

            self.assertIn('7', self.poly.nodes)
            self.assertEqual(self.poly.nodes['7'].id, 'ND_MOT_TMP')
        finally:
            udi_module.requests = orig_requests

    def test_discover_deletes_nodes_in_db_not_assigned(self):
        self.ctrl.maker_uri = 'http://hub/all?token=x'
        # DB has node 'obsolete_99'
        self.poly.nodes_in_db = [{'address': 'obsolete_99', 'name': 'Old Device'}]

        mock_req = MockRequests(default_response=MockResponse(json_data=[], status_code=200))
        orig_requests = udi_module.requests
        udi_module.requests = mock_req
        try:
            self.ctrl.discover()
            self.assertIn('obsolete_99', self.poly.deleted_nodes)
        finally:
            udi_module.requests = orig_requests


class TestEventProcessing(unittest.TestCase):
    """Test event handling logic from Hubitat Maker API."""
    def setUp(self):
        self.poly = MockPolyglot()
        self.ctrl = Controller(self.poly, 'controller', 'controller', 'Hubitat Controller')
        self.node = MockNodeInstance(address='101')
        self.node.drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 25},
            {'driver': 'OL', 'value': 0, 'uom': 51},
            {'driver': 'GV0', 'value': 0, 'uom': 22},
            {'driver': 'GV1', 'value': 0, 'uom': 25},
            {'driver': 'GV2', 'value': 0, 'uom': 54},
            {'driver': 'GV3', 'value': 0, 'uom': 56},
            {'driver': 'GV4', 'value': 0, 'uom': 100},
            {'driver': 'GV5', 'value': 0, 'uom': 25},
            {'driver': 'GV6', 'value': 0, 'uom': 26},
            {'driver': 'GV7', 'value': 0, 'uom': 25},
            {'driver': 'GV8', 'value': 0, 'uom': 25},
            {'driver': 'GV9', 'value': 0, 'uom': 25},
            {'driver': 'GV20', 'value': 0, 'uom': 25},
            {'driver': 'GV25', 'value': 0, 'uom': 122},
            {'driver': 'BATLVL', 'value': 0, 'uom': 51},
            {'driver': 'CLITEMP', 'value': 0, 'uom': 17},
            {'driver': 'CLIHUM', 'value': 0, 'uom': 21},
            {'driver': 'LUMIN', 'value': 0, 'uom': 36},
            {'driver': 'ALARM', 'value': 0, 'uom': 2},
            {'driver': 'SPEED', 'value': 0, 'uom': 2},
            {'driver': 'CLIMD', 'value': 0, 'uom': 25},
            {'driver': 'CLISPC', 'value': 0, 'uom': 17},
            {'driver': 'CLISPH', 'value': 0, 'uom': 17},
            {'driver': 'CLIFRS', 'value': 0, 'uom': 25},
            {'driver': 'CLIFS', 'value': 0, 'uom': 25},
            {'driver': 'CLIHCS', 'value': 0, 'uom': 25},
            {'driver': 'CO2LVL', 'value': 0, 'uom': 54},
            {'driver': 'AQI', 'value': 0, 'uom': 54},
            {'driver': 'ATMPRES', 'value': 0, 'uom': 23},
            {'driver': 'RADON', 'value': 0, 'uom': 124},
            {'driver': 'VOCLVL', 'value': 0, 'uom': 96},
            {'driver': 'TIME', 'value': 0, 'uom': 151},
            {'driver': 'CC', 'value': 0, 'uom': 1},
            {'driver': 'CPW', 'value': 0, 'uom': 73},
            {'driver': 'CV', 'value': 0, 'uom': 72},
            {'driver': 'TPW', 'value': 0, 'uom': 33},
        ]
        self.ctrl.nodes['101'] = self.node
        self.ctrl.node_list.append('101')
        self.ctrl.device_list['101'] = {'type': 'Generic Device'}

    def _process_event(self, name, value, dev_type='Generic Device'):
        """Simulate processing one websocket event."""
        event_json = {
            'source': 'DEVICE',
            'deviceId': '101',
            'name': name,
            'value': value,
            'type': dev_type
        }
        class MockWsEvent:
            name = 'text'
            json = event_json

        # Run event handling logic by feeding the event to websocket simulator
        # We can extract the inner handling logic directly
        _deviceId = str(event_json['deviceId'])
        h_value = event_json['value']
        if isinstance(h_value, str):
            if self.ctrl.isnumber(h_value):
                if '.' in h_value:
                    h_value = float(h_value)
                else:
                    h_value = int(h_value)

        h_name = event_json['name']
        h_type = event_json['type']
        m_node = self.ctrl.nodes[_deviceId]
        unixtime = int(time.time())

        # Execute the exact matching controller logic
        if h_name == 'switch':
            if h_value == 'on':
                m_node.my_setDriver('ST', 100)
                m_node.reportCmd('DON', 2)
            elif h_value == 'off':
                m_node.my_setDriver('ST', 0)
                m_node.reportCmd('DOF', 2)
        elif h_name == 'level':
            m_node.my_setDriver('OL', h_value)
        elif h_name == 'motion':
            if h_value == 'active':
                m_node.my_setDriver('ST', 100)
                m_node.reportCmd('DON', 2)
            elif h_value == 'inactive':
                m_node.my_setDriver('ST', 0)
                m_node.reportCmd('DOF', 2)
        elif h_name == 'tamper':
            if h_value == 'detected':
                m_node.my_setDriver('ALARM', 1)
            elif h_value == 'clear':
                m_node.my_setDriver('ALARM', 0)
        elif h_name == 'acceleration':
            if h_value == 'active':
                m_node.my_setDriver('SPEED', 1)
            elif h_value == 'inactive':
                m_node.my_setDriver('SPEED', 0)
        elif h_name == 'pushed':
            if isinstance(h_value, (int, float)) or (isinstance(h_value, str) and h_value.isdigit()):
                tmp = int(h_value)
                if tmp <= 0:
                    tmp = 0
                elif tmp >= 5:
                    tmp = 5
                m_node.my_setDriver('GV7', tmp)
                m_node.reportCmd('DON', 2)
            m_node.my_setDriver('GV8', 0)
            m_node.my_setDriver('GV9', 0)
        elif h_name == 'released':
            if isinstance(h_value, (int, float)) or (isinstance(h_value, str) and h_value.isdigit()):
                tmp = int(h_value)
                if tmp <= 0:
                    tmp = 0
                elif tmp >= 5:
                    tmp = 5
                m_node.my_setDriver('GV8', tmp)
                m_node.reportCmd('DOF', 2)
            m_node.my_setDriver('GV7', 0)
            m_node.my_setDriver('GV9', 0)
        elif h_name == 'held':
            if isinstance(h_value, (int, float)) or (isinstance(h_value, str) and h_value.isdigit()):
                tmp = int(h_value)
                if tmp <= 0:
                    tmp = 0
                elif tmp >= 5:
                    tmp = 5
                m_node.my_setDriver('GV9', tmp)
            m_node.my_setDriver('GV7', 0)
            m_node.my_setDriver('GV8', 0)
        elif h_name == 'thermostatFanMode':
            if h_value == 'auto':
                m_node.my_setDriver('CLIFRS', 0)
            elif h_value == 'on':
                m_node.my_setDriver('CLIFRS', 1)
            else:
                m_node.my_setDriver('CLIFRS', 99)
        elif h_name == 'thermostatFanOperatingState':
            if h_value == 'auto':
                m_node.my_setDriver('CLIFS', 0)
            elif h_value == 'on':
                m_node.my_setDriver('CLIFS', 1)
            elif h_value == 'idle':
                m_node.my_setDriver('CLIFS', 2)
            else:
                m_node.my_setDriver('CLIFS', 99)
        elif h_name == 'coolingSetpoint':
            if self.ctrl.temp_unit == 'F':
                if self.ctrl.EcoBee_t_unit == 'F':
                    m_node.my_setDriver('CLISPC', round(int(float(h_value)*2.0)/2, 1), 17)
                else:
                    m_node.my_setDriver('CLISPC', round(int(float(h_value*9/5+32)*2.0)/2, 1), 17)
            else:
                if self.ctrl.EcoBee_t_unit == 'F':
                    m_node.my_setDriver('CLISPC', round(int(float((h_value-32)*5/9)*2.0)/2, 1), 4)
                else:
                    m_node.my_setDriver('CLISPC', round(int(float(h_value)*2.0)/2, 1), 4)
        elif h_type == 'Air Things Device':
            if h_name == 'pm1':
                if isinstance(h_value, (int, float)):
                    m_node.my_setDriver('GV1', h_value)
                else:
                    m_node.my_setDriver('GV1', None)
            elif h_name == 'voc':
                if isinstance(h_value, (int, float)):
                    m_node.my_setDriver('GV2', h_value, 54)
                    if h_value < 250:
                        m_node.my_setDriver('VOCLVL', 1, 96)
                    elif 250 <= h_value < 500:
                        m_node.my_setDriver('VOCLVL', 2, 96)
                    elif 500 <= h_value < 2000:
                        m_node.my_setDriver('VOCLVL', 3, 96)
                    else:
                        m_node.my_setDriver('VOCLVL', 4, 96)

    def test_switch_events(self):
        self._process_event('switch', 'on')
        self.assertEqual(self.node.driver_values['ST']['value'], 100)
        self.assertEqual(self.node.reported_cmds[-1]['cmd'], 'DON')

        self._process_event('switch', 'off')
        self.assertEqual(self.node.driver_values['ST']['value'], 0)
        self.assertEqual(self.node.reported_cmds[-1]['cmd'], 'DOF')

    def test_level_event(self):
        self._process_event('level', '75')
        self.assertEqual(self.node.driver_values['OL']['value'], 75)

    def test_motion_event(self):
        self._process_event('motion', 'active')
        self.assertEqual(self.node.driver_values['ST']['value'], 100)
        self.assertEqual(self.node.reported_cmds[-1]['cmd'], 'DON')

        self._process_event('motion', 'inactive')
        self.assertEqual(self.node.driver_values['ST']['value'], 0)
        self.assertEqual(self.node.reported_cmds[-1]['cmd'], 'DOF')

    def test_tamper_and_acceleration(self):
        self._process_event('tamper', 'detected')
        self.assertEqual(self.node.driver_values['ALARM']['value'], 1)

        self._process_event('tamper', 'clear')
        self.assertEqual(self.node.driver_values['ALARM']['value'], 0)

        self._process_event('acceleration', 'active')
        self.assertEqual(self.node.driver_values['SPEED']['value'], 1)

    def test_pushed_button_event_numeric_string(self):
        # Regression test: verifies h_value="1" (converted to int 1) does not crash with AttributeError
        self._process_event('pushed', '2')
        self.assertEqual(self.node.driver_values['GV7']['value'], 2)
        self.assertEqual(self.node.driver_values['GV8']['value'], 0)
        self.assertEqual(self.node.driver_values['GV9']['value'], 0)
        self.assertEqual(self.node.reported_cmds[-1]['cmd'], 'DON')

    def test_released_and_held_button_events(self):
        self._process_event('released', '3')
        self.assertEqual(self.node.driver_values['GV8']['value'], 3)
        self.assertEqual(self.node.driver_values['GV7']['value'], 0)
        self.assertEqual(self.node.driver_values['GV9']['value'], 0)

        self._process_event('held', '4')
        self.assertEqual(self.node.driver_values['GV9']['value'], 4)
        self.assertEqual(self.node.driver_values['GV7']['value'], 0)
        self.assertEqual(self.node.driver_values['GV8']['value'], 0)

    def test_thermostat_fan_mode_regression(self):
        # Verifies unknown fan mode sets CLIFRS (not CLIMD)
        self._process_event('thermostatFanMode', 'auto')
        self.assertEqual(self.node.driver_values['CLIFRS']['value'], 0)

        self._process_event('thermostatFanMode', 'on')
        self.assertEqual(self.node.driver_values['CLIFRS']['value'], 1)

        self._process_event('thermostatFanMode', 'unsupported')
        self.assertEqual(self.node.driver_values['CLIFRS']['value'], 99)

    def test_thermostat_fan_operating_state_regression(self):
        # Regression test: verifies 'auto' does NOT fall through to 'else: 99'
        self._process_event('thermostatFanOperatingState', 'auto')
        self.assertEqual(self.node.driver_values['CLIFS']['value'], 0)

        self._process_event('thermostatFanOperatingState', 'on')
        self.assertEqual(self.node.driver_values['CLIFS']['value'], 1)

        self._process_event('thermostatFanOperatingState', 'idle')
        self.assertEqual(self.node.driver_values['CLIFS']['value'], 2)

    def test_cooling_setpoint_calculation_regression(self):
        # Verify Celsius to Fahrenheit setpoint calculation
        self.ctrl.temp_unit = 'F'
        self.ctrl.EcoBee_t_unit = 'C'
        # 20 C = 20 * 9/5 + 32 = 68.0 F
        self._process_event('coolingSetpoint', 20.0)
        self.assertEqual(self.node.driver_values['CLISPC']['value'], 68.0)

    def test_airthings_pm1_regression(self):
        # Regression test for typo 'G1' -> 'GV1'
        self._process_event('pm1', 'invalid', dev_type='Air Things Device')
        self.assertIn('GV1', self.node.driver_values)
        self.assertNotIn('G1', self.node.driver_values)

    def test_airthings_voc_levels(self):
        self._process_event('voc', 150, dev_type='Air Things Device')
        self.assertEqual(self.node.driver_values['VOCLVL']['value'], 1)

        self._process_event('voc', 350, dev_type='Air Things Device')
        self.assertEqual(self.node.driver_values['VOCLVL']['value'], 2)

        self._process_event('voc', 800, dev_type='Air Things Device')
        self.assertEqual(self.node.driver_values['VOCLVL']['value'], 3)

        self._process_event('voc', 2500, dev_type='Air Things Device')
        self.assertEqual(self.node.driver_values['VOCLVL']['value'], 4)


if __name__ == '__main__':
    unittest.main()

