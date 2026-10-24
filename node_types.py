""" Node classes used by the Hubitat Node Server. """
import requests
import re
import time 
import json

try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    logging.basicConfig(level=logging.DEBUG)

class HubitatBase(udi_interface.Node):
    """ Base class for lights and groups """
    from udiLib import my_setDriver
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
        self.hubitatRefresh()

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
        elif cmd in ['SET_HUE', 'SETHUE']:
            h_cmd = 'setHue'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd in ['SET_SAT', 'SETSAT']:
            h_cmd = 'setSaturation'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd in ['SET_KELVIN', 'SETKELVIN']:
            h_cmd = 'setColorTemperature'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd in ['PUSH_BTN', 'PUSHBTN']:
            h_cmd = 'push'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd in ['HOLD_BTN', 'HOLDBTN']:
            h_cmd = 'hold'
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
            #requests.get(cmd_uri)
        elif cmd in ['RELEASE_BTN', 'RELEASEBTN']:
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
        logging.debug('hubitatRefresh {} => {}'.format(cmd_uri, r))
        while r.status_code != self.RESPONSE_OK:
            time.sleep(1)
            logging.error('Hubitat not responding - waiting for good response')
            r = requests.get(cmd_uri)

    def hubitatDirectCtrl(self, command, h_cmd):
        logging.debug('hubitatDirectCtrl: {} , {}'.format(command, h_cmd))
        h_cmd = h_cmd
        #cmd = command.get('cmd')
        val = command.get('value')
        device_id = command.get('address')
        _raw_uri = self.maker_uri.split('?')
        _raw_http = _raw_uri[0].replace('all', device_id)
        cmd_ok = True
        if val != None and val != '':
            cmd_uri = _raw_http + '/' + h_cmd + '/' + val + '?' + _raw_uri[1]
        else:
            cmd_uri = _raw_http + '/' + h_cmd + '?' + _raw_uri[1]
        logging.debug('hubitatDirectCtrl URI: {}'.format(cmd_uri ))
        if cmd_ok:
            r = requests.get(cmd_uri)
            while r.status_code!= self.RESPONSE_OK:
                time.sleep(1)
                logging.error('Hubitat not responding - waiting for good response')
                r = requests.get(cmd_uri)
"""
New Class definitions for generalization
"""
class StdLampNode(HubitatBase):
    from udiLib import my_setDriver
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('StdLampNode Init')
        HubitatBase.hubitatRefresh(self)

    def start(self):
        pass

    def setOn(self, command = None):
        self.node.setDriver('ST', 1)
        self.node.reportCmd('DON')

    def setOff(self, command = None ):
        self.node.setDriver('ST', 0)
        self.node.reportCmd('DOF')

    def query(self):
        HubitatBase.hubitatRefresh(self)

    def set_level (self, command):
        logging.debug('StdLampNode set_level : {}'.format(command.get('value')))
        cmd = command
        cmd['value'] = str(command.get('value'))
        HubitatBase.hubitatDirectCtrl(self, cmd, 'setLevel')
        #self.node.reportCmd('OL', command.get('value'))

    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'OL', 'value': 75, 'uom': 51, 'name': 'On Level'}
    ]
    id = 'STDLAMP'
    commands = {
        'DON': HubitatBase.hubitatCtl, 
        'DOF': HubitatBase.hubitatCtl, 
        'QUERY': query,
        'SETLVL': set_level
    }


class RgbLampNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('RgbLampNode Init')
        HubitatBase.hubitatRefresh(self)

    def start(self):
        pass

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'OL', 'value': 0, 'uom': 51, 'name': 'On Level'},
        {'driver': 'GV3', 'value': 0, 'uom': 56, 'name': 'Hue'},
        {'driver': 'GV4', 'value': 0, 'uom': 100, 'name': 'Saturation'},
        {'driver': 'GV5', 'value': 0, 'uom': 25, 'name': 'Color Mode'},
        {'driver': 'GV6', 'value': 0, 'uom': 26, 'name': 'Color Temperature'}
    ]

    id = 'COLORLIGHT'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query,
        'SETLVL': HubitatBase.hubitatCtl, 'SET_HUE': HubitatBase.hubitatCtl, 'SETHUE': HubitatBase.hubitatCtl,
        'SET_SAT': HubitatBase.hubitatCtl, 'SETSAT': HubitatBase.hubitatCtl, 'SET_KELVIN': HubitatBase.hubitatCtl, 'SETKELVIN': HubitatBase.hubitatCtl
    }


class CtLampNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('CtLampNode Init')
        HubitatBase.hubitatRefresh(self)

    def start(self):
        pass

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'OL', 'value': 0, 'uom': 51, 'name': 'On Level'},
        {'driver': 'GV6', 'value': 0, 'uom': 26, 'name': 'Color Temperature'}
    ]

    id = 'COLORLIGHT'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query,
        'SETLVL': HubitatBase.hubitatCtl, 'SET_KELVIN': HubitatBase.hubitatCtl, 'SETKELVIN': HubitatBase.hubitatCtl
    }


class EnergyOutletNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('EnergyOutletNode Init')
        HubitatBase.hubitatRefresh(self)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'CC', 'value': 0, 'uom': 1, 'name': 'Current (Amps)'},
        {'driver': 'CPW', 'value': 0, 'uom': 73, 'name': 'Power (Watts)'},
        {'driver': 'CV', 'value': 0, 'uom': 72, 'name': 'Voltage'},
        {'driver': 'TPW', 'value': 0, 'uom': 33, 'name': 'Total Power Used (energy)'},
        {'driver': 'GV0', 'value': 0, 'uom': 73, 'name': 'Current High'},
        {'driver': 'GV1', 'value': 0, 'uom': 73, 'name': 'Current Low'},
        {'driver': 'GV2', 'value': 0, 'uom': 33, 'name': 'Power High'},
        {'driver': 'GV3', 'value': 0, 'uom': 33, 'name': 'Power Low'},
        {'driver': 'GV4', 'value': 0, 'uom': 72, 'name': 'Voltage High'},
        {'driver': 'GV5', 'value': 0, 'uom': 72, 'name': 'Voltage Low'},
        {'driver': 'GV6', 'value': 0, 'uom': 45, 'name': 'Duration'}
    ]
    id = 'ENERGYOUTLET'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }


class OutletNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('OutletNode Init')
        HubitatBase.hubitatRefresh(self)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
    ]
    id = 'OUTLET'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }


class SwitchNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('SwitchNode Init')
        HubitatBase.hubitatRefresh(self)

    def start(self):
        pass
    #     self.node.setDriver('ST', 0)

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [{'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'}]
    id = 'SWITCH'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }



class DimmerNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('DimmerNode Init')
        HubitatBase.hubitatRefresh(self)

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
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Status'},
        {'driver': 'OL', 'value': 75, 'uom': 51, 'name': 'On Level'}
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
        logging.debug('MultiSensorTHLA Init')
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'CLIHUM', 'value': 0, 'uom': 22, 'name': 'Humidity'},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36, 'name': 'Illuminance'},
        {'driver': 'ALARM', 'value': 0, 'uom': 2, 'name': 'Tamper Alarm'}
    ]
    id = 'MSTHLASENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorTLAS(polyinterface.Node):
class MultiSensorTLAS (HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('MultiSensorTLAS Init')
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36, 'name': 'Illuminance'},
        {'driver': 'ALARM', 'value': 0, 'uom': 2, 'name': 'Tamper Alarm'},
        {'driver': 'SPEED', 'value': 0, 'uom': 2, 'name': 'Acceleration'}
    ]
    id = 'MSTLASSENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorTH(polyinterface.Node):
