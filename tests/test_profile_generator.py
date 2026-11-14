"""
Unit tests specifically targeting profile_generator.py:
- Airthings sensor capability detection and driver synthesis
- Color lights, dimmers, power/energy meters
- Thermostat in Fahrenheit and Celsius
- Generic fallback for unknown device types
"""
import unittest
import profile_generator


class TestProfileGenerator(unittest.TestCase):
    def test_airthings_sensor_profile_generation(self):
        airthings_dev = {
            'id': '500',
            'name': 'Airthings Wave Plus',
            'label': 'Basement Airthings',
            'type': 'Air Things Device',
            'capabilities': ['Sensor', 'Refresh'],
            'attributes': {'radonShortTermAvg': '45', 'co2': '600', 'voc': '120'}
        }
        nid, drivers, commands = profile_generator.build_device_nodedef(airthings_dev, temp_unit='F')
        self.assertEqual(nid, 'AIRTHINGS')
        driver_keys = [d['driver'] for d in drivers]
        self.assertIn('ST', driver_keys)
        self.assertIn('RADON', driver_keys)
        self.assertIn('CO2LVL', driver_keys)
        self.assertIn('VOCLVL', driver_keys)
        self.assertIn('GV25', driver_keys)
        self.assertIn('GV1', driver_keys)
        self.assertIn('ATMPRES', driver_keys)
        self.assertIn('TIME', driver_keys)

        # Temp driver in F should have uom=17
        temp_d = next(d for d in drivers if d['driver'] == 'CLITEMP')
        self.assertEqual(temp_d['uom'], 17)

    def test_airthings_celsius(self):
        airthings_dev = {
            'id': '501',
            'name': 'Airthings Wave',
            'type': 'Airthings Wave',
            'capabilities': ['Sensor'],
            'attributes': {'radon': '10'}
        }
        nid, drivers, commands = profile_generator.build_device_nodedef(airthings_dev, temp_unit='C')
        self.assertEqual(nid, 'AIRTHINGS')
        temp_d = next(d for d in drivers if d['driver'] == 'CLITEMP')
        self.assertEqual(temp_d['uom'], 4)

    def test_color_light_with_power(self):
        rgb_bulb = {
            'id': '300',
            'name': 'Inovelli Color Bulb',
            'capabilities': ['Switch', 'SwitchLevel', 'ColorControl', 'ColorTemperature', 'PowerMeter'],
            'attributes': {'switch': 'on', 'level': '100', 'power': '9.5'}
        }
        nid, drivers, commands = profile_generator.build_device_nodedef(rgb_bulb)
        driver_keys = [d['driver'] for d in drivers]
        self.assertIn('ST', driver_keys)
        self.assertIn('OL', driver_keys)
        self.assertIn('GV0', driver_keys)  # Color Temp
        self.assertIn('GV1', driver_keys)  # Hue
        self.assertIn('GV2', driver_keys)  # Saturation
        self.assertIn('DON', commands)
        self.assertIn('DOF', commands)
        self.assertIn('SETLVL', commands)
        self.assertIn('SETKELVIN', commands)

    def test_lock_device(self):
        lock_dev = {
            'id': '400',
            'name': 'Yale Assure Lock',
            'capabilities': ['Lock', 'Battery'],
            'attributes': {'lock': 'locked', 'battery': '90'}
        }
        nid, drivers, commands = profile_generator.build_device_nodedef(lock_dev)
        self.assertEqual(nid, 'ND_LCK_BAT')
        self.assertIn('DON', commands)
        self.assertEqual(commands['DON'], 'lock')
        self.assertIn('DOF', commands)
        self.assertEqual(commands['DOF'], 'unlock')

    def test_unknown_device_fallback(self):
        unknown_dev = {
            'id': '999',
            'name': 'Virtual Helper Tool',
            'capabilities': [],
            'attributes': {}
        }
        nid, drivers, commands = profile_generator.build_device_nodedef(unknown_dev)
        self.assertEqual(nid, 'ND_GEN')
        self.assertEqual(len(drivers), 1)
        self.assertEqual(drivers[0]['driver'], 'ST')
        self.assertEqual(drivers[0]['value'], 99)


