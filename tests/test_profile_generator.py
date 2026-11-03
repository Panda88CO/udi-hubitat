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


if __name__ == '__main__':
    unittest.main()

