#!/usr/bin/env python
"""
control_test.py

This is a test to verify that a control node gets setup properly.

"""

import sys
import os

import unittest

sys.path.append(os.getcwd())

from tests.framework import Framework, check, check_output  # noqa E402


class TestControlNode(Framework):

    def test_control_node(self):
        """A control node has all services running, so this shouldn't be any
        different than our standard setup.

        """

        host = self.get_host()
        host.install()
        host.init(['--control'])

        print("Checking output of services ...")
        services = check_output(
            *host.prefix, 'systemctl', 'status', 'snap.microstack.*',
            '--no-page')

        print("services: @@@")
        print(services)

        self.assertTrue('neutron-' in services)
        self.assertTrue('keystone-' in services)
        self.assertTrue('nova-' in services)

        self.passed = True


if __name__ == '__main__':
    # Run our tests, ignoring deprecation warnings and warnings about
    # unclosed sockets. (TODO: setup a selenium server so that we can
    # move from PhantomJS, which is deprecated, to to Selenium headless.)
    unittest.main(warnings='ignore')
