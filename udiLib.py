try:
    import udi_interface
    logging = udi_interface.LOGGER
    Custom = udi_interface.Custom
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)



def my_setDriver(self, key, value, Unit=None, force=False, type=None):
    logging.debug(f'my_setDriver : {key} {value} {Unit} ')
    try:
        if any(item.get('driver') == key for item in self.drivers):
            if value is None:
                if type is not 'event':
                    logging.debug('None value passed = seting 99, UOM 25')
                    self.node.setDriver(key, 99, True, force, 25)
            else:                
                if isinstance(Unit, (int, float)):
                    self.node.setDriver(key, value, True, force, uom=Unit)
                else:
                    self.node.setDriver(key, value,True, force)
        else:
            logging.debug(f'Passed driver {key} does not exist in {self.drivers}')

    except ValueError: #A non number was passed 
        logging.error('Non numeric value passed to my_setDriver - setting 99 ')
        self.node.setDriver(key, 99, True, True, 25)