SAMPLE_DEVICES = [
    {'id': '1', 'name': 'Airthings Wave Plus', 'type': 'Airthings', 'capabilities': ['Sensor'], 'attributes': {'radon': '1'}},
    {'id': '2', 'name': 'Ecobee', 'capabilities': ['Thermostat', 'ThermostatMode'], 'attributes': {}},
    {'id': '3', 'name': 'Lock', 'capabilities': ['Lock', 'Battery'], 'attributes': {}},
    {'id': '4', 'name': 'Dimmer', 'capabilities': ['Switch', 'SwitchLevel'], 'attributes': {}},
    {'id': '5', 'name': 'RGB', 'capabilities': ['Switch', 'SwitchLevel', 'ColorControl', 'ColorTemperature', 'PowerMeter'], 'attributes': {}},
    {'id': '6', 'name': 'Multi', 'capabilities': ['MotionSensor', 'TemperatureMeasurement', 'RelativeHumidityMeasurement', 'IlluminanceMeasurement', 'Battery'], 'attributes': {}},
    {'id': '7', 'name': 'Pico', 'capabilities': ['PushableButton', 'Battery'], 'attributes': {}},
    {'id': '8', 'name': 'Virtual', 'capabilities': [], 'attributes': {}},
    {'id': '9', 'name': 'Door', 'capabilities': ['ContactSensor', 'Battery'], 'attributes': {}},
    {'id': '10', 'name': 'Outlet', 'capabilities': ['Switch', 'PowerMeter', 'EnergyMeter'], 'attributes': {}},
    {'id': '11', 'name': 'TempOnly', 'capabilities': ['TemperatureMeasurement'], 'attributes': {}},
]


class TestWireShape(unittest.TestCase):
    """generate_profile() must emit the shape udi_interface.updateJsonProfile() validates."""

    @classmethod
    def setUpClass(cls):
        cls.profile = profile_generator.generate_profile(SAMPLE_DEVICES, temp_unit='F')
        cls.editors = {e['id']: e for e in cls.profile['editors']}

    def test_top_level_sections_are_lists_of_dicts_with_string_ids(self):
        for section in ('editors', 'nodedefs', 'linkdefs'):
            self.assertIsInstance(self.profile[section], list, f'{section} must be a list')
            for item in self.profile[section]:
                self.assertIsInstance(item, dict)
                self.assertIsInstance(item['id'], str)

    def test_editor_ranges_use_string_uom(self):
        for ed in self.profile['editors']:
            self.assertIsInstance(ed['ranges'], list)
            for r in ed['ranges']:
                self.assertIsInstance(r['uom'], str, f"editor {ed['id']}")
                self.assertNotIn('nls', r, 'nls is not used on the wire; use inline names')

    def test_nodedef_structure_and_controller(self):
        ids = [n['id'] for n in self.profile['nodedefs']]
        self.assertEqual(ids[0], 'controller')
        self.assertEqual(len(ids), len(set(ids)), 'nodedef ids must be unique')
        for nd in self.profile['nodedefs']:
            self.assertTrue(nd['name'])
            self.assertEqual(nd['links'], {'ctl': [], 'rsp': []})
            self.assertEqual(nd['cmds']['sends'], [])
            self.assertIsInstance(nd['cmds']['accepts'], list)
            prop_ids = [p['id'] for p in nd['properties']]
            self.assertEqual(len(prop_ids), len(set(prop_ids)), f"{nd['id']}: duplicate property ids")

    def test_every_nodedef_has_st(self):
        for nd in self.profile['nodedefs']:
            self.assertIn('ST', [p['id'] for p in nd['properties']], nd['id'])

    def test_editor_references_resolve(self):
        for nd in self.profile['nodedefs']:
            for p in nd['properties']:
                self.assertIn(p['editor'], self.editors, f"{nd['id']}.{p['id']}")
            for a in nd['cmds']['accepts']:
                for param in a.get('parameters', []):
                    self.assertIn(param['editor'], self.editors, f"{nd['id']}.{a['id']}")
                    if 'init' in param:
                        self.assertIn(param['init'], [p['id'] for p in nd['properties']])

    def test_property_editor_has_range_for_driver_uom(self):
        """Regression: GV1 hue->PARTICLE, GV4 energy->REMOTEBTN, GV0 abs. humidity->TRUEFALSE."""
        for dev in SAMPLE_DEVICES:
            _, drivers, _ = profile_generator.build_device_nodedef(dev, 'F')
            for d in drivers:
                editor = self.editors[profile_generator._resolve_editor_for_driver(d['driver'], d['uom'])]
                uoms = {r['uom'] for r in editor['ranges']}
                self.assertIn(str(d['uom']), uoms, f"{dev['name']}: {d['driver']} (uom {d['uom']}) -> editor {editor['id']}")

    def test_all_generated_commands_have_metadata(self):
        for dev in SAMPLE_DEVICES:
            _, _, commands = profile_generator.build_device_nodedef(dev, 'F')
            for cmd_id in commands:
                self.assertIn(cmd_id, profile_generator.COMMAND_DEFS, f"{dev['name']}: {cmd_id}")

    def test_thermostat_commands_carry_parameter_editors(self):
        tstat = next(n for n in self.profile['nodedefs'] if n['id'] == 'THERMOSTAT')
        setcool = next(a for a in tstat['cmds']['accepts'] if a['id'] == 'SETCOOL')
        self.assertEqual(setcool['parameters'][0]['editor'], 'TSTATTEMP')
        self.assertEqual(setcool['parameters'][0]['init'], 'CLISPC')


if __name__ == '__main__':
    unittest.main()

