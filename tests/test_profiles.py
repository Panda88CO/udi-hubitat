"""
Unit tests for ISY/IoX profile definitions:
- profile/editor/editors.xml
- profile/nodedef/nodedefs.xml
- profile/nls/en_us.txt
- version.txt consistency
"""
import os
import unittest
import xml.etree.ElementTree as ET
from tests.test_helpers import PROJECT_ROOT, load_udi_hubitat


class TestProfiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editors_path = os.path.join(PROJECT_ROOT, 'profile', 'editor', 'editors.xml')
        cls.nodedefs_path = os.path.join(PROJECT_ROOT, 'profile', 'nodedef', 'nodedefs.xml')
        cls.nls_path = os.path.join(PROJECT_ROOT, 'profile', 'nls', 'en_us.txt')
        cls.version_path = os.path.join(PROJECT_ROOT, 'version.txt')
        cls.profile_version_path = os.path.join(PROJECT_ROOT, 'profile', 'version.txt')

        # Load NLS
        cls.nls_map = {}
        with open(cls.nls_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    cls.nls_map[k] = v

    def test_version_files_consistency(self):
        with open(self.version_path, 'r', encoding='utf-8') as f:
            root_version = f.read().strip()
        with open(self.profile_version_path, 'r', encoding='utf-8') as f:
            profile_version = f.read().strip()

        udi_mod = load_udi_hubitat()
        code_version = getattr(udi_mod, 'version', None)

        self.assertEqual(root_version, profile_version, "version.txt and profile/version.txt must match")
        self.assertEqual(root_version, code_version, "version.txt and udi-hubitat.py version must match")

    def test_nls_formatting_no_spaces_around_equal(self):
        with open(self.nls_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw or raw.startswith('#') or '=' not in raw:
                    continue
                k, v = raw.split('=', 1)
                self.assertEqual(k, k.rstrip(), f"Line {idx} has whitespace before '=': {raw}")
                self.assertEqual(v, v.lstrip(), f"Line {idx} has whitespace after '=': {raw}")

    def test_editors_xml_validity_and_rules(self):
        tree = ET.parse(self.editors_path)
        root = tree.getroot()
        self.assertEqual(root.tag, 'editors')

        editor_ids = []
        for editor in root.findall('editor'):
            eid = editor.attrib.get('id')
            self.assertIsNotNone(eid, "Editor must have an id attribute")
            self.assertEqual(eid, eid.upper(), f"Editor ID '{eid}' must be uppercase")
            self.assertNotIn('_', eid, f"Editor ID '{eid}' must not contain underscores")
            self.assertNotIn('-', eid, f"Editor ID '{eid}' must not contain dashes")
            editor_ids.append(eid)

        # Check TRUEFALSE editor is present
        self.assertIn('TRUEFALSE', editor_ids, "TRUEFALSE editor must exist in editors.xml")

    def test_nodedefs_xml_validity_and_editor_references(self):
        editors_tree = ET.parse(self.editors_path)
        valid_editors = {e.attrib.get('id') for e in editors_tree.getroot().findall('editor')}

        tree = ET.parse(self.nodedefs_path)
        root = tree.getroot()
        self.assertEqual(root.tag, 'nodeDefs')

        for nd in root.findall('nodeDef'):
            nid = nd.attrib.get('id')
            nls = nd.attrib.get('nls')
            self.assertIsNotNone(nid, "nodeDef must have an id")
            self.assertIsNotNone(nls, f"nodeDef {nid} must have an nls")
            self.assertEqual(nid, nid.upper(), f"nodeDef id '{nid}' must be uppercase")
            self.assertNotIn('_', nid, f"nodeDef id '{nid}' must not contain underscores")

            # Check that NLS contains definition for nodeDef
            self.assertIn(f"ND-{nid}-NAME", self.nls_map, f"Missing ND-{nid}-NAME in en_us.txt")
            self.assertIn(f"ND-{nid}-ICON", self.nls_map, f"Missing ND-{nid}-ICON in en_us.txt")

            # Check driver sts
            sts = nd.find('sts')
            if sts is not None:
                for st in sts.findall('st'):
                    sid = st.attrib.get('id')
                    editor = st.attrib.get('editor')
                    self.assertIn(editor, valid_editors, f"nodeDef {nid} st {sid} references invalid editor '{editor}'")
                    # Check driver name in NLS
                    nls_key = f"ST-{nls}-{sid}-NAME"
                    self.assertIn(nls_key, self.nls_map, f"Missing {nls_key} in en_us.txt for nodeDef {nid}")

            # Check accepted command IDs
            accepts = nd.find('cmds/accepts')
            if accepts is not None:
                for cmd in accepts.findall('cmd'):
                    cid = cmd.attrib.get('id')
                    self.assertEqual(cid, cid.upper(), f"Command id '{cid}' in {nid} must be uppercase")
                    self.assertNotIn('_', cid, f"Command id '{cid}' in {nid} must not contain underscores")


if __name__ == '__main__':
    unittest.main()

