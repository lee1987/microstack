#!/usr/bin/env python
"""
refresh_test.py

Verify that existing installs can refresh to our newly built snap.

"""
import json
import os
import sys
import unittest

sys.path.append(os.getcwd())

from tests.framework import Framework, check, check_output, call  # noqa E402


class TestRefresh(Framework):
    """Refresh from beta and from edge."""

    def test_refresh_from_beta(self):
        self._refresh_from('beta')
        self.passed = True

    def test_refresh_from_edge(self):
        self._refresh_from('edge')
        self.passed = True

    def _refresh_from(self, refresh_from='beta'):
        """Refresh test

        Like the basic test, but we refresh first.

        """
        print("Installing and verfying {} ...".format(refresh_from))
        host = self.get_host()
        host.install(snap="microstack", channel=refresh_from)
        host.init()
        prefix = host.prefix

        check(*prefix, '/snap/bin/microstack.launch', 'cirros',
              '--name', 'breakfast', '--retry')

        if 'multipass' in prefix:
            self.verify_instance_networking(host, 'breakfast')

        print("Upgrading ...")
        host.install()  # Install compiled snap
        # Should not need to re-init

        print("Verifying that refresh completed successfully ...")

        # Check our existing instance, starting it if necessary.
        if json.loads(check_output(*prefix, '/snap/bin/microstack.openstack',
                                   'server', 'show', 'breakfast',
                                   '--format', 'json'))['status'] == 'SHUTOFF':
            print("Starting breakfast (TODO: auto start.)")
            check(*prefix, '/snap/bin/microstack.openstack', 'server', 'start',
                  'breakfast')

        # Launch another instance
        check(*prefix, '/snap/bin/microstack.launch', 'cirros',
              '--name', 'lunch', '--retry')

        # Verify networking
        if 'multipass' in prefix:
            self.verify_instance_networking(host, 'breakfast')
            self.verify_instance_networking(host, 'lunch')

        # Verify GUI
        self.verify_gui(host)


if __name__ == '__main__':
    # Run our tests, ignoring deprecation warnings and warnings about
    # unclosed sockets. (TODO: setup a selenium server so that we can
    # move from PhantomJS, which is deprecated, to to Selenium headless.)
    unittest.main(warnings='ignore')
