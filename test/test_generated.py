from __future__ import absolute_import, division, print_function

import glob
import json
import os
import unittest

import taskcluster.sync


SOURCE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'taskcluster')
APIS_JSON_FILE = os.path.join(SOURCE_DIR, 'apis.json')
with open(APIS_JSON_FILE, "r") as fh:
    APIS_JSON = json.load(fh)


class TestGenerated(unittest.TestCase):
    """Ensure all apis in apis.json have a python file and class associated
    with them.
    """
    maxDiff = None

    def test_all_classes_exist(self):
        """test_generated | all apis have a class in taskcluster.sync
        """
        missingClasses = []
        for api in sorted(APIS_JSON.keys()):
            if api not in dir(taskcluster.sync):
                missingClasses.append(api)
        self.assertEqual(
            [], missingClasses,
            "The following classes are missing from taskcluster.sync: " + str(missingClasses)
        )

    def test_missing_files(self):
        """test_generated | all apis have a python file in taskcluster/sync
        """
        pyFiles = set(glob.glob(os.path.join(SOURCE_DIR, 'sync', '*.py')))
        expectedFiles = [os.path.join(SOURCE_DIR, 'sync', '__init__.py')]
        for api in sorted(APIS_JSON.keys()):
            expectedFiles.append(os.path.join(SOURCE_DIR, 'sync', '{}.py'.format(api)))
        expectedFiles = set(expectedFiles)
        expectedFiles.difference_update(pyFiles)
        self.assertEqual(expectedFiles, set([]),
                         "Missing the following files: " + str(sorted(list(expectedFiles))))

    def test_no_extra_files(self):
        """test_generated | no extra python files in taskcluster/sync
        """
        pyFiles = set(glob.glob(os.path.join(SOURCE_DIR, 'sync', '*.py')))
        expectedFiles = [os.path.join(SOURCE_DIR, 'sync', '__init__.py')]
        for api in sorted(APIS_JSON.keys()):
            expectedFiles.append(os.path.join(SOURCE_DIR, 'sync', '{}.py'.format(api)))
        expectedFiles = set(expectedFiles)
        pyFiles.difference_update(expectedFiles)
        self.assertEqual(pyFiles, set([]),
                         "Unexpected files found: " + str(sorted(list(pyFiles))))
