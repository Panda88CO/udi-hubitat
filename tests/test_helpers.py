"""
Shared test fixtures and mocks for udi-hubitat test suite.
Allows running all unit tests in any Python environment without
requiring a live Polyglot interface, network connection, or Hubitat hub.
"""
import importlib.util
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class MockPolyglot:
    """Mock for udi_interface.Interface."""
    STOP = 'stop'
    START = 'start'
    CUSTOMPARAMS = 'customparams'
    CONFIGDONE = 'configdone'
    ADDNODEDONE = 'addnodedone'

    def __init__(self):
        self.subscriptions = {}
        self.nodes = {}
        self.nodes_in_db = []
        self.deleted_nodes = []
        self.ready_called = False
        self.profile_updated = False
        self.stopped = False
        self.Notices = {}

    def subscribe(self, event, callback, address=None):
        if event not in self.subscriptions:
            self.subscriptions[event] = []
        self.subscriptions[event].append((callback, address))

    def ready(self):
        self.ready_called = True

    def stop(self):
        self.stopped = True

    def updateProfile(self):
        self.profile_updated = True
        return True

    def addNode(self, node):
        addr = getattr(node, 'address', None)
        if addr:
            self.nodes[addr] = node
            # Trigger ADDNODEDONE if subscribed
            if self.ADDNODEDONE in self.subscriptions:
                for cb, _ in self.subscriptions[self.ADDNODEDONE]:
                    cb({'address': addr})

    def getNode(self, address):
        return self.nodes.get(address)

    def getNodes(self):
        return self.nodes

    def getNodesFromDb(self):
        return self.nodes_in_db

    def delNode(self, address):
        self.deleted_nodes.append(address)
        if address in self.nodes:
            del self.nodes[address]

    def getValidAddress(self, address):
        import re
        return re.sub(r"[^A-Za-z0-9_]", "", str(address).lower())[:14]

    def getValidName(self, name):
        import re
        if name is None:
            return ""
        return re.sub(r"[^A-Za-z0-9_ ]", "", str(name))


class MockNodeInstance:
    """Mock for a node instance tracking driver updates and reported commands."""
    from udiLib import my_setDriver
    def __init__(self, address='mock_node', drivers=None):
        self.address = address
        self.drivers = drivers or []
        self.driver_values = {}
        self.reported_cmds = []

    def setDriver(self, key, value, report=True, force=False, uom=None):
        self.driver_values[key] = {'value': value, 'uom': uom, 'report': report, 'force': force}

    def reportCmd(self, cmd, val=None):
        self.reported_cmds.append({'cmd': cmd, 'val': val})

    def reportDrivers(self):
        pass


class MockResponse:
    """Mock for requests.Response."""
    def __init__(self, json_data=None, status_code=200, text=""):
        self._json = json_data or {}
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json


class MockRequests:
    """Mock for requests module."""
    def __init__(self, default_response=None):
        self.default_response = default_response or MockResponse()
        self.calls = []
        self.url_responses = {}

    def get(self, url, timeout=None, **kwargs):
        self.calls.append({'url': url, 'timeout': timeout, 'kwargs': kwargs})
        if url in self.url_responses:
            resp = self.url_responses[url]
            if isinstance(resp, Exception):
                raise resp
            return resp
        return self.default_response


def load_udi_hubitat():
    """Load udi-hubitat module dynamically since its filename contains a hyphen."""
    script_path = os.path.join(PROJECT_ROOT, 'udi-hubitat.py')
    spec = importlib.util.spec_from_file_location('udi_hubitat', script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
