#!/usr/bin/env python3

#try:
#    import polyinterface
#except ImportError:
#    import pgc_interface as polyinterface


import udi_interface
logging = udi_interface.LOGGER
Custom = udi_interface.Custom


import sys
import time
import requests
import traceback
from lomond import WebSocket
import node_types
version = '0.1.0'
#LOGGER = polyinterface.LOGGER

class Controller(udi_interface.Node):
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


    def start(self):
        logging.info('Started Hubitat')
        self.node.setDriver('ST', 1, True, True)
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
        self.node.setDriver('ST', 0, True, True)
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

    def discover(self, *args, **kwargs):
        r = requests.get(self.maker_uri)
        logging.debug('respose code {}'.format(r.status_code))
        while r.status_code!= self.RESPONSE_OK:
            time.sleep(30)
            logging.error('Hubitat not responding - waiting for good response')
            r = requests.get(self.maker_uri)
        data = r.json()

        for dev in data:
            logging.debug('device id: {}'.format(dev))
            _name = dev['name']
            _label = dev['label']
            _type = dev['type']
            _id = dev['id']

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
            if dev['type'] == 'Lutron Fast Pico':
                node_types.LutronFastPicoNode( self.poly, self.address, _id, _label, self.maker_uri )
            if dev['type'] == 'Virtual Switch':
                node_types.SwitchNode(self.poly, self.address, _id, _label, self.maker_uri )
            if dev['type'] == 'Virtual Dimmer':
                node_types.DimmerNode(self.poly,  self.address, _id, _label, self.maker_uri )
                pass
            if 'Light' in dev['capabilities']:
                if 'ColorTemperature' in dev['capabilities']:
                    if 'ColorControl' in dev['capabilities']:
                        node_types.RgbLampNode(self.poly,  self.address, _id, _label, self.maker_uri )
                    else:
                        node_types.CtLampNode(self.poly,  self.address, _id, _label, self.maker_uri )
                else:
                    node_types.StdLampNode(self.poly,  self.address, _id, _label, self.maker_uri )

            if 'Outlet' in dev['capabilities']:
                if 'EnergyMeter' in dev['capabilities']:
                    node_types.EnergyOutletNode(self.poly,  self.address, _id, _label, self.maker_uri )
                else:
                    node_types.OutletNode(self.poly,  self.address, _id, _label, self.maker_uri )

            if 'Switch' in dev['capabilities']:
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

            if 'MotionSensor' in dev['capabilities']:
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

            if dev['type'] == 'Sonoff Zigbee Temperature/Humidity Sensor':
                node_types.THSensor(self.poly,  self.address, _id, _label, self.maker_uri )

            if 'ContactSensor' in dev['capabilities']:
                node_types.ContactNode(self.poly,  self.address, _id, _label, self.maker_uri )
            # newly added
            if 'PushableButton' in dev['capabilities']:
                node_types.SimpleRemoteNode(self.poly,  self.address, _id, _label, self.maker_uri )  

        # Build node list
        self.nodes = self.poly.getNodes()
        for node in self.nodes:
            self.node_list.append(self.nodes[node].address)

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
        st = self.poly.installprofile()
        return st

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
                    _deviceId = str(event.json['deviceId'])
                    h_value = event.json['value']
                    h_name = event.json['name']

                    if self.debug_enabled:
                        logging.debug('---------------- Hubitat Device Info ----------------')
                        logging.debug(event.json)
                        logging.debug('Device Property: ' + h_name + " " + h_value)
                        logging.debug('-----------------------------------------------------')

                    if _deviceId in self.node_list:
                        m_node = self.nodes[_deviceId]

                        try:
                            if h_name == 'switch':
                                if h_value == 'on':
                                    m_node.setDriver('ST', 100)
                                    m_node.reportCmd('DON', 2)
                                elif h_value == 'off':
                                    m_node.setDriver('ST', 0)
                                    m_node.reportCmd('DOF', 2)
                            elif h_name == 'level':
                                m_node.setDriver('OL', h_value)
                            elif h_name == 'colorMode':
                                if h_value == 'CT':
                                    m_node.setDriver('GV5', 1)
                                elif h_value == 'RGB':
                                    m_node.setDriver('GV5', 2)
                                else:
                                    m_node.setDriver('GV5', 0)
                            elif h_name == 'colorTemperature':
                                m_node.setDriver('GV6', h_value)
                            elif h_name == 'hue':
                                m_node.setDriver('GV3', h_value)
                            elif h_name == 'saturation':
                                m_node.setDriver('GV4', h_value)
                            elif h_name == 'motion':
                                if h_value == 'active':
                                    m_node.setDriver('ST', 100)
                                    m_node.reportCmd('DON', 2)
                                elif h_value == 'inactive':
                                    m_node.setDriver('ST', 0)
                                    m_node.reportCmd('DOF', 2)
                            elif h_name == 'tamper':
                                if h_value == 'detected':
                                    m_node.setDriver('ALARM', 1)
                                elif h_value == 'clear':
                                    m_node.setDriver('ALARM', 0)
                            elif h_name == 'acceleration':
                                if h_value == 'active':
                                    m_node.setDriver('SPEED', 1)
                                elif h_value == 'inactive':
                                    m_node.setDriver('SPEED', 0)
                            elif h_name == 'battery':
                                m_node.setDriver('BATLVL', h_value)
                            elif h_name == 'temperature':
                                s_temp = str(int(float(h_value)))
                                m_node.setDriver('CLITEMP', s_temp)
                            elif h_name == 'humidity':
                                m_node.setDriver('CLIHUM', h_value)
                            elif h_name == 'illuminance':
                                m_node.setDriver('LUMIN', h_value)
                            elif h_name == 'current':
                                m_node.setDriver('CC', h_value)
                            elif h_name == 'currentH':
                                m_node.setDriver('GV0', h_value)
                            elif h_name == 'currentL':
                                m_node.setDriver('GV1', h_value)
                            elif h_name == 'energy':
                                m_node.setDriver('TPW', h_value)
                            elif h_name == 'power':
                                m_node.setDriver('CPW', h_value)
                            elif h_name == 'powerH':
                                m_node.setDriver('GV2', h_value)
                            elif h_name == 'powerL':
                                m_node.setDriver('GV3', h_value)
                            elif h_name == 'voltage':
                                m_node.setDriver('CV', h_value)
                            elif h_name == 'voltageH':
                                m_node.setDriver('GV4', h_value)
                            elif h_name == 'voltageL':
                                m_node.setDriver('GV5', h_value)
                            elif h_name == 'energyDuration':
                                _h_value = h_value.split(' ')[0]
                                m_node.setDriver('GV6', _h_value)
                                # Lutron Pico buttons ## and remobe botton
                            elif h_name == 'pushed':
                                if h_value == '1':
                                    m_node.setDriver('GV7', h_value)
                                elif h_value == '2':
                                    m_node.setDriver('GV7', h_value)
                                elif h_value == '3':
                                    m_node.setDriver('GV7', h_value)
                                elif h_value == '4':
                                    m_node.setDriver('GV7', h_value)
                                elif h_value == '5':
                                    m_node.setDriver('GV7', h_value)
                            elif h_name == 'released':
                                if h_value == '1':
                                    m_node.setDriver('GV8', h_value)
                                elif h_value == '2':
                                    m_node.setDriver('GV8', h_value)
                                elif h_value == '3':
                                    m_node.setDriver('GV8', h_value)
                                elif h_value == '4':
                                    m_node.setDriver('GV8', h_value)
                                elif h_value == '5':
                                    m_node.setDriver('GV8', h_value)
                            elif h_name == 'held':
                                if h_value.isdigit():
                                    m_node.setDriver('GV9', int(h_value))
                                elif h_value == '2':
                                    m_node.setDriver('GV9', h_value)
                                elif h_value == '3':
                                    m_node.setDriver('GV9', h_value)
                                elif h_value == '4':
                                    m_node.setDriver('GV9', h_value)
                                elif h_value == '5':
                                    m_node.setDriver('GV9', h_value)
                            elif h_name == 'contact':
                                if h_value == 'open':
                                    m_node.setDriver('ST', 0)
                                    m_node.reportCmd('DON', 2)
                                elif h_value == 'closed':
                                    m_node.setDriver('ST', 100)
                                    m_node.reportCmd('DOF', 2)
                            else:
                                print('Driver not implemented')
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