class MultiSensorTH(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('MultiSensorTH Init')
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'CLIHUM', 'value': 0, 'uom': 22, 'name': 'Humidity'},
    ]
    id = 'MSTHSENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorT(polyinterface.Node):
class MultiSensorT(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('MultiSensorT Init')
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'}
    ]
    id = 'MSTSENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorTL(polyinterface.Node):
class MultiSensorTL(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('MultiSensorTL Init')
        HubitatBase.hubitatRefresh(self)
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36, 'name': 'Illuminance'},
    ]
    id = 'MSTLSENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MultiSensorL(polyinterface.Node):
class MultiSensorL(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('MultiSensorL Init')
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
        {'driver': 'LUMIN', 'value': 0, 'uom': 36, 'name': 'Illuminance'},
    ]
    id = 'MSLSENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


#class MotionSensor(polyinterface.Node):
class MotionSensor(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('MotionSensor Init')
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
    ]
    id = 'MSSENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }


class LutronPicoNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('LutronPicoNode Init')
        HubitatBase.hubitatRefresh(self)

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
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': 'Status'},
        {'driver': 'GV7', 'value': 0, 'uom': 25, 'name': 'Button'},
        {'driver': 'GV8', 'value': 0, 'uom': 25, 'name': 'Released'},
        {'driver': 'GV9', 'value': 0, 'uom': 25, 'name': 'Held'}
    ]
    id = 'PICONODE'
    commands = {
        # 'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }


class LutronFastPicoNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('LutronFastPicoNode Init')
        HubitatBase.hubitatRefresh(self)
    def start(self):
        pass

    def setOn(self, command):
        self.node.setDriver('ST', 100)

    def setOff(self, command):
        self.node.setDriver('ST', 0)

    def query(self):
        self.reportDrivers()

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': 'Status'},
        {'driver': 'GV7', 'value': 0, 'uom': 25, 'name': 'Pushed'},
        {'driver': 'GV8', 'value': 0, 'uom': 25, 'name': 'Released'},
        {'driver': 'GV9', 'value': 0, 'uom': 25, 'name': 'Held'}
    ]
    id = 'FASTPICONODE'
    commands = {
        # 'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }

class THSensor(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('THSensor Init')
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'CLIHUM', 'value': 0, 'uom': 22, 'name': 'Humidity'},
    ]
    id = 'THSENSOR'
    commands = {
        # 'DON': setOn, 'DOF': setOff
    }

class ContactNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('ContactNode Init')
        HubitatBase.hubitatRefresh(self)

    def query(self):
        HubitatBase.hubitatRefresh(self)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 79, 'name': 'Status'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51, 'name': 'Battery'}
    ]
    id = 'CONTACTSENSOR'
    commands = {
        'DON': HubitatBase.hubitatCtl, 'DOF': HubitatBase.hubitatCtl, 'QUERY': query
    }

#############
#   Newly added devices
###############
    

class SimpleRemoteNode(HubitatBase):
    def __init__(self, polyglot, primary, address, name, marker_uri):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('SimpleRemoteNode Init')
        HubitatBase.hubitatRefresh(self)

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
        {'driver': 'ST', 'value': 0, 'uom': 78, 'name': 'Status'},
        {'driver': 'GV7', 'value': 0, 'uom': 25, 'name': 'Pushed'},
        {'driver': 'GV8', 'value': 0, 'uom': 25, 'name': 'Released'},
        {'driver': 'GV9', 'value': 0, 'uom': 25, 'name': 'Held'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 51, 'name': 'Battery Level'},
        {'driver': 'GV20', 'value': 99, 'uom': 25, 'name': 'Device Status'},
    ]
    id = 'REMOTEBTNNODE'
    commands = {
        'PUSH_BTN': HubitatBase.hubitatCtl, 'PUSHBTN': HubitatBase.hubitatCtl, 'HOLD_BTN': HubitatBase.hubitatCtl, 'HOLDBTN': HubitatBase.hubitatCtl, 'RELEASE_BTN': HubitatBase.hubitatCtl, 'RELEASEBTN': HubitatBase.hubitatCtl, 'QUERY': query
    }


