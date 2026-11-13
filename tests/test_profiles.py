"""
Unit tests for Dynamic JSON Profiles:
- data/base_profile.json schema & editor definitions
- profile_generator dynamic profile synthesis from real datasets
- version consistency between version.txt and udi-hubitat.py
"""
import os
import json
import ast
import unittest
import profile_generator
from tests.test_helpers import PROJECT_ROOT, load_udi_hubitat


class TestDynamicProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_profile_path = os.path.join(PROJECT_ROOT, 'data', 'base_profile.json')
        cls.version_path = os.path.join(PROJECT_ROOT, 'version.txt')
        cls.dataset_path = os.path.join(PROJECT_ROOT, 'dataset.json')
        cls.zb_path = os.path.join(PROJECT_ROOT, 'ZB devices hubitat.txt')

    def test_version_files_consistency(self):
        with open(self.version_path, 'r', encoding='utf-8') as f:
            root_version = f.read().strip()

        udi_mod = load_udi_hubitat()
        code_version = getattr(udi_mod, 'version', None)

        self.assertEqual(root_version, code_version, "version.txt and udi-hubitat.py version must match")
        self.assertEqual(root_version, '0.2.0')

    def test_base_profile_json_validity(self):
        self.assertTrue(os.path.exists(self.base_profile_path), "data/base_profile.json must exist")
        with open(self.base_profile_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.assertIn("editors", data)
        self.assertIsInstance(data["editors"], list)
        editors_by_id = {ed["id"]: ed["ranges"] for ed in data["editors"]}

        # Essential standard editors
        required_editors = [
            'TRUEFALSE', 'STATUS', 'OL', 'BATLVL', 'CLITEMP', 'CLIHUM',
            'LUMIN', 'RADON', 'CO2LVL', 'VOCLVL', 'PARTICLE', 'ATMPRES'
        ]
        for ed in required_editors:
            self.assertIn(ed, editors_by_id, f"Base profile must define editor {ed}")
            ranges = editors_by_id[ed]
            self.assertIsInstance(ranges, list)
            self.assertGreater(len(ranges), 0)
            for r in ranges:
                self.assertIn("uom", r)
                self.assertIsInstance(r["uom"], str, f"uom in {ed} must be a quoted string")
                self.assertNotIn("nls", r, f"nls in {ed} must be replaced with inline names")

    def test_dynamic_profile_generation_dataset_json(self):
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            devices = json.load(f)

        profile = profile_generator.generate_profile(devices, temp_unit='F')

        self.assertIn("editors", profile)
        self.assertIsInstance(profile["editors"], list)
        self.assertIn("nodedefs", profile)
        self.assertIsInstance(profile["nodedefs"], list)

        nodedefs_by_id = {nd["id"]: nd for nd in profile["nodedefs"]}

        # Controller must always be present with lowercase id 'controller'
        self.assertIn("controller", nodedefs_by_id)
        for nd in profile["nodedefs"]:
            self.assertIn("id", nd)
            self.assertIn("name", nd)
            self.assertIn("properties", nd)
            self.assertIn("cmds", nd)
            self.assertIn("sends", nd["cmds"])
            self.assertIn("accepts", nd["cmds"])
            self.assertEqual(nd["links"], {"ctl": [], "rsp": []})
            if nd["id"] != "controller":
                prop_ids = [p["id"] for p in nd["properties"]]
                self.assertIn("ST", prop_ids, f"NodeDef {nd['id']} must have an ST property")

        # Ecobee Thermostat in dataset.json must produce THERMOSTAT nodedef
        self.assertIn("THERMOSTAT", nodedefs_by_id)
        tstat_drivers = [p["id"] for p in nodedefs_by_id["THERMOSTAT"]["properties"]]
        self.assertIn("ST", tstat_drivers)
        self.assertIn("CLIMD", tstat_drivers)
        self.assertIn("CLISPC", tstat_drivers)
        self.assertIn("CLISPH", tstat_drivers)
        self.assertIn("CLITEMP", tstat_drivers)

        # Ecobee Sensor must produce motion + temp nodedef
        self.assertIn("ND_MOT_TMP", nodedefs_by_id)
        sensor_drivers = [p["id"] for p in nodedefs_by_id["ND_MOT_TMP"]["properties"]]
        self.assertIn("ST", sensor_drivers)
        self.assertIn("CLITEMP", sensor_drivers)

    def test_dynamic_profile_generation_zigbee_dataset(self):
        with open(self.zb_path, 'r', encoding='utf-8') as f:
            lines = [f.readline() for _ in range(8)]
        text = ''.join(lines)
        devices = ast.literal_eval(text)

        profile = profile_generator.generate_profile(devices, temp_unit='F')
        nodedefs_by_id = {nd["id"]: nd for nd in profile["nodedefs"]}

        # Sengled bulb produces ND_SW_LVL
        self.assertIn("ND_SW_LVL", nodedefs_by_id)
        sw_lvl_drivers = [p["id"] for p in nodedefs_by_id["ND_SW_LVL"]["properties"]]
        self.assertIn("ST", sw_lvl_drivers)
        self.assertIn("OL", sw_lvl_drivers)

        # Zigbee switch produces ND_SW
        self.assertIn("ND_SW", nodedefs_by_id)

        # Zigbee outlet with power meter produces ND_SW_PWR
        self.assertIn("ND_SW_PWR", nodedefs_by_id)
        pwr_drivers = [p["id"] for p in nodedefs_by_id["ND_SW_PWR"]["properties"]]
        self.assertIn("ST", pwr_drivers)
        self.assertIn("GV2", pwr_drivers)

        # Aqara button remote produces ND_BTN_BAT
        self.assertIn("ND_BTN_BAT", nodedefs_by_id)
        btn_drivers = [p["id"] for p in nodedefs_by_id["ND_BTN_BAT"]["properties"]]
        self.assertIn("ST", btn_drivers)
        self.assertIn("GV4", btn_drivers)
        self.assertIn("GV5", btn_drivers)
        self.assertIn("GV6", btn_drivers)
        self.assertIn("BATLVL", btn_drivers)

    def test_nodedef_id_rules(self):
        """Non-controller NodeDef IDs must be uppercase, <= 14 characters, without spaces."""
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            devices = json.load(f)

        profile = profile_generator.generate_profile(devices)
        for nd in profile["nodedefs"]:
            nodedef_id = nd["id"]
            if nodedef_id == "controller":
                continue
            self.assertTrue(nodedef_id.isupper(), f"NodeDef ID {nodedef_id} must be uppercase")
            self.assertLessEqual(len(nodedef_id), 14, f"NodeDef ID {nodedef_id} exceeds 14 chars")
            self.assertNotIn(" ", nodedef_id, f"NodeDef ID {nodedef_id} must not contain spaces")


if __name__ == '__main__':
    unittest.main()
