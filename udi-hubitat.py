#!/usr/bin/env python3

#try:
#    import polyinterface
#except ImportError:
#    import pgc_interface as polyinterface


import udi_interface
logging = udi_interface.LOGGER
Custom = udi_interface.Custom

from datetime import datetime
import sys
import time
import requests
import traceback
import json
from lomond import WebSocket
import node_types
version = '0.1.13'
#LOGGER = polyinterface.LOGGER

class Controller(udi_interface.Node):
    from udiLib import my_setDriver
    def __init__(self, polyglot, primary, address, name):

        self.RESPONSE_OK = 200
        self.RESPONSE_NO_SUPPORT = 400
        self.RESPONSE_NO_RESPONSE = 404
        self.RESPONSE_SERVER_ERROR = 500

        self.poly = polyglot
        self.primary = primary
        self.address = address
        self.name = name
        self.id = 'controller'
        logging.setLevel(10)
        self.drivers = [{'driver': 'ST', 'value': 1, 'uom': 2}]
        self.node_list = []
        self.hb = 0
        self.Parameters = Custom(self.poly, 'customparams')
        self.Notices = Custom(self.poly, 'notices')
        self.configDone = False
        self.n_queue = []
        self.poly.subscribe(self.poly.STOP, self.stopHandler)
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.customParamsHandler)
        self.poly.subscribe(self.poly.CONFIGDONE, self.configDoneHandler)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

        self.poly.addNode(self)
        self.node = self.poly.getNode(self.address)
        self.debug_enabled = True
        self.poly.updateProfile()
        self.poly.ready()
        self.temp_unit= 'F'
        self.EcoBee_t_unit = 'F'
        self.device_list = {}
        self.airth_radon_readings = {}

    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()



    #def shortPoll(self):
    #    pass

    #def longPoll(self):
    #    pass
    def heartbeat(self):
        logging.debug('heartbeat: ' + str(self.hb))
        
        if self.hb == 0:
            self.reportCmd('DON',2)
            self.hb = 1
        else:
            self.reportCmd('DOF',2)
            self.hb = 0

    def start(self):
        logging.info('Started Hubitat')
        self.my_setDriver('ST', 1)
        # Remove all existing notices
        self.poly.Notices.clear()
        while not self.configDone:
            time.sleep(10)
            logging.info('Waiting for confuguration to complete')
        #self.removeNoticesAll()
        self.discover()
        self.hubitat_events()


    def stopHandler(self):
        # Set nodes offline
        self.my_setDriver('ST', 0)
        #self.node.setOffline()
        self.poly.stop()



    def configDoneHandler(self):
        # We use this to discover devices, or ask to authenticate if user has not already done so
        self.poly.Notices.clear()
        self.configDone = True


    def query(self):
        for node in self.nodes:
            self.nodes[node].reportDrivers()


    def customParamsHandler(self, userParams):
        self.Parameters.load(userParams)
        logging.debug('customParamsHandler called')
        default_maker_uri = 'http://<IP_ADDRESS>/apps/api/<APP_ID>/devices/all?access_token=<TOKEN>'
        self.maker_uri = default_maker_uri

        if 'maker_uri' in userParams:
            self.maker_uri = userParams['maker_uri']
            if self.maker_uri != default_maker_uri:
                maker_st = True
            else:
                maker_st = False
        else:
            logging.error('Hubitat Maker API URL is not defined in configuration')
            maker_st = False

        if 'debug_enabled' in userParams:
            debug_enabled = userParams['debug_enabled']
            if debug_enabled == "true" or debug_enabled == "True":
                self.debug_enabled = True
            else:
                self.debug_enabled = False

        if self.maker_uri == default_maker_uri:
            self.poly.Notices['maker_uri'] = 'Please set proper Hubitat and Maker API URI, and restart this NodeServer'

        if 'temp_unit' in userParams:
            temp_unit = userParams['temp_unit']
            if temp_unit[0] == "C" or temp_unit[0] == "c":
                 self.temp_unit= 'C'
            else:
                self.temp_unit= 'F'
    '''
    def check_params(self):
        default_maker_uri = 'http://<IP_ADDRESS>/apps/api/<APP_ID>/devices/all?access_token=<TOKEN>'
        maker_uri = default_maker_uri

        if 'maker_uri' in self.polyConfig['customParams']:
            maker_uri = self.polyConfig['customParams']['maker_uri']
            if maker_uri != default_maker_uri:
                maker_st = True
            else:
                maker_st = False
        else:
            logging.error('Hubitat Maker API URL is not defined in configuration')
            maker_st = False

        if 'debug_enabled' in self.polyConfig['customParams']:
            debug_enabled = self.polyConfig['customParams']['debug_enabled']
            if debug_enabled == "true" or debug_enabled == "True":
                self.debug_enabled = True
            else:
                self.debug_enabled = False
        else:
            self.addCustomParam({'debug_enabled': "False"})

        # Make sure they are in the params
        self.addCustomParam({'maker_uri': maker_uri})


        if maker_uri == default_maker_uri:
            self.addNotice('Please set proper Hubitat and Maker API URI, and restart this NodeServer', 'HubitatNotice')

        if maker_st:
            return True
    '''
    def update_radon_long(self):
        # Calculate 24H average radon level
        total = 0
        count = 0
        delete_list = []
        now = int(time.time())
        logging.debug('Calculating Radon 24H average from {} readings'.format(len(self.airth_radon_readings)))  
        for timestamp in self.airth_radon_readings:
            #logging.debug('Radon timestamp: {} value: {}'.format(timestamp, self.airth_radon_readings[timestamp]))
            if now - timestamp <= 86400:
                total += self.airth_radon_readings[timestamp]
                count += 1
            else:
                delete_list.append(timestamp)
        for timestamp in delete_list:
            del self.airth_radon_readings[timestamp]    

        if count > 0:
            avg_radon = round(total/count,1)
        else:
            avg_radon = 0
        logging.debug('Radon 24H average: {} pCi/L'.format(avg_radon))
        return avg_radon
    
    def discover(self, *args, **kwargs):
        assigned_addresses =['controller']    
        r = requests.get(self.maker_uri)
        logging.debug('respose code {}'.format(r.status_code))
        while r.status_code!= self.RESPONSE_OK:
            time.sleep(30)
            logging.error('Hubitat not responding - waiting for good response')
            r = requests.get(self.maker_uri)
        data = r.json()
        logging.debug('Hubitat data::{}'.format(json.dumps(data, indent=4, separators=(',', ': ') )))

        for dev in data:
            logging.debug('device id: {}'.format(dev))
            _name = dev['name']

            _label = self.poly.getValidName(dev['label'])
            _type = dev['type']
            #_id = 'hubitat'+ dev['id']
            _id =  dev['id']
            self.device_list[_id] = dev
            dev['temp_unit'] = self.temp_unit
            # if dev['type'] == 'Virtual Switch':
            #     self.addNode(node_types.VirtualSwitchNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'Generic Z-Wave Switch':
            #     self.addNode(node_types.ZWaveSwitchNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'Generic Z-Wave Dimmer':
            #     self.addNode(node_types.ZWaveDimmerNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'Generic Zigbee Bulb':
            #     self.addNode(node_types.ZigbeeBulbNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'NYCE Motion Sensor Series':
            #     self.addNode(node_types.NYCEMotionSensorNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'Zooz 4-in-1 Sensor':
            #     self.addNode(node_types.Zooz4n1SensorNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'Hue Motion Sensor':
            #     self.addNode(node_types.HueMotionSensorNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'Dome Motion Sensor':
            #     self.addNode(node_types.DomeMotionSensorNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # # if dev['type'] == 'Zooz Power Switch':
            # #     self.addNode(node_types.ZoozPowerSwitchNode(self.poly,  self.address, _id, _label, self.maker_uri ))
            # if dev['type'] == 'Fibaro Motion Sensor ZW5':
            #     self.addNode(node_types.FibaroZW5Node(self.poly,  self.address, _id, _label, self.maker_uri ))
            
            if dev['type'] == 'Lutron Pico':
                node_types.LutronPicoNode(self.poly, self.address, _id, _label, self.maker_uri )
                '''
                elif dev['type'] == 'Lutron Fast Pico':
                    node_types.LutronFastPicoNode( self.poly, self.address, _id, _label, self.maker_uri )
                elif dev['type'] == 'Virtual Switch':
                    node_types.SwitchNode(self.poly, self.address, _id, _label, self.maker_uri )
                elif dev['type'] == 'Virtual Dimmer':
                    node_types.DimmerNode(self.poly,  self.address, _id, _label, self.maker_uri )
                '''
            elif dev['type'] == 'Air Things Device':
                node_types.AirThingsSensor(self.poly,  self.address, _id, _label, self.maker_uri, dev )

            elif dev['type'] == 'Ecobee Sensor':
                #nodeAdr = str(_id)
                node_types.EcobeeSensor(self.poly,  self.address, _id, _label, self.maker_uri, dev )
            elif dev['type'] == 'Ecobee Thermostat':
                #nodeAdr = str(_id)
                node_types.EcobeeThermostat(self.poly,  self.address, _id, _label, self.maker_uri, dev )                                
                
            elif 'Light' in dev['capabilities']:
                if 'ColorTemperature' in dev['capabilities']:
                    if 'ColorControl' in dev['capabilities']:
                        node_types.RgbLampNode(self.poly,  self.address, _id, _label, self.maker_uri )
                    else:
                        node_types.CtLampNode(self.poly,  self.address, _id, _label, self.maker_uri )
                else:
                    node_types.StdLampNode(self.poly,  self.address, _id, _label, self.maker_uri )
       
            elif 'Outlet' in dev['capabilities']:
                if 'EnergyMeter' in dev['capabilities']:
                    node_types.EnergyOutletNode(self.poly,  self.address, _id, _label, self.maker_uri )
                else:
                    node_types.OutletNode(self.poly,  self.address, _id, _label, self.maker_uri )
  
            elif 'Switch' in dev['capabilities']:
                if 'Virtual' not in dev['type']:
                    if 'Outlet' not in dev['capabilities']:
                        if 'Light' not in dev['capabilities']:
                            if 'Actuator' in dev['capabilities']:
                                if 'SwitchLevel' in dev['capabilities']:
                                    node_types.DimmerNode(self.poly,  self.address, _id, _label, self.maker_uri )
                                else:
                                    node_types.SwitchNode(self.poly,  self.address, _id, _label, self.maker_uri )
                            else:
                                node_types.SwitchNode(self.poly,  self.address, _id, _label, self.maker_uri )

                '''
                elif 'MotionSensor' in dev['capabilities']:
                    if 'TemperatureMeasurement' in dev['capabilities'] and 'IlluminanceMeasurement' in dev['capabilities']:
                        if 'AccelerationSensor' in dev['capabilities']:
                            node_types.MultiSensorTLAS(self.poly,  self.address, _id, _label, self.maker_uri )
                        elif 'RelativeHumidityMeasurement' in dev['capabilities']:
                            node_types.MultiSensorTHLA(self.poly,  self.address, _id, _label, self.maker_uri )
                        else:
                            node_types.MultiSensorTL(self.poly,  self.address, _id, _label, self.maker_uri )
                    elif 'TemperatureMeasurement' in dev['capabilities'] and 'RelativeHumidityMeasurement' in dev['capabilities']:
                        if 'IlluminanceMeasurement' not in dev['capabilities']:
                            node_types.MultiSensorTH(self.poly,  self.address, _id, _label, self.maker_uri )
                    elif 'IlluminanceMeasurement' in dev['capabilities']:
                        node_types.MultiSensorL(self.poly,  self.address, _id, _label, self.maker_uri )
                    elif 'TemperatureMeasurement' in dev['capabilities']:
                        node_types.MultiSensorT(self.poly,  self.address, _id, _label, self.maker_uri )
                    else:
                        node_types.MotionSensor(self.poly,  self.address, _id, _label, self.maker_uri )

                elif dev['type'] == 'Sonoff Zigbee Temperature/Humidity Sensor':
                    node_types.THSensor(self.poly,  self.address, _id, _label, self.maker_uri )

                elif 'ContactSensor' in dev['capabilities']:
                    node_types.ContactNode(self.poly,  self.address, _id, _label, self.maker_uri )
                # newly added
                '''
            
            elif 'PushableButton' in dev['capabilities']:
                node_types.SimpleRemoteNode(self.poly,  self.address, _id, _label, self.maker_uri )  

            assigned_addresses.append(_id)    
            
        # Build node list
        self.nodes = self.poly.getNodes()
        for node in self.nodes:
            self.node_list.append(self.nodes[node].address)
        # remove unused nodes still to be added
        
        self.nodes_in_db = self.poly.getNodesFromDb()
        logging.debug('Scanning db for extra nodes : {}'.format(assigned_addresses))
        for nde in range(0, len(self.nodes_in_db)):
            node = self.nodes_in_db[nde]
            #logging.debug('Scanning db for node : {}'.format(node))
            if node['address'] not in assigned_addresses:
                logging.debug('Removing node : {} {}'.format(node['name'], node))
                self.poly.delNode(node['address'])
        


    def delete(self):
        """
        Example
        This is sent by Polyglot upon deletion of the NodeServer. If the process is
        co-resident and controlled by Polyglot, it will be terminiated within 5 seconds
        of receiving this message.
        """
        logging.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def stop(self):
        logging.debug('NodeServer stopped.')

    def remove_notices_all(self,command):
        logging.info('remove_notices_all:')
        # Remove all existing notices
        self.poly.Notices.clear()
        #self.removeNoticesAll()

    def update_profile(self,command):
        logging.info('update_profile:')
        st = self.poly.updateProfile()
        return st
    
    def isnumber(self, string):
        try:
            float(string)
            return True
        except ValueError:
            return False

    def hubitat_events(self):
        logging.debug('hubitat_events')
        maker_uri = self.Parameters['maker_uri']
        ws_uri = 'ws://' + maker_uri.split('/')[2] + '/eventsocket'

        #logging.info(ws_uri)
        #logging.info(maker_uri)
        websocket = WebSocket(ws_uri)
        for event in websocket:
            if event.name == "text":
                if event.json['source'] == 'DEVICE':
                    logging.debug(json.dumps(event.json, indent=4, separators=(',', ': ') ))
                    _deviceId = str(event.json['deviceId'])
                    h_value = event.json['value']
                    if isinstance(h_value, str):
                        if self.isnumber(h_value):
                            if '.' in h_value:
                                h_value = float(h_value)
                            else:
                                h_value = int(h_value)

                    h_name = event.json['name']
                    h_type = event.json['type']
                    if h_type in ['null', '', None]:
                        h_type = self.device_list[_deviceId]['type']    
                    if 'date' in event.json:
                        temp_data = event.json['date']
                        dt = datetime.strptime(temp_data, '%Y-%m-%dT%H:%M:%S%z')
                        unixtime = int(dt.timestamp())
                    else:
                        unixtime = int(time.time())

                    logging.debug('Device Property: ' + h_name + " " + str(h_value) + " " + h_type)

                    if _deviceId in self.node_list:
                        m_node = self.nodes[_deviceId]

                        try:

                            if h_name == 'switch':
                                if h_value == 'on':
                                    m_node.my_setDriver('ST', 100)
                                    m_node.reportCmd('DON', 2)
                                elif h_value == 'off':
                                    m_node.my_setDriver('ST', 0)
                                    m_node.reportCmd('DOF', 2)
                            elif h_name == 'level':
                                m_node.my_setDriver('OL', h_value)
                            elif h_name == 'colorMode':
                                if h_value == 'CT':
                                    m_node.my_setDriver('GV5', 1)
                                elif h_value == 'RGB':
                                    m_node.my_setDriver('GV5', 2)
                                else:
                                    m_node.my_setDriver('GV5', 0)
                            elif h_name == 'colorTemperature':
                                m_node.my_setDriver('GV6', h_value)
                            elif h_name == 'hue':
                                m_node.my_setDriver('GV3', h_value)
                            elif h_name == 'saturation':
                                m_node.my_setDriver('GV4', h_value)
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
                            elif h_name == 'battery':
                                m_node.my_setDriver('BATLVL', h_value)
                            elif h_name in ['temperature']:
                                    #Need to separate Ecobee
                                if self.device_list[_deviceId] in ['Ecobee Sensor', 'Ecobee Thermostat']:
                                    if self.temp_unit == 'F':
                                        if self.EcoBee_t_unit == 'F':
                                            m_node.my_setDriver('CLITEMP', round(int(float(h_value)*2.0)/2, 1), 17)
                                        else: #C
                                            m_node.my_setDriver('CLITEMP', round(int(float((h_value+32)*9/5)*2.0)/2, 1), 17) 
                                    else:
                                        if self.EcoBee_t_unit == 'F':
                                            m_node.my_setDriver('CLITEMP', round(int(float((h_value*5/9-32)*2.0)/2, 1), 4))
                                        else:
                                            m_node.my_setDriver('CLITEMP', round(int(float(h_value)*2.0)/2, 1), 4)                                    
    
                                else:
                                    if self.temp_unit == 'F':           
                                        m_node.my_setDriver('CLITEMP', round(int(float((h_value*5/9-32)*2.0)/2, 1), 17))
                                    else:
                                        m_node.my_setDriver('CLITEMP', round(int(float(h_value)*2.0)/2, 1), 4)

                            elif h_name == 'humidity':
                                m_node.my_setDriver('CLIHUM', h_value)
                            elif h_name == 'illuminance':
                                m_node.my_setDriver('LUMIN', h_value)
                            elif h_name == 'current':
                                m_node.my_setDriver('CC', h_value)
                            elif h_name == 'currentH':
                                m_node.my_setDriver('GV0', h_value)
                            elif h_name == 'currentL':
                                m_node.my_setDriver('GV1', h_value)
                            elif h_name == 'energy':
                                m_node.my_setDriver('TPW', h_value)
                            elif h_name == 'power':
                                m_node.my_setDriver('CPW', h_value)
                            elif h_name == 'powerH':
                                m_node.my_setDriver('GV2', h_value)
                            elif h_name == 'powerL':
                                m_node.my_setDriver('GV3', h_value)
                            elif h_name == 'voltage':
                                m_node.my_setDriver('CV', h_value)
                            elif h_name == 'voltageH':
                                m_node.my_setDriver('GV4', h_value)
                            elif h_name == 'voltageL':
                                m_node.my_setDriver('GV5', h_value)
                            elif h_name == 'energyDuration':
                                _h_value = h_value.split(' ')[0]
                                m_node.my_setDriver('GV6', _h_value)
                                # Lutron Pico buttons ## and remote botton
                            elif h_name == 'pushed':
                                if h_value.isdigit():
                                    tmp = int(h_value)
                                    if tmp <= 0:
                                        tmp = 0
                                    if tmp >= 5:
                                        tmp = 5        
                                    m_node.my_setDriver('GV8',tmp)
                                    m_node.reportCmd('DON', 2)
                                else:
                                    logging.error ('Unexpected value: {}'.format(h_value))
                                '''                                
                                if h_value == '1':
                                    m_node.my_setDriver('GV7', h_value)
                                elif h_value == '2':
                                    m_node.my_setDriver('GV7', h_value)
                                elif h_value == '3':
                                    m_node.my_setDriver('GV7', h_value)
                                elif h_value == '4':
                                    m_node.my_setDriver('GV7', h_value)
                                elif h_value == '5':
                                    m_node.my_setDriver('GV7', h_value)
                                '''
                                m_node.my_setDriver('GV8', 0)
                                m_node.my_setDriver('GV9', 0)
                            elif h_name == 'released':
                                if h_value.isdigit():
                                    tmp = int(h_value)
                                    if tmp <= 0:
                                        tmp = 0
                                    if tmp >= 5:
                                        tmp = 5        
                                    m_node.my_setDriver('GV8',tmp)
                                    m_node.reportCmd('DOF', 2)
                                else:
                                    logging.error ('Unexpected value: {}'.format(h_value))
                                '''
                                if h_value == '1':
                                    m_node.my_setDriver('GV8', h_value)
                                elif h_value == '2':
                                    m_node.my_setDriver('GV8', h_value)
                                elif h_value == '3':
                                    m_node.my_setDriver('GV8', h_value)
                                elif h_value == '4':
                                    m_node.my_setDriver('GV8', h_value)
                                elif h_value == '5':
                                    m_node.my_setDriver('GV8', h_value)
                                '''
                                m_node.my_setDriver('GV7', 0)
                                m_node.my_setDriver('GV9', 0)
                            elif h_name == 'held':
                                if h_value.isdigit():
                                    tmp = int(h_value)
                                    if tmp <= 0:
                                        tmp = 0
                                    if tmp >= 5:
                                        tmp = 5
                                    m_node.my_setDriver('GV9',tmp)
                                else:
                                    logging.error ('Unexpected value: {}'.format(h_value))
                                '''
                                elif h_value == '2':
                                    m_node.my_setDriver('GV9', h_value)
                                elif h_value == '3':
                                    m_node.my_setDriver('GV9', h_value)
                                elif h_value == '4':
                                    m_node.my_setDriver('GV9', h_value)
                                elif h_value == '5':
                                    m_node.my_setDriver('GV9', h_value)
                                '''
                                m_node.my_setDriver('GV7', 0)
                                m_node.my_setDriver('GV8', 0)
                            elif h_name == 'contact':
                                if h_value == 'open':
                                    m_node.my_setDriver('ST', 0)
                                    m_node.reportCmd('DON', 2)
                                elif h_value == 'closed':
                                    m_node.my_setDriver('ST', 100)
                                    m_node.reportCmd('DOF', 2)

                            elif h_name== 'DeviceWatch-DeviceStatus':
                                if h_value == 'online':
                                    m_node.my_setDriver('GV20', 1)
                                else:
                                    m_node.my_setDriver('GV20', 0)
                            elif h_name== 'deviceAlive':
                                if h_value == 'online':
                                    m_node.my_setDriver('ST', 1)
                                else:
                                    m_node.my_setDriver('ST', 0)

                                                    
                            elif h_name == 'thermostatMode':
                                if h_value  == 'auto':
                                    m_node.my_setDriver('CLIMD', 0)
                                elif h_value  == 'cool':
                                    m_node.my_setDriver('CLIMD', 1)
                                elif h_value  == 'heat':                                    
                                    m_node.my_setDriver('CLIMD', 2)
                                elif h_value  == 'off':
                                    m_node.my_setDriver('CLIMD', 3)                                        
                                #elif h_value  == 'off':
                                #    m_node.my_setDriver('CLIMD', 4)
                                #elif h_value  == 'emergencyHeat':
                                #    m_node.my_setDriver('CLIMD', 5)
                                else:
                                    m_node.my_setDriver('CLIMD', 99)
                                    logging.error('Unknown value for {} {}'.format(h_name, h_value))
                            elif h_name== 'coolingSetpoint':
                                    if self.temp_unit == 'F':
                                        if self.EcoBee_t_unit == 'F':
                                            m_node.my_setDriver('CLISPC', round(int(float(h_value)*2.0)/2, 1), 17)
                                        else: #C
                                            m_node.my_setDriver('CLISPC', round(int(float((h_value+32)*9/5)*2.0)/2, 1), 17) 
                                    else:
                                        if self.EcoBee_t_unit == 'F':
                                             m_node.my_setDriver('CLISPC', round(int(float((h_value*5/9-32)*2.0)/2, 1), 4))
                                        else:
                                            m_node.my_setDriver('CLISPC', round(int(float(h_value)*2.0)/2, 1), 4)
                            elif h_name== 'heatingSetpoint':
                                    if self.temp_unit == 'F':
                                        if self.EcoBee_t_unit == 'F':
                                            m_node.my_setDriver('CLISPH', round(int(float(h_value)*2.0)/2, 1), 17)
                                        else: #C
                                            m_node.my_setDriver('CLISPH', round(int(float((h_value+32)*9/5)*2.0)/2, 1), 17) 
                                    else:
                                        if self.EcoBee_t_unit == 'F':
                                             m_node.my_setDriver('CLISPH', round(int(float((h_value*5/9-32)*2.0)/2, 1), 4))
                                        else:
                                            m_node.my_setDriver('CLISPH', round(int(float(h_value)*2.0)/2, 1), 4)                                    
                            elif h_name == 'thermostatFanMode':
                                if h_value  == 'auto':
                                    m_node.my_setDriver('CLIFRS', 0)
                                elif h_value  == 'on':
                                    m_node.my_setDriver('CLIFRS', 1)
                                else:
                                    m_node.my_setDriver('CLIMD', 99)
                                    logging.error('Unknown value for {} {}'.format(h_name, h_value))
                            elif h_name == 'thermostatOperatingState':
                                if -1 != h_value.find('auto'):
                                    m_node.my_setDriver('CLIHCS', 0)
                                elif -1 != h_value.find('cool'):
                                    m_node.my_setDriver('CLIHCS', 1)
                                elif -1 != h_value.find('heat'):                        
                                    m_node.my_setDriver('CLIHCS', 2)
                                elif -1 != h_value.find('off'):
                                    m_node.my_setDriver('CLIHCS', 3)
                                elif -1 != h_value.find('idle'):
                                    m_node.my_setDriver('CLIHCS', 4)                             
                                elif -1 != h_value.find('emergencyHeat'):
                                    m_node.my_setDriver('CLIHCS', 5)
                                else:
                                    m_node.my_setDriver('CLIHCS', 99)
                                    logging.error('Unknown value for {} {}'.format(h_name, h_value))
                            elif h_name == 'thermostatFanOperatingState':  # Not found this one yet so guessing name
                                if h_value  == 'auto':
                                    m_node.my_setDriver('CLIFS', 0)
                                if h_value  == 'on':
                                    m_node.my_setDriver('CLIFS', 1)
                                if h_value  == 'idle':
                                    m_node.my_setDriver('CLIFS', 2)
                                else:
                                    m_node.my_setDriver('CLIFS', 99)
                                    logging.error('Unknown value for {} {}'.format(h_name, h_value))       

                            elif h_name == 'deviceTemperatureUnit':
                                logging.debug('Temp Unit - no need to update')
                                self.EcoBee_t_unit = h_value

                            #elif h_name in ['fanAuto', 'fanCirculate', 'fanOn', 'off']:

                            #elif h_name in ['resumeProgram']:
                            #    m_node.my_setDriver(
                                    
                            elif h_name == 'deviceAlive':
                                logging.debug('deviceAlive')
                                if h_value  == 'true':
                                    m_node.my_setDriver('ST', 1,  25)
                                else:
                                    m_node.my_setDriver('ST', 0,  25)

                                '''
                                elif h_name == 'temperature':
                                        if self.temp_unit == 'F':
                                            if self.EcoBee_t_unit == 'F':
                                                m_node.my_setDriver('CLITEMP', round(int(float(h_value)*2.0)/2, 1), True, True, 17)
                                            else: #C
                                                m_node.my_setDriver('CLITEMP', round(int(float((h_value+32)*9/5)*2.0)/2, 1), True, True, 17) 
                                        else:
                                            if self.EcoBee_t_unit == 'F':
                                                m_node.my_setDriver('CLITEMP', round(int(float((h_value*5/9-32)*2.0)/2, 1), True, True, 4))
                                            else:
                                                m_node.my_setDriver('CLITEMP', round(int(float(h_value)*2.0)/2, 1), True, True, 4)
                                '''

                            elif h_name == 'motion':
                                if h_value  == 'inactive':
                                    m_node.my_setDriver('ST', 0,  25)
                                elif  h_value  == 'active':
                                    m_node.my_setDriver('ST', 1,  25)
                                else:
                                    m_node.my_setDriver('ST', 99, 25)


                            elif h_name == 'absHumidity':
                                m_node.my_setDriver('CLIHUM', h_value)

                            elif h_name in ['co2', 'carbonDioxide']:
                                m_node.my_setDriver('CO2LVL', h_value)

                            elif h_name in ['airQualityIndex']:
                                m_node.my_setDriver('AQI', h_value)

                            elif h_name in ['pressure']:
                                m_node.my_setDriver('ATMPRES', h_value)     
                            elif h_name in ['radonShortTermAvg']:
                            # Need to support Metric value 1 pCi/L is equivalent to 37 Bq/m3
                            
                                m_node.my_setDriver('RADON', round(h_value/37,1), 124)    
                                self.airth_radon_readings[unixtime] = h_value/37
                                logging.debug('Radon reading added: {} timestamp: {}'.format(round(h_value/37,1), unixtime))
                                
                            elif h_name in ['voc']:
                                if isinstance(h_value, (int, float)):
                                    if h_value < 250:
                                        m_node.my_setDriver('VOCLVL', 1)
                                    elif 250 <= h_value < 500:
                                        m_node.my_setDriver('VOCLVL', 2) 
                                    elif 500 <= h_value < 2000:
                                        m_node.my_setDriver('VOCLVL', 3)
                                    else:
                                        m_node.my_setDriver('VOCLVL', 4)

                                m_node.my_setDriver('GV2', h_value)
                            elif h_type == 'Air Things Device':
                                if h_name in ['pm25','pm1', 'absHumidity', 'voc']:
                                    if h_name == 'pm25':
                                        m_node.my_setDriver('GV25', h_value)
                                    elif h_name == 'pm1':
                                        m_node.my_setDriver('GV1', h_value)
                                    elif h_name == 'absHumidity':
                                        m_node.my_setDriver('GV0', h_value)
                                    elif h_name == 'voc':
                                        if isinstance(h_value, (int, float)):
                                            m_node.my_setDriver('GV2', h_value)
                                    elif h_name in ['radonShortTermAvg']:
                                        radon24H =self.update_radon_long()
                                        m_node.my_setDriver('ST', radon24H, 124)
                            elif h_name in ['battery']:
                                if isinstance(h_value, (int, float)):
                                    if h_value == 0:
                                        m_node.my_setDriver('BATLVL', 98, 25)
                                    else:
                                        m_node.my_setDriver('BATLVL', h_value)
                                m_node.my_setDriver('TIME', unixtime)


                            else:
                                print('Driver not implemented for {} {} {}'.format(h_name, h_value, event.json))
                        
                                '''
                                    "dataType": "NUMBER",
                                    "values": null,
                                    "pm12": null,
                                    "pm29": null,
                                    "relayDeviceType": "hub",
                                    "pm21": null,
                                    "rssi": "0",
                                X "absHumidity": "9.09",
                                    "pm10": null,
                                    "pm27": null,
                                X "pressure": "991.0",
                                X "co2": "662.0",
                                    X"carbonDioxide": "662.0",
                                    X"airQualityIndex": "12",
                                    "html": null,
                                    X"temperature": "20.1",
                                    "pm19": null,
                                    "pm23": null,
                                    "pm15": null,
                                    "humidity": "52.0",
                                    "pm25AqiText": "<span style='color:green'>Good</span>",
                                    "pm25": "3.0",
                                    "pm11": null,
                                    "pm17": null,
                                    "pm16": null,
                                    "pm14": null,
                                    "pm25Aqi": "12.5",
                                    "mold": null,
                                    "lastPoll": null,
                                    X"radonShortTermAvg": "103.0",
                                    "pm24": null,
                                    "pm18": null,
                                    "pm28": null,
                                    "pm20": null,
                                    "battery": "0",
                                    "pm1": "3.0",
                                    "pm22": null,
                                    "pm26": null,
                                    "voc": "269.0",
                                    "pm13": null
                                },

                                '''
                        except KeyError:
                            print('Device not found in ISY')

    id = 'controller'
    commands = {
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile,
        'REMOVE_NOTICES_ALL': remove_notices_all
    }
    drivers = [{'driver': 'ST', 'value': 1, 'uom': 2}]


if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        """
        Instantiates the Interface to Polyglot.
        """
        polyglot.start({ 'version': version, 'requestId': True })
        """
        Starts MQTT and connects to Polyglot.
        """
        polyglot.setCustomParamsDoc()
        control = Controller(polyglot, 'controller', 'controller', 'hubitat')
        """
        Creates the Controller Node and passes in the Interface
        """
        polyglot.ready()
        polyglot.runForever()
        """
        Sits around and does nothing forever, keeping your program running.
        """
    except (KeyboardInterrupt, SystemExit):
        logging.error(f"Error starting Nodeserver: {traceback.format_exc()}")
        polyglot.stop()
        sys.exit(0)
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