class EcobeeSensor(HubitatBase):
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Motion Detection'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},        
        {'driver': 'GV20', 'value': 99, 'uom': 25, 'name': 'Device Status'}
    ] 
    id = 'ECOBSENSOR'

    def __init__(self, polyglot, primary, address, name, marker_uri, dev):
        #def __init__(self, polyglot, primary, marker_uri, dev):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('EcobeeSensor Init')
        self.poly = polyglot
        time.sleep(1)
        self.dev_info = dev
        logging.debug('EcobeeSensor dev info: {}'.format(dev))
        HubitatBase.hubitatRefresh(self)
 
        
        try:
            self.t_unit = dev['attributes']['deviceTemperatureUnit']
        except:
            self.t_unit = 1

    def query(self):
        HubitatBase.hubitatRefresh(self)

    commands = {  'QUERY': query   }

    
class AirThingsSensor(HubitatBase):    
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': '24H Longterm Radon Level'},
        {'driver': 'RADON', 'value': 99, 'uom': 25, 'name': 'Current Radon Reading'},
        {'driver': 'CLITEMP', 'value': 99, 'uom': 25, 'name': 'Temperature'},
        {'driver': 'CLIHUM', 'value': 99, 'uom': 25, 'name': 'Relative Humidity'},
        {'driver': 'GV0', 'value': 99, 'uom': 25, 'name': 'Absolute Humidity'},
        {'driver': 'ATMPRES', 'value': 99, 'uom': 25, 'name': 'Atmospheric Pressure'},
        {'driver': 'CO2LVL', 'value': 99, 'uom': 25, 'name': 'CO2 level'},
        {'driver': 'AQI', 'value': 99, 'uom': 25, 'name': 'Air Quality Index'},
        {'driver': 'VOCLVL', 'value': 99, 'uom': 25, 'name': 'VOC level'},
        {'driver': 'GV2', 'value': 99, 'uom': 25, 'name': 'VOC state'},
        {'driver': 'GV25', 'value': 99, 'uom': 25, 'name': '2.5 ppm particle count'},
        {'driver': 'GV1', 'value': 99, 'uom': 25, 'name': '1 ppm particle count'},
        {'driver': 'BATLVL', 'value': 99, 'uom': 25, 'name': 'Battery Level'},
        {'driver': 'TIME', 'value': int(time.time()), 'uom': 151, 'name': 'Last Update Time'},
        {'driver': 'GV20', 'value': 99, 'uom': 25, 'name': 'Device Status'},
    ]

    id = 'AIRTHSENSOR'
    def __init__(self, polyglot, primary,address, name, marker_uri, dev):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('AirThingsSensor Init')
        self.poly = polyglot
        self.dev_info = dev

        if dev['temp_unit'] == 'F':
            self.id = 'AIRTHSENSORF'

    def updateAirthingData(self, command):
        logging.debug('updateAirthingData')
        HubitatBase.hubitatRefresh(self)

    commands = {'QUERY'     : updateAirthingData,

                }
    
class EcobeeSensor(HubitatBase):
    drivers = [
        {'driver': 'ST', 'value': 99, 'uom': 25, 'name': 'Motion Detection'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},        
        {'driver': 'GV20', 'value': 99, 'uom': 25, 'name': 'Device Status'}
    ] 
    id = 'ECOBSENSOR'

    def __init__(self, polyglot, primary, address, name, marker_uri, dev):
        #def __init__(self, polyglot, primary, marker_uri, dev):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('EcobeeSensor Init')
        self.poly = polyglot
        time.sleep(1)
        self.dev_info = dev
        logging.debug('EcobeeSensor dev info: {}'.format(dev))
        HubitatBase.hubitatRefresh(self)
 
        
        try:
            self.t_unit = dev['attributes']['deviceTemperatureUnit']
        except:
            self.t_unit = 1

    def query(self):
        HubitatBase.hubitatRefresh(self)

    commands = {  'QUERY': query   }    
