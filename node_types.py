""" Universal and Dynamic Node classes for Hubitat Node Server (Polyglot v3). """
try:
    import requests
except ImportError:
    requests = None
import re
import time
import json
from udiLib import my_setDriver

try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG)

    class _MockNode:
        def __init__(self, polyglot=None, primary=None, address=None, name=None):
            self.poly = polyglot
            self.primary = primary
            self.address = address
            self.name = name
            self.drivers = getattr(self, 'drivers', [])

        def setDriver(self, driver, value, report=True, force=False, uom=None):
            pass

        def reportCmd(self, cmd, val=None):
            pass

        def reportDrivers(self):
            pass

    class _MockCustom(dict):
        def __init__(self, polyglot=None, name=None):
            super().__init__()
            self.poly = polyglot
            self.name = name

        def load(self, params):
            self.update(params)

    class _MockUdi:
        Node = _MockNode
        LOGGER = logging
        Custom = _MockCustom

    udi_interface = _MockUdi


class GenericHubitatNode(udi_interface.Node):
    """
    Universal Hubitat Node for Polyglot v3.
    Dynamically configured with drivers and commands synthesized from Hubitat capabilities.
    """
    RESPONSE_OK = 200

    def __init__(self, polyglot, primary, address, name, maker_uri, node_def_id=None, drivers=None, command_map=None):
        self.poly = polyglot
        self.primary = primary
        self.address = self.getValidAddress(address)
        self.name = self.getValidName(name)
        self.maker_uri = maker_uri
        self.id = node_def_id or getattr(self, 'id', 'GEN_NODE')
        self.drivers = drivers if drivers is not None else getattr(self, 'drivers', [])
        self.command_map = command_map if command_map is not None else getattr(self, 'command_map', {})
        self.node = self

        super().__init__(polyglot, primary, self.address, self.name)

        # Instance commands table for Polyglot v3 dispatch
        self.commands = {
            'DON': self.cmd_on,
            'DOF': self.cmd_off,
            'DFON': self.cmd_on,
            'DFOF': self.cmd_off,
            'SETLVL': self.cmd_set_level,
            'QUERY': self.cmd_query,
            'SETMODE': self.cmd_set_mode,
            'SETFAN': self.cmd_set_fan,
            'SETCOOL': self.cmd_set_cool,
            'SETHEAT': self.cmd_set_heat,
            'SETKELVIN': self.cmd_set_kelvin,
            'SETHUE': self.cmd_set_hue,
            'SETSAT': self.cmd_set_sat,
        }

    def my_setDriver(self, key, value, Unit=None, force=False, type=None):
        return my_setDriver(self, key, value, Unit, force, type)

    def getValidAddress(self, address):
        if address is None:
            return ""
        return re.sub(r"[^A-Za-z0-9]", "", str(address))[:14].lower()

    def getValidName(self, name):
        if name is None:
            return ""
        name = bytes(str(name), 'utf-8').decode('utf-8', 'ignore')
        return re.sub(r"[^A-Za-z0-9_ ]", "", name)

    def _build_uri(self, device_id, h_cmd, val=None):
        if not getattr(self, 'maker_uri', None):
            return None
        dev_str = str(device_id) if device_id is not None else ''
        if '?' in self.maker_uri:
            _raw_uri = self.maker_uri.split('?', 1)
            _raw_http = _raw_uri[0].replace('all', dev_str)
            query_part = '?' + _raw_uri[1]
        else:
            _raw_http = self.maker_uri.replace('all', dev_str)
            query_part = ''
        if val is not None and str(val) != '':
            return f"{_raw_http}/{h_cmd}/{val}{query_part}"
        return f"{_raw_http}/{h_cmd}{query_part}"

    def _send_request(self, cmd_uri, max_retries=3, timeout=10):
        if not requests or not cmd_uri:
            return None
        retries = 0
        while retries < max_retries:
            try:
                r = requests.get(cmd_uri, timeout=timeout)
                if r.status_code == self.RESPONSE_OK:
                    return r
                time.sleep(1)
                logging.error('Hubitat not responding - waiting for good response')
            except Exception as e:
                logging.error(f'Hubitat request failed: {e}')
                time.sleep(1)
            retries += 1
        return None

    def _execute_h_cmd(self, iox_cmd_name, val=None):
        h_cmd = self.command_map.get(iox_cmd_name)
        if not h_cmd:
            logging.warning(f"No Hubitat command mapped for {iox_cmd_name} on {self.address}")
            return False
        uri = self._build_uri(self.address, h_cmd, val)
        return self._send_request(uri) is not None

    def cmd_on(self, command=None):
        self._execute_h_cmd('DON')

    def cmd_off(self, command=None):
        self._execute_h_cmd('DOF')

    def cmd_set_level(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETLVL', val)

    def cmd_query(self, command=None):
        uri = self._build_uri(self.address, 'refresh')
        self._send_request(uri)

    def cmd_set_mode(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETMODE', val)

    def cmd_set_fan(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETFAN', val)

    def cmd_set_cool(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETCOOL', val)

    def cmd_set_heat(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETHEAT', val)

    def cmd_set_kelvin(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETKELVIN', val)

    def cmd_set_hue(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETHUE', val)

    def cmd_set_sat(self, command):
        val = command.get('value')
        self._execute_h_cmd('SETSAT', val)

    # Alias methods for legacy compatibility
    def hubitatRefresh(self):
        self.cmd_query()

    def hubitatCtl(self, command):
        cmd = command.get('cmd')
        val = command.get('value')
        self._execute_h_cmd(cmd, val)


# Legacy Base Class & Subclasses for backward compatibility
class HubitatBase(GenericHubitatNode):
    pass


class StdLampNode(GenericHubitatNode):
    id = 'STDLAMP'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'OL', 'value': 75, 'uom': 51, 'name': 'On Level'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'STDLAMP', self.drivers,
                         {'DON': 'on', 'DOF': 'off', 'SETLVL': 'setLevel'})


class RgbLampNode(GenericHubitatNode):
    id = 'COLORLIGHT'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'OL', 'value': 99, 'uom': 51, 'name': 'On Level'},
        {'driver': 'GV3', 'value': 99, 'uom': 56, 'name': 'Hue'},
        {'driver': 'GV4', 'value': 99, 'uom': 100, 'name': 'Saturation'},
        {'driver': 'GV5', 'value': 99, 'uom': 25, 'name': 'Color Mode'},
        {'driver': 'GV6', 'value': 99, 'uom': 26, 'name': 'Color Temperature'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'COLORLIGHT', self.drivers,
                         {'DON': 'on', 'DOF': 'off', 'SETLVL': 'setLevel'})


class CtLampNode(GenericHubitatNode):
    id = 'CTLAMP'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'OL', 'value': 99, 'uom': 51, 'name': 'On Level'},
        {'driver': 'GV0', 'value': 99, 'uom': 26, 'name': 'Color Temperature'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'CTLAMP', self.drivers,
                         {'DON': 'on', 'DOF': 'off', 'SETLVL': 'setLevel'})


class SwitchNode(GenericHubitatNode):
    id = 'SWITCH'
    drivers = [{'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'}]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'SWITCH', self.drivers,
                         {'DON': 'on', 'DOF': 'off'})


class OutletNode(GenericHubitatNode):
    id = 'OUTLET'
    drivers = [{'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'}]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'OUTLET', self.drivers,
                         {'DON': 'on', 'DOF': 'off'})


class EnergyOutletNode(GenericHubitatNode):
    id = 'ENERGYOUTLET'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'CC', 'value': 99, 'uom': 1, 'name': 'Current (Amps)'},
        {'driver': 'CPW', 'value': 99, 'uom': 73, 'name': 'Power (Watts)'},
        {'driver': 'CV', 'value': 99, 'uom': 72, 'name': 'Voltage'},
        {'driver': 'TPW', 'value': 99, 'uom': 33, 'name': 'Total Power Used (energy)'},
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'ENERGYOUTLET', self.drivers,
                         {'DON': 'on', 'DOF': 'off'})


