"""
Unit tests for udiLib.py.
"""
import unittest
from tests.test_helpers import MockNodeInstance
import udiLib


class TestUdiLib(unittest.TestCase):
    def setUp(self):
        self.drivers = [
            {'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Status'},
            {'driver': 'OL', 'value': 0, 'uom': 51, 'name': 'On Level'},
            {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'}
        ]
        self.node = MockNodeInstance(address='test_addr', drivers=self.drivers)

    def test_my_setDriver_success(self):
        result = udiLib.my_setDriver(self.node, 'ST', 100)
        self.assertTrue(result)
        self.assertIn('ST', self.node.driver_values)
        self.assertEqual(self.node.driver_values['ST']['value'], 100)
        self.assertIsNone(self.node.driver_values['ST']['uom'])

    def test_my_setDriver_with_unit(self):
        result = udiLib.my_setDriver(self.node, 'CLITEMP', 72.5, Unit=17)
        self.assertTrue(result)
        self.assertIn('CLITEMP', self.node.driver_values)
        self.assertEqual(self.node.driver_values['CLITEMP']['value'], 72.5)
        self.assertEqual(self.node.driver_values['CLITEMP']['uom'], 17)

    def test_my_setDriver_none_value_defaults_to_99(self):
        result = udiLib.my_setDriver(self.node, 'ST', None)
        self.assertTrue(result)
        self.assertEqual(self.node.driver_values['ST']['value'], 99)
        self.assertEqual(self.node.driver_values['ST']['uom'], 25)

    def test_my_setDriver_none_value_with_event_type(self):
        # When type == 'event', None value should not set 99
        self.node.driver_values.clear()
        result = udiLib.my_setDriver(self.node, 'ST', None, type='event')
        self.assertTrue(result)
        self.assertNotIn('ST', self.node.driver_values)

    def test_my_setDriver_non_existent_driver(self):
        result = udiLib.my_setDriver(self.node, 'INVALID_DRIVER', 50)
        self.assertFalse(result)
        self.assertNotIn('INVALID_DRIVER', self.node.driver_values)

    def test_my_setDriver_delegates_to_self_node_if_present(self):
        class Container:
            def __init__(self, drivers, node):
                self.drivers = drivers
                self.node = node

        container = Container(self.drivers, self.node)
        result = udiLib.my_setDriver(container, 'OL', 80)
        self.assertTrue(result)
        self.assertEqual(self.node.driver_values['OL']['value'], 80)

    def test_my_setDriver_handles_empty_drivers(self):
        empty_node = MockNodeInstance(address='empty', drivers=[])
        result = udiLib.my_setDriver(empty_node, 'ST', 1)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()

