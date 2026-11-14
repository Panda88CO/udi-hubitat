"""
Dynamic JSON Profile Generator for Hubitat Devices in Polyglot v3 (PG3x).
Synthesizes NodeDefs on the fly matching the exact capabilities of paired devices.
"""

import json
import os
import re
import logging

LOGGER = logging.getLogger('profile_generator')

BASE_PROFILE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'base_profile.json')


def load_base_profile():
    """Loads baseline editors and profile metadata from data/base_profile.json."""
    if os.path.exists(BASE_PROFILE_PATH):
        try:
            with open(BASE_PROFILE_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            LOGGER.error(f"Error loading base_profile.json: {e}")
    return {
        "editors": [],
        "nodedefs": []
    }


def is_airthings(device):
    """Detects if a device is an Airthings air quality monitor."""
    dev_type = device.get('type', '').lower()
    dev_name = device.get('name', '').lower()
    attrs = device.get('attributes', {})
    if 'airthings' in dev_type or 'airthings' in dev_name:
        return True
    if 'radonShortTermAvg' in attrs or 'radon' in attrs:
        return True
    return False


def build_device_nodedef(device, temp_unit='F'):
    """
    Analyzes device capabilities and attributes, returning:
    (nodedef_id, drivers, command_map)
    where:
      - nodedef_id: clean uppercase identifier (<= 14 chars)
      - drivers: list of driver dicts: [{'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Status'}, ...]
      - command_map: dict mapping IoX command name to Hubitat REST command name
    """
    caps = set(device.get('capabilities', []))
    attrs = device.get('attributes', {})
    dev_id = str(device.get('id', ''))
    dev_type = device.get('type', '')

    drivers = []
    commands = {'QUERY': 'refresh'}
    features = []

    # 1. Specialized: Airthings Air Quality Monitor
    if is_airthings(device):
        t_uom = 17 if temp_unit == 'F' else 4
        drivers = [
            {'driver': 'ST', 'value': 99, 'uom': 124, 'name': '24H Radon Average'},
            {'driver': 'RADON', 'value': 99, 'uom': 124, 'name': 'Current Radon Reading'},
            {'driver': 'CLITEMP', 'value': 99, 'uom': t_uom, 'name': 'Temperature'},
            {'driver': 'CLIHUM', 'value': 99, 'uom': 22, 'name': 'Relative Humidity'},
            {'driver': 'GV0', 'value': 99, 'uom': 21, 'name': 'Absolute Humidity'},
            {'driver': 'ATMPRES', 'value': 99, 'uom': 117, 'name': 'Atmospheric Pressure'},
            {'driver': 'CO2LVL', 'value': 99, 'uom': 54, 'name': 'CO2 Level'},
            {'driver': 'AQI', 'value': 99, 'uom': 54, 'name': 'Air Quality Index'},
            {'driver': 'VOCLVL', 'value': 99, 'uom': 54, 'name': 'VOC Level'},
            {'driver': 'GV25', 'value': 99, 'uom': 122, 'name': 'PM2.5 Particle Count'},
            {'driver': 'GV1', 'value': 99, 'uom': 122, 'name': 'PM1.0 Particle Count'},
            {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery Level'},
            {'driver': 'TIME', 'value': 0, 'uom': 151, 'name': 'Last Update Time'},
        ]
        return ('AIRTHINGS', drivers, commands)

    # 2. Specialized: Thermostat (Ecobee or generic Hubitat Thermostat)
    if 'Thermostat' in caps or 'ThermostatMode' in caps:
        t_uom = 17 if temp_unit == 'F' else 4
        drivers = [
            {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
            {'driver': 'CLIMD', 'value': 0, 'uom': 25, 'name': 'Thermostat Mode'},
            {'driver': 'CLIFS', 'value': 0, 'uom': 25, 'name': 'Fan Operating State'},
            {'driver': 'CLIFRS', 'value': 0, 'uom': 25, 'name': 'Fan Mode'},
            {'driver': 'CLISPC', 'value': 72, 'uom': t_uom, 'name': 'Cool Setpoint'},
            {'driver': 'CLISPH', 'value': 68, 'uom': t_uom, 'name': 'Heat Setpoint'},
            {'driver': 'CLITEMP', 'value': 70, 'uom': t_uom, 'name': 'Ambient Temperature'},
            {'driver': 'CLIHUM', 'value': 50, 'uom': 22, 'name': 'Relative Humidity'},
        ]
        commands.update({
            'SETMODE': 'setThermostatMode',
            'SETFAN': 'setThermostatFanMode',
            'SETCOOL': 'setCoolingSetpoint',
            'SETHEAT': 'setHeatingSetpoint',
        })
        return ('THERMOSTAT', drivers, commands)

    # 3. Lock
    if 'Lock' in caps:
        drivers.append({'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Lock Status'})
        commands.update({'DON': 'lock', 'DOF': 'unlock'})
        features.append('LCK')

    # 4. Switch / Outlet / Relay
    has_switch = ('Switch' in caps or 'Outlet' in caps or 'Relay' in caps or 'switch' in attrs)
    if has_switch and not any(d['driver'] == 'ST' for d in drivers):
        drivers.append({'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Status'})
        commands.update({'DON': 'on', 'DOF': 'off'})
        features.append('SW')

    # 5. Dimmers / Level
    has_level = ('SwitchLevel' in caps or 'ChangeLevel' in caps or 'level' in attrs)
    if has_level:
        drivers.append({'driver': 'OL', 'value': 0, 'uom': 51, 'name': 'On Level'})
        commands.update({'SETLVL': 'setLevel'})
        features.append('LVL')

    # 6. Color / Color Temperature
    if 'ColorTemperature' in caps or 'colorTemperature' in attrs:
        drivers.append({'driver': 'GV0', 'value': 2700, 'uom': 26, 'name': 'Color Temperature'})
        commands.update({'SETKELVIN': 'setColorTemperature'})
        features.append('CT')
    if 'ColorControl' in caps or 'hue' in attrs:
        drivers.append({'driver': 'GV1', 'value': 0, 'uom': 56, 'name': 'Hue'})
        drivers.append({'driver': 'GV2', 'value': 0, 'uom': 100, 'name': 'Saturation'})
        commands.update({'SETHUE': 'setHue', 'SETSAT': 'setSaturation'})
        features.append('RGB')

    # 7. Power & Energy Metering
    if 'PowerMeter' in caps or 'power' in attrs:
        drivers.append({'driver': 'GV2' if 'RGB' not in features else 'GV3', 'value': 0, 'uom': 73, 'name': 'Power (Watts)'})
        features.append('PWR')
    if 'EnergyMeter' in caps or 'energy' in attrs:
        drivers.append({'driver': 'GV3' if 'PWR' not in features else 'GV4', 'value': 0, 'uom': 33, 'name': 'Total Energy (kWh)'})
        features.append('ENG')

    # 8. Motion & Contact Sensors
    if 'MotionSensor' in caps or 'motion' in attrs:
        if not any(d['driver'] == 'ST' for d in drivers):
            drivers.append({'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Motion'})
        else:
            drivers.append({'driver': 'GV5', 'value': 0, 'uom': 25, 'name': 'Motion'})
        features.append('MOT')

    if 'ContactSensor' in caps or 'contact' in attrs:
        if not any(d['driver'] == 'ST' for d in drivers):
            drivers.append({'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Contact'})
        else:
            drivers.append({'driver': 'GV6', 'value': 0, 'uom': 25, 'name': 'Contact'})
        features.append('CNT')

    # 9. Climate: Temperature & Humidity
    if 'TemperatureMeasurement' in caps or 'temperature' in attrs:
        t_uom = 17 if temp_unit == 'F' else 4
        drivers.append({'driver': 'CLITEMP', 'value': 0, 'uom': t_uom, 'name': 'Temperature'})
        features.append('TMP')

    if 'RelativeHumidityMeasurement' in caps or 'humidity' in attrs:
        drivers.append({'driver': 'CLIHUM', 'value': 0, 'uom': 22, 'name': 'Humidity'})
        features.append('HUM')

    # 10. Illuminance
    if 'IlluminanceMeasurement' in caps or 'illuminance' in attrs:
        drivers.append({'driver': 'LUMIN', 'value': 0, 'uom': 36, 'name': 'Illuminance'})
        features.append('LUX')

    # 11. Buttons (Pico, Aqara, Zigbee remotes)
    if {'PushableButton', 'HoldableButton', 'DoubleTapableButton'} & caps or 'pushed' in attrs:
        drivers.append({'driver': 'GV4', 'value': 0, 'uom': 57, 'name': 'Last Button Pushed'})
        drivers.append({'driver': 'GV5', 'value': 0, 'uom': 57, 'name': 'Last Button Held'})
        drivers.append({'driver': 'GV6', 'value': 0, 'uom': 57, 'name': 'Last Button Double Tapped'})
        features.append('BTN')

    # 12. Battery
    if 'Battery' in caps or 'battery' in attrs:
        drivers.append({'driver': 'BATLVL', 'value': 100, 'uom': 51, 'name': 'Battery Level'})
        features.append('BAT')

    # Fallback if no features matched: generic sensor/status
    if not drivers:
        drivers.append({'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'})
        features.append('GEN')

    # Every non-controller nodedef needs an ST property; add a plain status one if no feature supplied it.
    if not any(d['driver'] == 'ST' for d in drivers):
        drivers.insert(0, {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'})

    # Build clean uppercase NodeDef ID (<= 14 chars)
    # E.g. 'ND_SW_LVL_PWR' or 'ND_MOT_TMP_HUM'
    raw_id = 'ND_' + '_'.join(features)
    if len(raw_id) > 14:
        raw_id = raw_id[:14].rstrip('_')
    nodedef_id = raw_id.upper()

    return (nodedef_id, drivers, commands)


# IoX command metadata for cmds.accepts:
#   command id -> (display name, native, parameter editor id or None, property id the UI seeds the value from)
COMMAND_DEFS = {
    'QUERY':     ('Update', 'true', None, None),
    'DON':       ('On', 'true', None, None),
    'DOF':       ('Off', 'true', None, None),
    'SETLVL':    ('Set On Level', 'false', 'OL', 'OL'),
    'SETHUE':    ('Set Hue', 'false', 'ZCLHUE', 'GV1'),
    'SETSAT':    ('Set Saturation', 'false', 'ZCLSAT', 'GV2'),
    'SETKELVIN': ('Set Color Temperature', 'false', 'KELVIN', 'GV0'),
    'SETMODE':   ('Set Mode', 'false', 'SETCLIMD', 'CLIMD'),
    'SETFAN':    ('Set Fan Mode', 'false', 'CLIFRS', 'CLIFRS'),
    'SETCOOL':   ('Set Cool Setpoint', 'false', 'TSTATTEMP', 'CLISPC'),
    'SETHEAT':   ('Set Heat Setpoint', 'false', 'TSTATTEMP', 'CLISPH'),
}

# Feature token (from build_device_nodedef's generated id) -> label used in the nodedef display name
FEATURE_LABELS = {
    'SW': 'Switch', 'LVL': 'Dimmer', 'CT': 'Color Temp', 'RGB': 'Color', 'PWR': 'Power',
    'ENG': 'Energy', 'MOT': 'Motion', 'CNT': 'Contact', 'TMP': 'Temperature', 'HUM': 'Humidity',
    'LUX': 'Illuminance', 'BTN': 'Buttons', 'BAT': 'Battery', 'LCK': 'Lock', 'GEN': 'Generic',
}


def _nodedef_display_name(nodedef_id):
    """Human-readable nodedef name derived from the generated id (e.g. ND_SW_LVL -> 'Hubitat Switch / Dimmer')."""
    if nodedef_id == 'AIRTHINGS':
        return 'Hubitat Airthings Monitor'
    if nodedef_id == 'THERMOSTAT':
        return 'Hubitat Thermostat'
    tokens = [t for t in nodedef_id.split('_') if t and t != 'ND']
    return 'Hubitat ' + ' / '.join(FEATURE_LABELS.get(t, t.title()) for t in tokens)


def _build_accepts(commands, driver_ids):
    """cmds.accepts entries for every command id in `commands` (the generator's IoX-name -> Hubitat-command map)."""
    accepts = []
    for cmd_id in commands:
        name, native, editor, init = COMMAND_DEFS.get(cmd_id, (cmd_id, 'false', None, None))
        entry = {"id": cmd_id, "name": name, "native": native}
        if editor:
            param = {"id": "", "editor": editor, "optional": False}
            if init in driver_ids:
                param["init"] = init
            entry["parameters"] = [param]
        accepts.append(entry)
    return accepts


def generate_profile(devices, temp_unit='F'):
    """
    Transforms a list of Hubitat devices into a Dynamic Profiles *wire-shape* document, the shape
    udi_interface's updateJsonProfile() validates and sends to PG3x:
    {
        "profile_version": "1.0.0",
        "editors":  [ {"id": ..., "ranges": [ {"uom": "25", "subset": "0,1", "names": {...}} ]} ],
        "nodedefs": [ {"id": ..., "name": ..., "properties": [ {"id", "name", "editor"} ],
                       "cmds": {"sends": [], "accepts": [ ... ]}, "links": {"ctl": [], "rsp": []}} ],
        "linkdefs": []
    }
    """
    base = load_base_profile()
    profile_data = {
        "editors": list(base.get("editors", [])),
        "nodedefs": []
    }

    # Controller definition is always included. Its id must equal Controller.id in udi-hubitat.py.
    profile_data["nodedefs"].append({
        "id": "controller",
        "name": "Hubitat Elevation",
        "properties": [
            # Controller.drivers reports ST with uom 2, so use the editor that has a uom-2 range.
            {"id": "ST", "name": "NodeServer Online", "editor": "TRUEFALSE"}
        ],
        "cmds": {
            "sends": [],
            "accepts": [
                {"id": "DISCOVER", "name": "Re-Discover", "native": "false"},
                {"id": "UPDATEPROFILE", "name": "Update Profile", "native": "false"},
                {"id": "REMOVENOTICESALL", "name": "Remove Notices", "native": "false"}
            ]
        },
        "links": {"ctl": [], "rsp": []}
    })

    seen = {"controller"}
    for dev in devices:
        if not isinstance(dev, dict):
            continue
        nodedef_id, drivers, commands = build_device_nodedef(dev, temp_unit)
        if nodedef_id in seen:
            continue
        seen.add(nodedef_id)
        properties = [
            {
                "id": d['driver'],
                "name": d.get('name', d['driver']),
                "editor": _resolve_editor_for_driver(d['driver'], d.get('uom'))
            }
            for d in drivers
        ]
        profile_data["nodedefs"].append({
            "id": nodedef_id,
            "name": _nodedef_display_name(nodedef_id),
            "properties": properties,
            "cmds": {"sends": [], "accepts": _build_accepts(commands, {d['driver'] for d in drivers})},
            "links": {"ctl": [], "rsp": []}
        })

    return profile_data


def _resolve_editor_for_driver(driver, uom):
    """Maps a driver key and UOM to standard editor ID in base_profile.json."""
    if driver == 'ST':
        if uom == 124:
            return 'RADON'
        return 'TRUEFALSE'
    if driver == 'OL':
        return 'OL'
    if driver in ('CLITEMP', 'TSTATTEMP'):
        return 'CLITEMP'
    if driver == 'CLIHUM':
        return 'CLIHUM'
    if driver == 'BATLVL':
        return 'BATLVL'
    if driver == 'LUMIN':
        return 'LUMIN'
    if driver == 'RADON':
        return 'RADON'
    if uom == 122:
        return 'PARTICLE'
    if driver == 'CO2LVL':
        return 'CO2LVL'
    if driver == 'AQI':
        return 'AQI'
    if driver == 'VOCLVL':
        return 'VOCLVL'
    if driver == 'ATMPRES':
        return 'ATMPRES'
    if driver == 'TIME':
        return 'UNIXTIME'
    if uom == 57:
        return 'REMOTEBTN'
    if driver == 'CLIMD':
        return 'CLIMD'
    if driver in ('CLIFS', 'CLIFRS'):
        return 'CLIFRS'
    if driver in ('CLISPC', 'CLISPH'):
        return 'TSTATTEMP'
    if uom == 21:
        return 'ABSCLIHUM'
    if uom == 73:
        return 'CPW'
    if uom == 33:
        return 'TPW'
    if uom == 72:
        return 'CV'
    if uom == 1:
        return 'CC'
    if uom == 26:
        return 'KELVIN'
    if uom == 56:
        return 'ZCLHUE'
    if uom == 100:
        return 'ZCLSAT'
    return 'TRUEFALSE'