class DimmerNode(GenericHubitatNode):
    id = 'DIMMER'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'OL', 'value': 99, 'uom': 51, 'name': 'On Level'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'DIMMER', self.drivers,
                         {'DON': 'on', 'DOF': 'off', 'SETLVL': 'setLevel'})


class MotionSensor(GenericHubitatNode):
    id = 'MSSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'MSSENSOR', self.drivers)


class ContactNode(GenericHubitatNode):
    id = 'CONTACT'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery Level'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'CONTACT', self.drivers)


class THSensor(GenericHubitatNode):
    id = 'THSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLIHUM', 'value': 99, 'uom': 22, 'name': 'Humidity'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'THSENSOR', self.drivers)


class LutronPicoNode(GenericHubitatNode):
    id = 'LUTPICO'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'GV4', 'value': 99, 'uom': 57, 'name': 'Last Button Pushed'},
        {'driver': 'GV5', 'value': 99, 'uom': 57, 'name': 'Last Button Released'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'LUTPICO', self.drivers)


class LutronFastPicoNode(GenericHubitatNode):
    id = 'LUTPICO'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'GV4', 'value': 99, 'uom': 57, 'name': 'Last Button Pushed'},
        {'driver': 'GV5', 'value': 99, 'uom': 57, 'name': 'Last Button Released'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'LUTPICO', self.drivers)


class SimpleRemoteNode(GenericHubitatNode):
    id = 'SIMPLEREMOTE'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'GV4', 'value': 99, 'uom': 57, 'name': 'Last Button Pushed'},
        {'driver': 'GV5', 'value': 99, 'uom': 57, 'name': 'Last Button Released'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'SIMPLEREMOTE', self.drivers)


