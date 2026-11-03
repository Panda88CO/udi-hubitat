#!/usr/bin/env python3
"""
Test runner script for udi-hubitat.
Runs all unit tests in the tests/ directory.
"""
import os
import sys
import unittest

if __name__ == '__main__':
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    suite = unittest.defaultTestLoader.discover(tests_dir, pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(not result.wasSuccessful())

