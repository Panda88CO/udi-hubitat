""" Node classes used by the Hubitat Node Server. """
import requests
import re
import time 

try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG)

class HubitatBase(udi_interface.Node):
    """ Base class for lights and groups """
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name)
        self.RESPONSE_OK = 200
        self.RESPONSE_NO_SUPPORT = 400
        self.RESPONSE_NO_RESPONSE = 404
        self.RESPONSE_SERVER_ERROR = 500
        self.poly = polyglot
        self.name = self.getValidName(name)
        self.address = self.getValidAddress(address)
        self.primary = primary
        self.maker_uri = marker_uri
        self.n_queue = []
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)


        self.poly.ready()
        self.poly.addNode(self)
        self.wait_for_node_done()
        self.node = self.poly.getNode(address)
        logging.debug('self.node : {}'.format(self.node ))
        # self.st = None
        #self.maker_uri = polyglot.Parameters['maker_uri']
        #logging.debug('maker_uri: {}'.format(self.maker_uri))

    def getValidName(self, name):
        name = bytes(name, 'utf-8').decode('utf-8','ignore')
        return re.sub(r"[^A-Za-z0-9_ ]", "", name)

    # remove all illegal characters from node address
    def getValidAddress(self, name):
        name = bytes(name, 'utf-8').decode('utf-8','ignore')
        tmp = re.sub(r"[^A-Za-z0-9_]", "", name.lower())
        logging.debug('getValidAddress {}'.format(tmp))
        return tmp[:14]
    
    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
            logging.debug('wait_for_node_done')
        self.n_queue.pop()


    """ Basic On/Off controls """
    def hubitatCtl(self, command):
        h_cmd = None
        cmd = command.get('cmd')
        val = command.get('value')
        device_id = command.get('address')
        _raw_uri = self.maker_uri.split('?')
        _raw_http = _raw_uri[0].replace('all', device_id)
        cmd_ok = True
        # print('debug------------------')
        # print(command.keys())
        # print(self.maker_uri)
        # print(self.name)
        # print(cmd)
        # print(val)
        # print(device_id)

        if cmd in ['DON', 'DFON']:
            h_cmd = 'on'
            cmd_uri = _raw_http + '/' + h_cmd + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
            # val = command.get('value')
            # print(cmd_uri)
        elif cmd in ['DOF', 'DFOF']:
            h_cmd = 'off'
            cmd_uri = _raw_http + '/' + h_cmd + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
            # val = command.get('value')
            # print(cmd_uri)
        elif cmd == 'SETLVL':
            h_cmd = 'setLevel'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd == 'SET_HUE':
            h_cmd = 'setHue'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd == 'SET_SAT':
            h_cmd = 'setSaturation'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd == 'SET_KELVIN':
            h_cmd = 'setColorTemperature'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd == 'PUSH_BTN':
            h_cmd = 'push'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd == 'HOLD_BTN':
            h_cmd = 'hold'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd == 'RELEASE_BTN':
            h_cmd = 'release'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)                                                
        

        # if h_cmd == 'on':
        #     r = requests.get(cmd_uri)
        #     if r.status_code == 200:
        #         self.node.setDriver('ST', 100)
        # elif h_cmd == 'off':
        #     r = requests.get(cmd_uri)
        #     if r.status_code == 200:
        #         self.node.setDriver('ST', 0)
        else:
            logging.error('unsupported command; {} , {}'.format(cmd, val))
            cmd_ok = False

        if cmd_ok:
            r = requests.get(cmd_uri)
            while r.status_code!= self.RESPONSE_OK:
                time.sleep(1)
                logging.error('Hubitat not responding - waiting for good response')
                r = requests.get(cmd_uri)
                # print(r.status_code)
            # print(r.status_code)
        # print('debug------------------')

    def hubitatRefresh(self):
        device_id = self.address
        _raw_uri = self.maker_uri.split('?')
        _raw_http = _raw_uri[0].replace('all', device_id)

        h_cmd = 'refresh'
        cmd_uri = _raw_http + '/' + h_cmd + '?' + _raw_uri[1]
        r = requests.get(cmd_uri)
        while r.status_code != self.RESPONSE_OK:
            time.sleep(1)
            logging.error('Hubitat not responding - waiting for good response')
            r = requests.get(cmd_uri)


"""
New Class definitions for generalization
"""
class StdLampNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'OL', 'value': 0, 'uom': 51}
    ]
    id = 'STD_LAMP'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query,
        'SETLVL': HubitatBase.hubitatCtl
    }


class RgbLampNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'OL', 'value': 0, 'uom': 51},
        {'driver': 'GV3', 'value': 0, 'uom': 56},
        {'driver': 'GV4', 'value': 0, 'uom': 100},
        {'driver': 'GV5', 'value': 0, 'uom': 25},
        {'driver': 'GV6', 'value': 0, 'uom': 26}
    ]

    id = 'COLOR_LIGHT'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query,
        'SETLVL': HubitatBase.hubitatCtl, 'SET_HUE': HubitatBase.hubitatCtl,
        'SET_SAT': HubitatBase.hubitatCtl, 'SET_KELVIN': HubitatBase.hubitatCtl
    }


class CtLampNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'OL', 'value': 0, 'uom': 51},
        {'driver': 'GV6', 'value': 0, 'uom': 26}
    ]

    id = 'COLOR_LIGHT'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query,
        'SETLVL': HubitatBase.hubitatCtl, 'SET_KELVIN': HubitatBase.hubitatCtl
    }


class EnergyOutletNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},  # Status
        {'driver': 'CC', 'value': 0, 'uom': 1},  # Current - (Amps)
        {'driver': 'CPW', 'value': 0, 'uom': 73},  # Current Power Used (Watts)
        {'driver': 'CV', 'value': 0, 'uom': 72},  # Current Voltage
        {'driver': 'TPW', 'value': 0, 'uom': 33},  # Total Power Used (energy)
        {'driver': 'GV0', 'value': 0, 'uom': 73},  # currentH
        {'driver': 'GV1', 'value': 0, 'uom': 73},  # currentL
        {'driver': 'GV2', 'value': 0, 'uom': 33},  # powerH
        {'driver': 'GV3', 'value': 0, 'uom': 33},  # powerL
        {'driver': 'GV4', 'value': 0, 'uom': 72},  # voltageH
        {'driver': 'GV5', 'value': 0, 'uom': 72},  # voltageL
        {'driver': 'GV6', 'value': 0, 'uom': 45}  # energy duration
    ]
    id = 'ENERGY_OUTLET'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }


class OutletNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},  # Status
    ]
    id = 'OUTLET'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }


class SwitchNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass
    #     self.node.setDriver('ST', 0)

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [{'driver': 'ST', 'value': 0, 'uom': 78}]
    id = 'SWITCH'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }

class SimpleRemoteNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass
    #     self.node.setDriver('ST', 0)

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [ {'driver': 'ST', 'value': 0, 'uom': 78},
                {'driver': 'GV7', 'value': 0, 'uom': 25},
                {'driver': 'GV8', 'value': 0, 'uom': 25},
                {'driver': 'GV9', 'value': 0, 'uom': 25},
                {'driver': 'BATLVL', 'value': 0, 'uom': 51},
                ]
    id = 'remotebtnnnode'
    commands = {
        'PUSH_BTN': HubitatBase.hubitatCtl, 'HOLD_BTN': HubitatBase.hubitatCtl, 'RELEASE_BTN': HubitatBase.hubitatCtl, 'QUERY': query
    }



class DimmerNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass
    #     self.node.setDriver('ST', 0)

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'OL', 'value': 0, 'uom': 51}
    ]
    id = 'DIMMER'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query,
        'SETLVL': HubitatBase.hubitatCtl
    }


#class MultiSensorTHLA(polyinterface.Node):
class MultiSensorTHLA(HubitatBase):

    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)



    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17},
        {'driver': 'CLIHUM', 'value': 0, 'uom': 22},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36},
        {'driver': 'ALARM', 'value': 0, 'uom': 2}
    ]
    id = 'MSTHLA_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorTLAS(polyinterface.Node):
class MultiSensorTLAS (HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36},
        {'driver': 'ALARM', 'value': 0, 'uom': 2},
        {'driver': 'SPEED', 'value': 0, 'uom': 2}
    ]
    id = 'MSTLAS_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorTH(polyinterface.Node):
class MultiSensorTH(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17},
        {'driver': 'CLIHUM', 'value': 0, 'uom': 22},
    ]
    id = 'MSTH_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorT(polyinterface.Node):
class MultiSensorT(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17}
    ]
    id = 'MST_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorTL(polyinterface.Node):
class MultiSensorTL(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36},
    ]
    id = 'MSTL_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorL(polyinterface.Node):
class MultiSensorL(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36},
    ]
    id = 'MSL_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MotionSensor(polyinterface.Node):
class MotionSensor(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
    ]
    id = 'MS_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


class LutronPicoNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass
    #     self.node.setDriver('ST', 0)

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        self.reportDrivers()

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2},
        {'driver': 'GV7', 'value': 0, 'uom': 25},
        {'driver': 'GV8', 'value': 0, 'uom': 25},
        ]
    id = 'piconode'
    commands = {
        # 'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }


class LutronFastPicoNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def start(self):
        pass

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        self.reportDrivers()

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2},
        {'driver': 'GV7', 'value': 0, 'uom': 25},
        {'driver': 'GV8', 'value': 0, 'uom': 25}
    ]
    id = 'fastpiconode'
    commands = {
        # 'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }

class THSensor(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17},
        {'driver': 'CLIHUM', 'value': 0, 'uom': 22},
    ]
    id = 'TH_SENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }

class ContactNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 79},  # Status
    ]
    id = 'CONTACT_SENSOR'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }