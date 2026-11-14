#!/usr/bin/env python3
"""
Hubitat Elevation NodeServer for Universal Devices Polyglot v3 (PG3x).
Capability-Driven Generic Connector with Dynamic JSON Profiles.
"""

import sys
import os
import json
import time
import re
import threading
import traceback
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

try:
    from lomond import WebSocket
except ImportError:
    WebSocket = None

import node_types
import profile_generator
from udiLib import my_setDriver

try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)

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
    Custom = _MockCustom

version = '0.2.0'


class Controller(udi_interface.Node):
    """
    Controller node for Hubitat Elevation NodeServer.
    Manages Maker API discovery, dynamic profile updates, and live WebSocket event dispatch.
    """
    id = 'controller'
    drivers = [{'driver': 'ST', 'value': 1, 'uom': 2, 'name': 'NodeServer Online'}]

    def __init__(self, polyglot, primary, address, name):
        super().__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.primary = primary
        self.address = address
        self.name = name
        self.node = self
        self.RESPONSE_OK = 200

        self.drivers = [{'driver': 'ST', 'value': 1, 'uom': 2, 'name': 'NodeServer Online'}]
        self.nodes = {}
        self.node_list = []
        self.device_list = {}
        self.airth_radon_readings = {}
        self.n_queue = []
        self.hb = 0
        self.configDone = False
        self.debug_enabled = True
        self.temp_unit = 'F'
        self.EcoBee_t_unit = 'F'
        self.ws_thread = None

        self.Parameters = Custom(self.poly, 'customparams')
        self.Notices = Custom(self.poly, 'notices')

        if hasattr(self.poly, 'subscribe'):
            self.poly.subscribe(self.poly.STOP, self.stopHandler)
            self.poly.subscribe(self.poly.START, self.start, address)
            self.poly.subscribe(self.poly.CUSTOMPARAMS, self.customParamsHandler)
            self.poly.subscribe(self.poly.CONFIGDONE, self.configDoneHandler)
            self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

        if hasattr(self.poly, 'addNode'):
            self.poly.addNode(self)

    def my_setDriver(self, key, value, Unit=None, force=False, type=None):
        return my_setDriver(self, key, value, Unit, force, type)

    def getValidName(self, name):
        if name is None:
            return ""
        name = bytes(str(name), 'utf-8').decode('utf-8', 'ignore')
        return re.sub(r"[^A-Za-z0-9_ ]", "", name)

    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        timeout = 50
        while len(self.n_queue) == 0 and timeout > 0:
            time.sleep(0.1)
            timeout -= 1
        if len(self.n_queue) > 0:
            self.n_queue.pop()

    def heartbeat(self):
        logging.debug(f'heartbeat: {self.hb}')
        if self.hb == 0:
            self.reportCmd('DON', 2)
            self.hb = 1
        else:
            self.reportCmd('DOF', 2)
            self.hb = 0

    def start(self):
        logging.info(f'Started Hubitat NodeServer v{version}')
        self.my_setDriver('ST', 1)
        if hasattr(self.poly, 'Notices') and hasattr(self.poly.Notices, 'clear'):
            self.poly.Notices.clear()

        # Perform discovery and profile generation
        self.discover()

        # Start WebSocket event listener in background daemon thread
        if self.ws_thread is None or not self.ws_thread.is_alive():
            self.ws_thread = threading.Thread(target=self.hubitat_events, daemon=True, name="HubitatEvents")
            self.ws_thread.start()
            logging.info('Started background Hubitat WebSocket event listener.')

    def stopHandler(self):
        self.my_setDriver('ST', 0)
        if hasattr(self.poly, 'stop'):
            self.poly.stop()

    def configDoneHandler(self):
        if hasattr(self.poly, 'Notices') and hasattr(self.poly.Notices, 'clear'):
            self.poly.Notices.clear()
        self.configDone = True

    def query(self):
        for node_id in self.nodes:
            if hasattr(self.nodes[node_id], 'reportDrivers'):
                self.nodes[node_id].reportDrivers()

    def customParamsHandler(self, userParams):
        self.Parameters.load(userParams)
        default_maker_uri = 'http://<IP_ADDRESS>/apps/api/<APP_ID>/devices/all?access_token=<TOKEN>'
        self.maker_uri = default_maker_uri

        if 'maker_uri' in userParams:
            self.maker_uri = userParams['maker_uri']
        else:
            logging.error('Hubitat Maker API URL is not defined in configuration')

        if 'debug_enabled' in userParams:
            self.debug_enabled = str(userParams['debug_enabled']).lower() in ('true', '1')

        if self.maker_uri == default_maker_uri and hasattr(self.poly, 'Notices'):
            self.poly.Notices['maker_uri'] = 'Please set proper Hubitat Maker API URI and restart this NodeServer'

        if 'temp_unit' in userParams:
            self.temp_unit = 'C' if str(userParams['temp_unit']).upper().startswith('C') else 'F'
            self.EcoBee_t_unit = self.temp_unit

    def update_radon_long(self, _deviceId, current_pci=None):
        """Calculates 24H rolling average radon level for Airthings sensors."""
        now = int(time.time())
        readings = self.airth_radon_readings.setdefault(_deviceId, {})
        if current_pci is not None:
            readings[now] = current_pci

        total = 0
        count = 0
        delete_list = []
        for timestamp, val in readings.items():
            if now - timestamp <= 86400:
                total += val
                count += 1
            else:
                delete_list.append(timestamp)

        for timestamp in delete_list:
            del readings[timestamp]

        avg_radon = round(total / count, 1) if count > 0 else 0
        logging.debug(f'Radon 24H average for {_deviceId}: {avg_radon} pCi/L ({count} readings)')
        return avg_radon

    def discover(self, *args, **kwargs):
        """
        Discovers all devices from Hubitat Maker API, dynamically generates
        the matching JSON profile, and instantiates nodes.
        """
        assigned_addresses = ['controller']
        if not requests or not getattr(self, 'maker_uri', None):
            logging.error('Cannot discover: requests or maker_uri not available')
            return

        try:
            r = requests.get(self.maker_uri, timeout=10)
            retries = 0
            while r.status_code != self.RESPONSE_OK and retries < 3:
                time.sleep(1)
                r = requests.get(self.maker_uri, timeout=10)
                retries += 1
            if r.status_code != self.RESPONSE_OK:
                logging.error(f'Hubitat discover failed with status {r.status_code}')
                return
            data = r.json()
        except Exception as e:
            logging.error(f'Error during discover: {e}')
            return

        logging.debug(f'Discovered {len(data)} devices from Hubitat Maker API.')

        # 1. Synthesize and push Dynamic JSON Profile
        profile_data = profile_generator.generate_profile(data, self.temp_unit)
        if hasattr(self.poly, 'updateJsonProfile'):
            try:
                self.poly.updateJsonProfile(profile_data)
                logging.info('Successfully sent dynamic JSON profile to Polyglot.')
            except Exception as e:
                logging.error(f'Failed to send updateJsonProfile: {e}')
        elif hasattr(self.poly, 'updateProfile'):
            self.poly.updateProfile()

        # 2. Instantiate and add nodes
        for dev in data:
            if not isinstance(dev, dict):
                continue
            _name = dev.get('name', '')
            _dev_name = dev.get('label') or _name or 'Device'
            if hasattr(self.poly, 'getValidName'):
                _label = self.poly.getValidName(_dev_name)
            else:
                _label = self.getValidName(_dev_name)

            _id = str(dev['id'])
            self.device_list[_id] = dev
            dev['temp_unit'] = self.temp_unit

            if self.debug_enabled:
                logging.debug(
                    f"Discovered Hubitat device id={_id} name={dev.get('name')!r} "
                    f"label={dev.get('label')!r} type={dev.get('type')!r} "
                    f"capabilities={dev.get('capabilities')} attributes={dev.get('attributes')}"
                )

            nodedef_id, drivers, command_map = profile_generator.build_device_nodedef(dev, self.temp_unit)

            node = node_types.GenericHubitatNode(
                self.poly,
                self.address,
                _id,
                _label,
                self.maker_uri,
                node_def_id=nodedef_id,
                drivers=drivers,
                command_map=command_map
            )
            if hasattr(self.poly, 'addNode'):
                self.poly.addNode(node)

            self.nodes[_id] = node
            assigned_addresses.append(_id)

        # 3. Synchronize nodes from Polyglot & Clean up orphaned nodes
        if hasattr(self.poly, 'getNodes'):
            poly_nodes = self.poly.getNodes()
            if poly_nodes:
                self.nodes.update(poly_nodes)
            for node_key in self.nodes:
                node_inst = self.nodes[node_key]
                if hasattr(node_inst, 'address'):
                    self.node_list.append(node_inst.address)

        if hasattr(self.poly, 'getNodesFromDb'):
            nodes_in_db = self.poly.getNodesFromDb() or []
            logging.debug(f'Scanning DB for extra nodes. Active: {assigned_addresses}')
            for node in nodes_in_db:
                addr = node.get('address')
                if addr and addr not in assigned_addresses:
                    logging.info(f'Removing orphaned node from DB: {node.get("name")} ({addr})')
                    self.poly.delNode(addr)

    def isnumber(self, string):
        try:
            float(string)
            return True
        except (ValueError, TypeError):
            return False

    def hubitat_events(self):
        """WebSocket event listener loop connecting to Hubitat /eventsocket."""
        if not WebSocket:
            logging.error('Lomond WebSocket not installed.')
            return

        maker_uri = getattr(self, 'maker_uri', '')
        if not maker_uri or 'http' not in maker_uri:
            logging.error('Cannot connect WebSocket: invalid maker_uri.')
            return

        parts = maker_uri.split('/')
        if len(parts) < 3:
            logging.error(f'Invalid maker_uri: {maker_uri}')
            return
        ws_uri = f'ws://{parts[2]}/eventsocket'
        logging.info(f'Connecting WebSocket to {ws_uri}')

        while True:
            try:
                websocket = WebSocket(ws_uri)
                for event in websocket:
                    if event.name == "text":
                        try:
                            payload = json.loads(event.text)
                            if payload.get('source') == 'DEVICE':
                                self.process_event(payload)
                        except Exception as e:
                            logging.error(f'Error parsing event: {e}')
                    elif event.name in ("closed", "disconnected"):
                        logging.warning('WebSocket disconnected, reconnecting in 5s...')
                        time.sleep(5)
                        break
            except Exception as e:
                logging.error(f'WebSocket error: {e}, reconnecting in 5s...')
                time.sleep(5)

    def process_event(self, event_data):
        """
        Declaratively routes a Hubitat Maker API live event to the matching node's drivers.
        """
        _deviceId = str(event_data.get('deviceId', ''))
        h_name = event_data.get('name')
        h_value = event_data.get('value')
        h_type = event_data.get('type')

        if not _deviceId or not h_name:
            return

        # Numeric string casting
        if isinstance(h_value, str) and self.isnumber(h_value):
            h_value = float(h_value) if '.' in h_value else int(h_value)

        # Date / Unix timestamp resolution
        unixtime = int(time.time())
        if 'date' in event_data:
            try:
                dt = datetime.strptime(event_data['date'], '%Y-%m-%dT%H:%M:%S%z')
                unixtime = int(dt.timestamp())
            except Exception:
                pass

        m_node = self.nodes.get(_deviceId)
        if not m_node:
            return

        logging.debug(f'Event: Device {_deviceId} [{h_name} = {h_value}]')

        # Routing table
        if h_name == 'switch':
            val = 100 if h_value == 'on' else (0 if h_value == 'off' else 99)
            m_node.my_setDriver('ST', val, 25)
            if hasattr(m_node, 'reportCmd'):
                m_node.reportCmd('DON' if val == 100 else 'DOF', 2)

        elif h_name == 'level':
            m_node.my_setDriver('OL', h_value, 51)

        elif h_name == 'motion':
            val = 100 if h_value == 'active' else 0
            # If node has GV5 (multi-sensor), use GV5; else use ST
            if any(d.get('driver') == 'GV5' for d in getattr(m_node, 'drivers', [])):
                m_node.my_setDriver('GV5', val, 25)
            else:
                m_node.my_setDriver('ST', val, 25)
            if hasattr(m_node, 'reportCmd'):
                m_node.reportCmd('DON' if val == 100 else 'DOF', 2)

        elif h_name == 'contact':
            val = 100 if h_value == 'open' else 0
            if any(d.get('driver') == 'GV6' for d in getattr(m_node, 'drivers', [])):
                m_node.my_setDriver('GV6', val, 25)
            else:
                m_node.my_setDriver('ST', val, 25)
            if hasattr(m_node, 'reportCmd'):
                m_node.reportCmd('DON' if val == 100 else 'DOF', 2)

        elif h_name == 'battery':
            m_node.my_setDriver('BATLVL', h_value, 51)

        elif h_name == 'temperature':
            uom = 17 if self.temp_unit == 'F' else 4
            m_node.my_setDriver('CLITEMP', h_value, uom)

        elif h_name == 'humidity':
            m_node.my_setDriver('CLIHUM', h_value, 22)

        elif h_name == 'power':
            m_node.my_setDriver('GV2', h_value, 73)
            m_node.my_setDriver('CPW', h_value, 73)

        elif h_name == 'energy':
            m_node.my_setDriver('GV3', h_value, 33)
            m_node.my_setDriver('TPW', h_value, 33)

        elif h_name == 'illuminance':
            m_node.my_setDriver('LUMIN', h_value, 36)

        elif h_name == 'colorMode':
            val = 1 if h_value == 'CT' else (2 if h_value == 'RGB' else 0)
            m_node.my_setDriver('GV5', val, 25)

        elif h_name == 'colorTemperature':
            m_node.my_setDriver('GV0', h_value, 26)
            m_node.my_setDriver('GV6', h_value, 26)

        elif h_name == 'hue':
            m_node.my_setDriver('GV1', h_value, 56)
            m_node.my_setDriver('GV3', h_value, 56)

        elif h_name == 'saturation':
            m_node.my_setDriver('GV2', h_value, 100)
            m_node.my_setDriver('GV4', h_value, 100)

        elif h_name == 'lock':
            val = 100 if h_value == 'locked' else 0
            m_node.my_setDriver('ST', val, 25)

        elif h_name in ('pushed', 'held', 'doubleTapped'):
            btn_val = int(h_value) if self.isnumber(h_value) else 1
            if h_name == 'pushed':
                m_node.my_setDriver('GV4', btn_val, 57)
                m_node.my_setDriver('GV7', btn_val, 57)
            elif h_name == 'held':
                m_node.my_setDriver('GV5', btn_val, 57)
                m_node.my_setDriver('GV8', btn_val, 57)
            elif h_name == 'doubleTapped':
                m_node.my_setDriver('GV6', btn_val, 57)
                m_node.my_setDriver('GV9', btn_val, 57)
            if hasattr(m_node, 'reportCmd'):
                m_node.reportCmd('DON', 2)

        elif h_name in ('radonShortTermAvg', 'radon'):
            if isinstance(h_value, (int, float)):
                val_pci = round(h_value / 37.0, 1)
                m_node.my_setDriver('RADON', val_pci, 124)
                avg_24h = self.update_radon_long(_deviceId, val_pci)
                m_node.my_setDriver('ST', avg_24h, 124)

        elif h_name == 'co2':
            m_node.my_setDriver('CO2LVL', h_value, 54)

        elif h_name in ('voc', 'vocLevel'):
            m_node.my_setDriver('VOCLVL', h_value, 54)

        elif h_name == 'pm25':
            m_node.my_setDriver('GV25', h_value, 122)

        elif h_name == 'pm1':
            m_node.my_setDriver('GV1', h_value, 122)

        elif h_name == 'pressure':
            m_node.my_setDriver('ATMPRES', h_value, 117)

        elif h_name == 'absHumidity':
            m_node.my_setDriver('GV0', h_value, 21)

        # Thermostat controls
        elif h_name == 'thermostatMode':
            mode_map = {'off': 0, 'heat': 1, 'cool': 2, 'auto': 3, 'emergency heat': 4}
            m_node.my_setDriver('CLIMD', mode_map.get(str(h_value).lower(), 99), 25)

        elif h_name == 'thermostatFanMode':
            fan_map = {'auto': 0, 'on': 1, 'circulate': 2}
            m_node.my_setDriver('CLIFRS', fan_map.get(str(h_value).lower(), 99), 25)

        elif h_name == 'thermostatOperatingState':
            state_map = {'idle': 0, 'heating': 1, 'cooling': 2, 'fan only': 3}
            m_node.my_setDriver('CLIFS', state_map.get(str(h_value).lower(), 99), 25)

        elif h_name == 'coolingSetpoint':
            uom = 17 if self.temp_unit == 'F' else 4
            m_node.my_setDriver('CLISPC', round(float(h_value) * 2.0) / 2, uom)

        elif h_name == 'heatingSetpoint':
            uom = 17 if self.temp_unit == 'F' else 4
            m_node.my_setDriver('CLISPH', round(float(h_value) * 2.0) / 2, uom)

    def remove_notices_all(self, command=None):
        if hasattr(self.poly, 'Notices') and hasattr(self.poly.Notices, 'clear'):
            self.poly.Notices.clear()

    def update_profile(self, command=None):
        logging.info('Manual update profile requested.')
        self.discover()

    commands = {
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile,
        'UPDATEPROFILE': update_profile,
        'REMOVE_NOTICES_ALL': remove_notices_all,
        'REMOVENOTICESALL': remove_notices_all,
    }


if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start({'version': version, 'requestId': True})
        polyglot.setCustomParamsDoc()
        control = Controller(polyglot, 'controller', 'controller', 'hubitat')
        polyglot.ready()
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        logging.error(f"Error starting Nodeserver: {traceback.format_exc()}")
        polyglot.stop()
        sys.exit(0)