class EcobeeThermostat(HubitatBase):
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 25, 'name': 'State'},
        {'driver': 'CLITEMP', 'value': 0, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'CLIHUM', 'value': 0, 'uom': 22, 'name': 'Humidity'},
        {'driver': 'CLIFS', 'value': 99, 'uom': 25, 'name': 'Fan Operating Mode'},
        {'driver': 'CLIMD', 'value': 99, 'uom': 25, 'name': 'Thermostat Operating Mode'},
        {'driver': 'CLISPC', 'value': 90, 'uom': 17, 'name': 'Cooling setpoint'},
        {'driver': 'CLISPH', 'value': 50, 'uom': 17, 'name': 'Heating setpoint'},
        {'driver': 'CLIHCS', 'value': 99, 'uom': 25, 'name': 'Thermostat state'},
        {'driver': 'CLIFRS', 'value': 99, 'uom': 25, 'name': 'Fan State'},
        {'driver': 'GV19', 'value': 99, 'uom': 25, 'name': 'Supported Modes'},
        {'driver': 'GV20', 'value': 99, 'uom': 25, 'name': 'Device Status'},
    ]

    id = 'ECOBTSTAT'
    
    def __init__(self, polyglot, primary,address, name, marker_uri, dev):
        super().__init__(polyglot, primary, address, name, marker_uri)
        logging.debug('EcobeeThermostat Init')
        self.poly = polyglot
        self.dev_info = dev
        thtype = 99
        logging.debug('EcobeeThermostat dev info: {}'.format(dev))
        self.hereawayState = 99
        #self.node.setDriver('CLISMD', self.hereawayState  )
        try:
            thmode = str(dev['attributes']['supportedThermostatModes'])
            logging.debug('thmode : {}'.format(thmode))
            
            thmodes = ['off']
            if 'heat' in thmode:
                thmodes.append('heat')
            if 'cool' in thmode:
                thmodes.append('cool')
            if 'auto' in thmode:
                thmodes.append('auto')
            logging.debug('thmodes : {}'.format(thmodes))

            if len(thmodes) == 2:
                if 'heat' in thmodes:
                    thtype = 0
                elif 'cool' in thmodes:
                    thtype = 1
                elif 'auto' in thmodes:
                    thtype = 2
            elif len(thmodes) == 3:
                thtype = 3
            elif len(thmodes) == 4:
                thtype = 4
            else:
                thtype = 99

    
            self.t_unit = dev['attributes']['deviceTemperatureUnit']
        except Exception as e:
            logging.error('not able to determine type {}'.format(e))
            self.t_unit = 1
            thtype = 99

        self.node.setDriver('GV19', thtype)
        HubitatBase.hubitatRefresh(self)
        
    def query(self):
        HubitatBase.hubitatRefresh(self)


    def setOperationMode(self, command):        
        logging.debug('setOperationMode')
        cmd = command
        if int(command.get('value')) == 0:
            cmd['value'] = ''
            HubitatBase.hubitatDirectCtrl(self, cmd, 'auto')
        elif int(command.get('value')) == 1:
            cmd['value'] = ''
            HubitatBase.hubitatDirectCtrl(self, cmd, 'cool')
        elif int(command.get('value')) == 2:
            cmd['value'] = ''
            HubitatBase.hubitatDirectCtrl(self, cmd, 'heat')
        elif int(command.get('value')) == 3:
            cmd['value'] = ''
            HubitatBase.hubitatDirectCtrl(self, cmd, 'off')   
        time.sleep(1)
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')


    def setThermostatMode(self, command):
        logging.debug('setTHermostatMode')
        '''
        CLIHCS-0 = Auto
        CLIHCS-1 = Cool
        CLIHCS-2 = Heat
        ---
        CLIHCS-3 = Off
        ----
        CLIHCS-4 = Idle
        ----
        CLIHCS-5 = Emergency Heat
        CLIHCS-99 = Unknown
        '''

        cmd = command
        if int(command.get('value')) == 0:
            cmd['value'] = 'auto'
            HubitatBase.hubitatDirectCtrl(self, cmd, 'setThermostatMode')
            #HubitatBase.hubitatDirectCtrl(cmd, 'auto')

        elif int(command.get('value')) == 1:
            cmd['value'] = 'cool'
            HubitatBase.hubitatDirectCtrl(self, cmd, 'setThermostatMode')
        elif int(command.get('value')) == 2:
            cmd['value'] = 'heat'
            HubitatBase.hubitatDirectCtrl(self, cmd, 'setThermostatMode')
        elif int(command.get('value')) == 3:
            cmd['value'] = 'off' 
            HubitatBase.hubitatDirectCtrl(self, cmd, 'setThermostatMode')
        else:
            logging.error('setThermostatMode unexpected command: {}'.format(command.get('value') ))           
        time.sleep(3)
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')        


    def setFanMode(self, command):
        logging.debug('setFanMode')
        '''
        CLIHCS-0 = On
        CLIHCS-1 = Auto
        CLIHCS-2 = Circulate
        '''
        cmd = command
        if int(command.get('value')) == 0:
            cmd['value'] = 'on'   
            HubitatBase.hubitatDirectCtrl(self, cmd, 'setThermostatFanMode')         
        elif int(command.get('value')) == 1:
            cmd['value'] = 'auto'
            HubitatBase.hubitatDirectCtrl(self, cmd, 'setThermostatFanMode')
        elif int(command.get('value')) == 2:
            cmd['value'] = 'circulate'
            HubitatBase.hubitatDirectCtrl(self, cmd, 'setThermostatFanMode')
        else:
            logging.error('setFanMode unexpected command: {}'.format(command.get('value') ))           
        time.sleep(1)
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')        

    def setHeatPoint(self, command):
        logging.debug('setHeatPoint : {}'.format(command))
        
        cmd = command#query = command.get("query")
        unit = command.get('uom')
        set_temp = command.get('value')
        cmd['value'] = str(set_temp)
        HubitatBase.hubitatDirectCtrl(self, cmd, 'setHeatingSetpoint')
        time.sleep(1)
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')

    def setResume(self, command):

        logging.debug('setResume')
        cmd = command
        HubitatBase.hubitatDirectCtrl(self, cmd, 'resumeProgram')
        time.sleep(1)
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')

    def setAway(self, command):
        logging.debug('setAway')
        cmd = command
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'setAway')
        time.sleep(1)
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')

    def setCoolPoint(self, command):
        logging.debug('setCoolPoint : {}'.format(command)) 
        cmd = command
        unit = command.get('uom')
        set_temp = str(command.get('value'))
        cmd['value'] = set_temp     
        HubitatBase.hubitatDirectCtrl(self, cmd, 'setCoolingSetpoint')
        time.sleep(1)
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')

    def setTempUnit(self, t_unit):
        logging.debug('setTempUnit')
        if t_unit.lower()  == 'c':
            self.t_unit = 'C'
        elif t_unit.lower()  == 'f':
            self.t_unit = 'F'
        else:
            logging.error('Unknow temp unit: {}'.format(t_unit))

    def updateThermostat(self, command):
        cmd = command
        cmd['value'] = ''
        HubitatBase.hubitatDirectCtrl(self, cmd, 'refresh')


    commands = {'QUERY'     : updateThermostat,
                'FANMODE'   : setFanMode,
                'TSTATMODE' : setThermostatMode,
                'AWAY'      : setAway,
                'RESUME'    : setResume,
                'HEATPOINT' : setHeatPoint,  
                'COOLPOINT' : setCoolPoint
                }
    