class EcobeeSensor(GenericHubitatNode):
    id = 'ECOBEESENS'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Motion/Occupancy'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'CLIHUM', 'value': 99, 'uom': 22, 'name': 'Relative Humidity'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'ECOBEESENS', self.drivers)


class AirThingsSensor(GenericHubitatNode):
    id = 'AIRTHSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 124, 'name': '24H Longterm Radon Level'},
        {'driver': 'RADON', 'value': 99, 'uom': 124, 'name': 'Current Radon Reading'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'CLIHUM', 'value': 99, 'uom': 22, 'name': 'Relative Humidity'},
        {'driver': 'GV0', 'value': 99, 'uom': 21, 'name': 'Absolute Humidity'},
        {'driver': 'ATMPRES', 'value': 99, 'uom': 117, 'name': 'Atmospheric Pressure'},
        {'driver': 'CO2LVL', 'value': 99, 'uom': 54, 'name': 'CO2 level'},
        {'driver': 'AQI', 'value': 99, 'uom': 54, 'name': 'Air Quality Index'},
        {'driver': 'VOCLVL', 'value': 99, 'uom': 54, 'name': 'VOC level'},
        {'driver': 'GV2', 'value': 99, 'uom': 25, 'name': 'VOC state'},
        {'driver': 'GV25', 'value': 99, 'uom': 122, 'name': '2.5 ppm particle count'},
        {'driver': 'GV1', 'value': 99, 'uom': 122, 'name': '1 ppm particle count'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery Level'},
        {'driver': 'TIME', 'value': int(time.time()), 'uom': 151, 'name': 'Last Update Time'},
        {'driver': 'GV20', 'value': 99, 'uom': 25, 'name': 'Device Status'},
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri, dev=None):
        node_id = 'AIRTHSENSOR'
        if dev and dev.get('temp_unit') == 'F':
            node_id = 'AIRTHSENSORF'
        super().__init__(polyglot, primary, address, name, marker_uri, node_id, self.drivers)


class EcobeeThermostat(GenericHubitatNode):
    id = 'ECOBEETSTAT'
    drivers = [
        {'driver': 'CLIMD', 'value': 99, 'uom': 25, 'name': 'Thermostat Mode'},
        {'driver': 'CLIFS', 'value': 99, 'uom': 25, 'name': 'Thermostat Fan State'},
        {'driver': 'CLIFRS', 'value': 99, 'uom': 25, 'name': 'Thermostat Fan Mode'},
        {'driver': 'CLISPC', 'value': 99, 'uom': 17, 'name': 'Cooling Setpoint'},
        {'driver': 'CLISPH', 'value': 99, 'uom': 17, 'name': 'Heating Setpoint'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Ambient Temperature'},
        {'driver': 'CLIHUM', 'value': 99, 'uom': 22, 'name': 'Relative Humidity'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'ECOBEETSTAT', self.drivers,
                         {'SETMODE': 'setThermostatMode', 'SETFAN': 'setThermostatFanMode',
                          'SETCOOL': 'setCoolingSetpoint', 'SETHEAT': 'setHeatingSetpoint'})


# MultiSensor variants
class MultiSensorTHLA(GenericHubitatNode):
    id = 'MSTHLASENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLIHUM', 'value': 99, 'uom': 22, 'name': 'Humidity'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'LUMIN', 'value': 99, 'uom': 36, 'name': 'Illuminance'},
        {'driver': 'ALARM', 'value': 99, 'uom': 2, 'name': 'Tamper Alarm'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'MSTHLASENSOR', self.drivers)


class MultiSensorTLAS(GenericHubitatNode):
    id = 'MSTLASSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'LUMIN', 'value': 99, 'uom': 36, 'name': 'Illuminance'},
        {'driver': 'ALARM', 'value': 99, 'uom': 2, 'name': 'Tamper Alarm'},
        {'driver': 'SPEED', 'value': 99, 'uom': 2, 'name': 'Acceleration'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'MSTLASSENSOR', self.drivers)


class MultiSensorTH(GenericHubitatNode):
    id = 'MSTHSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLIHUM', 'value': 99, 'uom': 22, 'name': 'Humidity'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'MSTHSENSOR', self.drivers)


class MultiSensorT(GenericHubitatNode):
    id = 'MSTSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'MSTSENSOR', self.drivers)


class MultiSensorTL(GenericHubitatNode):
    id = 'MSTLSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'LUMIN', 'value': 99, 'uom': 36, 'name': 'Illuminance'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'MSTLSENSOR', self.drivers)


class MultiSensorL(GenericHubitatNode):
    id = 'MSLSENSOR'
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery'},
        {'driver': 'LUMIN', 'value': 99, 'uom': 36, 'name': 'Illuminance'}
    ]
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri, 'MSLSENSOR', self.drivers)
