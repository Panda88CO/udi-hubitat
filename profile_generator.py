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
    """Loads baseline editors from data/base_profile.json."""
    if os.path.exists(BASE_PROFILE_PATH):
        try:
            with open(BASE_PROFILE_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            LOGGER.error(f"Error loading base_profile.json: {e}")
    return {"editors": []}


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
            {'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'Status'},
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

    # Ensure every non-controller nodedef has an ST property
    if not any(d['driver'] == 'ST' for d in drivers):
        drivers.insert(0, {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'})
        if not features:
            features.append('GEN')

    # Build clean uppercase NodeDef ID (<= 14 chars)
    # E.g. 'ND_SW_LVL_PWR' or 'ND_MOT_TMP_HUM'
    raw_id = 'ND_' + '_'.join(features)
    if len(raw_id) > 14:
        raw_id = raw_id[:14].rstrip('_')
    nodedef_id = raw_id.upper()

    return (nodedef_id, drivers, commands)


_COMMAND_NAMES = {
    'QUERY': 'Update',
    'DON': 'On',
    'DOF': 'Off',
    'SETLVL': 'Set On Level',
    'SETKELVIN': 'Set Color Temperature',
    'SETHUE': 'Set Hue',
    'SETSAT': 'Set Saturation',
    'SETMODE': 'Set Thermostat Mode',
    'SETFAN': 'Set Fan Mode',
    'SETCOOL': 'Set Cool Setpoint',
    'SETHEAT': 'Set Heat Setpoint',
}

_NODEDEF_NAMES = {
    'AIRTHINGS': 'Airthings Air Quality',
    'THERMOSTAT': 'Thermostat',
}


def _command_name(cmd_id):
    return _COMMAND_NAMES.get(cmd_id, cmd_id.replace('_', ' ').title())


def _nodedef_name(nodedef_id):
    if nodedef_id in _NODEDEF_NAMES:
        return _NODEDEF_NAMES[nodedef_id]
    return f"Hubitat {nodedef_id}"


def _normalize_editors(raw_editors):
    """Normalizes editors into a list of {"id": ..., "ranges": [...]} with string uoms."""
    if isinstance(raw_editors, dict):
        editor_list = [{"id": ed_id, "ranges": ranges} for ed_id, ranges in raw_editors.items()]
    elif isinstance(raw_editors, list):
        editor_list = raw_editors
    else:
        return []

    normalized = []
    for ed in editor_list:
        ranges = []
        for r in ed.get("ranges", []):
            r_copy = dict(r)
            if "uom" in r_copy:
                r_copy["uom"] = str(r_copy["uom"])
            ranges.append(r_copy)
        normalized.append({"id": ed["id"], "ranges": ranges})
    return normalized


def generate_profile(devices, temp_unit='F'):
    """
    Transforms a list of Hubitat devices into the flat wire shape for
    Polyglot v3 (PG3x) updateJsonProfile:
    {
        "editors": [{"id": ..., "ranges": [...]}],
        "nodedefs": [
            {
                "id": "controller" | "<nodedef_id>",
                "name": "...",
                "properties": [{"id": ..., "editor": ..., "name": ...}],
                "cmds": {"sends": [...], "accepts": [...]},
                "links": {"ctl": [], "rsp": []}
            }
        ]
    }
    """
    base = load_base_profile()
    editors = _normalize_editors(base.get("editors", []))

    nodedefs = [
        {
            "id": "controller",
            "name": "Hubitat Elevation",
            "properties": [
                {"id": "ST", "editor": "ONLINE", "name": "NodeServer Online"}
            ],
            "cmds": {
                "sends": [],
                "accepts": [
                    {"id": "DISCOVER", "name": "Re-Discover"},
                    {"id": "UPDATEPROFILE", "name": "Update Profile"},
                    {"id": "REMOVENOTICESALL", "name": "Remove Notices"}
                ]
            },
            "links": {"ctl": [], "rsp": []}
        }
    ]
    seen_ids = {"controller"}

    for dev in devices:
        if not isinstance(dev, dict):
            continue
        nodedef_id, drivers, commands = build_device_nodedef(dev, temp_unit)
        if nodedef_id in seen_ids:
            continue
        seen_ids.add(nodedef_id)

        properties = [
            {
                "id": d["driver"],
                "editor": _resolve_editor_for_driver(d["driver"], d.get("uom")),
                "name": d.get("name", d["driver"])
            }
            for d in drivers
        ]
        sends_cmds = [cmd for cmd in ("DON", "DOF") if cmd in commands]
        nodedefs.append({
            "id": nodedef_id,
            "name": _nodedef_name(nodedef_id),
            "properties": properties,
            "cmds": {
                "sends": [{"id": cmd, "name": _command_name(cmd)} for cmd in sends_cmds],
                "accepts": [{"id": cmd, "name": _command_name(cmd)} for cmd in commands.keys()]
            },
            "links": {"ctl": [], "rsp": []}
        })

    return {
        "editors": editors,
        "nodedefs": nodedefs
    }


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
    if driver in ('GV25', 'GV1'):
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
    if driver in ('GV4', 'GV5', 'GV6'):
        return 'REMOTEBTN'
    if driver == 'CLIMD':
        return 'CLIMD'
    if driver == 'CLIFS':
        return 'CLIFS'
    if driver == 'CLIFRS':
        return 'CLIFRS'
    if driver in ('CLISPC', 'CLISPH'):
        return 'TSTATTEMP'
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

